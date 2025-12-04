import asyncio
import json
import re
import time
from typing import List, Optional, cast, AnyStr, Any, Dict, Coroutine
from uuid import uuid4

from app.core.central_orchestrator.central_orchestrator import CentralOrchestrator
from app.core.central_orchestrator.version_management_center.record import OperatorExecutionRecord
from app.core.central_orchestrator.version_management_center.vmc_provider import vmc
from app.core.service.agent_service import AgentService
from contourpy.util.data import simple
from fontTools.ttLib.tables.ttProgram import instructions

from app.core.common.system_env import SystemEnv

from app.core.reasoner.model_service_factory import ModelServiceFactory

from app.core.reasoner.model_service import ModelService

from app.core.prompt.reasoner import OPERATOR_PROMPT_TEMPLATE, OPERATOR_SUMMARY_PROMPT_TEMPLATE, \
    OPERATOR_ACTION_INPUT_PROMPT_TEMPLATE
from app.core.reasoner.simple_reasoner import SimpleReasoner
from app.core.service.action_service import ActionService, ActionPipeline
from app.core.service.operator_service import OperatorService
from app.core.toolkit.action import Action

from app.core.env.insight.insight import Insight
from app.core.model.file_descriptor import FileDescriptor
from app.core.model.job import Job, SubJob
from app.core.model.knowledge import Knowledge
from app.core.model.message import FileMessage, HybridMessage, MessageType, WorkflowMessage
from app.core.model.task import Task
from app.core.reasoner.reasoner import Reasoner
from app.core.service.file_service import FileService
from app.core.service.knowledge_base_service import KnowledgeBaseService
from app.core.service.message_service import MessageService
from app.core.service.tool_connection_service import ToolConnectionService
from app.core.service.toolkit_service import ToolkitService
from app.core.workflow.operator_config import OperatorConfig


class Operator:
    """Operator is a sequence of actions and tools that need to be executed.

    Attributes:
        _id (str): The unique identifier of the operator.
        _config (OperatorConfig): The configuration of the operator.
    """

    def __init__(self, config: OperatorConfig):
        self._name = config.name
        self._config: OperatorConfig = config
        self._model = ModelServiceFactory.create(
            model_platform_type=SystemEnv.MODEL.value,
        )
        self._private_reasoner = SimpleReasoner()
        self._action_service: ActionService = ActionService.instance

    async def execute_new_version(
        self,
        reasoner: Reasoner,
        job: Job,
        workflow_messages: Optional[List[WorkflowMessage]] = None,
        previous_expert_outputs: Optional[List[WorkflowMessage]] = None,
        lesson: Optional[str] = None,
    ) -> WorkflowMessage:
        """Execute operator using the new multi-action pipeline + VMC logging."""

        # 1) 获取执行上下文（包含 workflow_version_id / trace_id / span 管理）
        central_orchestrator: CentralOrchestrator = CentralOrchestrator.instance
        expert_name = job.assigned_expert_name
        ctx = central_orchestrator.get_execution_context(expert_name=expert_name)

        op_id = self.get_id()
        operator_span_id = ctx.new_operator_span(op_id)

        # 2) 获取该 Operator 实际需要处理的 task（由 orchestrator 动态提供）
        task: str = central_orchestrator.get_running_operator_task(
            expert_name=expert_name,
            op_id=op_id,
        )

        # 3) 并行构建 action-DAG + 摘要上下文
        start_time = time.time()
        built_actions_dag, summarize_message = await asyncio.gather(
            self._build_actions_line(task=task, lesson=lesson),
            self.summarize_messages(
                task=task,
                job=job,
                workflow_messages=workflow_messages,
                previous_expert_outputs=previous_expert_outputs,
                lesson=lesson,
            ),
        )

        # 4) 执行 action pipeline
        action_pipeline = ActionPipeline(
            built_actions_dag,
            summarize_message,
            job.id,
            op_id,
            job,
        )
        results: str = await action_pipeline.run()

        # 5) 得到最后 operator 输出
        final_answer = await self.conclude(results)
        final_message = WorkflowMessage(payload={"scratchpad": final_answer}, job_id=job.id)

        # 6) 计算耗时
        latency_ms = (time.time() - start_time) * 1000

        # 7) 通知 orchestrator 当前 operator 已结束（用于 supervisor 审核）
        central_orchestrator.notify_operator_result(
            expert_name=expert_name,
            operator_id=op_id,
            answer=final_answer,
            task=task,
            job_id=job.id,
        )

        # 8) 写 OperatorExecutionRecord → Version Management Center
        record = OperatorExecutionRecord(
            operator_id=op_id,
            workflow_version_id=ctx.workflow_version_id,
            expert_name=ctx.expert_name,

            trace_id=ctx.trace_id,
            span_id=operator_span_id,
            parent_span_id=ctx.get_operator_parent_span(),

            operator_name=self._config.name,
            operator_config=self._config.to_dict(),

            job_input={
                "previous_operator_outputs": workflow_messages or [],
                "previous_expert_outputs": previous_expert_outputs or [],
                "lesson": lesson,
            },

            output_message=final_message,
            latency_ms=latency_ms,
        )
        vmc.log_operator(record)

        # 9) 返回最终消息
        return final_message


    async def execute(
            self,
            reasoner: Reasoner,
            job: Job,
            workflow_messages: Optional[List[WorkflowMessage]] = None,
            previous_expert_outputs: Optional[List[WorkflowMessage]] = None,
            lesson: Optional[str] = None,
    ) -> WorkflowMessage:
        """Execute the operator by LLM client.

        Args:
            reasoner (Reasoner): The reasoner.
            job (Job): The job assigned to the expert.
            workflow_messages (Optional[List[WorkflowMessage]]): The outputs of previous operators.
            previous_expert_outputs (Optional[List[WorkflowMessage]]): The outputs of previous
                experts in workflow message type.
            lesson (Optional[str]): The lesson learned (provided by the successor expert).
        """
        task = self._build_task(
            job=job,
            workflow_messages=workflow_messages,
            previous_expert_outputs=previous_expert_outputs,
            lesson=lesson,
        )

        # infer by the reasoner
        result = await reasoner.infer(task=task)

        # destroy MCP connections for the operator
        tool_connection_service: ToolConnectionService = ToolConnectionService.instance
        await tool_connection_service.release_connection(call_tool_ctx=task.get_tool_call_ctx())

        return WorkflowMessage(payload={"scratchpad": result}, job_id=job.id)


    def _build_task(
            self,
            job: Job,
            workflow_messages: Optional[List[WorkflowMessage]] = None,
            previous_expert_outputs: Optional[List[WorkflowMessage]] = None,
            lesson: Optional[str] = None,
    ) -> Task:
        toolkit_service: ToolkitService = ToolkitService.instance
        file_service: FileService = FileService.instance
        message_service: MessageService = MessageService.instance
        # 获取到推荐的tools 和 actions
        rec_tools, rec_actions = toolkit_service.recommend_tools_actions(
            actions=self._config.actions,
            threshold=self._config.threshold,
            hops=self._config.hops,
        )

        merged_workflow_messages: List[WorkflowMessage] = workflow_messages or []
        merged_workflow_messages.extend(previous_expert_outputs or [])

        # 提供获取文件内容的方法
        file_descriptors: List[FileDescriptor] = []
        if isinstance(job, SubJob):
            original_job_id: Optional[str] = job.original_job_id
            assert original_job_id is not None, "SubJob must have an original job id"
        else:
            original_job_id = job.id
        # 从hybrid_message中获取到信息
        hybrid_messages: List[HybridMessage] = cast(
            List[HybridMessage],
            message_service.get_message_by_job_id(
                job_id=original_job_id, message_type=MessageType.HYBRID_MESSAGE
            ),
        )
        for hybrid_message in hybrid_messages:
            # get the file descriptors from the hybrid message
            attached_messages = hybrid_message.get_attached_messages()
            for attached_message in attached_messages:
                if isinstance(attached_message, FileMessage):
                    file_descriptor = file_service.get_file_descriptor(
                        file_id=attached_message.get_file_id()
                    )
                    file_descriptors.append(file_descriptor)

        task = Task(
            job=job,
            operator_config=self._config,
            workflow_messages=merged_workflow_messages,
            tools=rec_tools,
            actions=rec_actions,
            knowledge=self.get_knowledge(job),
            insights=self.get_env_insights(),
            lesson=lesson,
            file_descriptors=file_descriptors,
        )
        return task


    def get_knowledge(self, job: Job) -> Knowledge:
        """Get the knowledge from the knowledge base."""
        query = "[JOB TARGET GOAL]:\n" + job.goal + "\n[INPUT INFORMATION]:\n" + job.context
        knowledge_base_service: KnowledgeBaseService = KnowledgeBaseService.instance
        return knowledge_base_service.get_knowledge(query, job.session_id)


    def get_env_insights(self) -> Optional[List[Insight]]:
        """Get the environment information."""
        # TODO: get the environment information
        return None


    def get_id(self) -> str:
        """Get the operator id."""
        return self._config.id


    def get_operator_config(self) -> OperatorConfig:
        return self._config

        # 构建actions的pipeline


    async def _build_actions_line(self, task, lesson) -> dict[Any, Any]:
        print("[operator] _build_actions_Pipeline……]")
        actions: List[Action] = self._config.actions
        actions_str = json.dumps([action.to_dict() for action in actions], indent=2)
        print(actions_str)
        prompt = OPERATOR_PROMPT_TEMPLATE.format(
            actions=actions_str,
            lesson=lesson,
            task=task
        )
        result = await self._private_reasoner.generate(prompt)
        action_dag = self.convert_to_action_line(result)
        return action_dag


    def convert_to_action_line(self, result) -> dict[Any, Any]:
        answer: List[Dict[str, Any]] = self.extract_json(result)
        actions_dag = self.build_dag(answer)
        return actions_dag


    def extract_json(self, s: str):
        """自动提取字符串中第一个合法 JSON 数组"""
        match = re.search(r"\[.*\]", s, re.DOTALL)
        if not match:
            raise ValueError("未找到 JSON 数组。")
        json_str = match.group(0)
        return json.loads(json_str)


    def build_dag(self, actions: list):
        """根据 action 列表构建 DAG 依赖图"""
        dag = {}
        for act in actions:
            dag[act["id"]] = {
                "name": act["name"],
                "task": act["task"],
                "prev": act.get("depends_on", []),
                "next": [],
                "parallel_group": act.get("parallel_group"),
                "order": act.get("order", 0),
            }

        # 填充 next 关系
        for act_id, node in dag.items():
            for dep in node["prev"]:
                if dep in dag:
                    dag[dep]["next"].append(act_id)

        return dag


    async def summarize_messages(
            self,
            task: str,
            job: Job,
            workflow_messages: Optional[List[WorkflowMessage]],
            previous_expert_outputs: Optional[List[WorkflowMessage]],
            lesson: Optional[str],
    ) -> WorkflowMessage:
        # ========== Step 1. 收集所有文本 ==========
        def extract_texts(messages):
            texts = []
            for m in messages or []:
                if isinstance(m, dict):
                    texts.append(m.get("content", ""))
                elif hasattr(m, "get_payload"):
                    payload = m.get_payload()
                    text = payload.get("content") or payload.get("summary") or str(payload)
                    texts.append(text)
                else:
                    texts.append(str(m))
            return [t.strip() for t in texts if t.strip()]

        wf_texts = extract_texts(workflow_messages)
        expert_texts = extract_texts(previous_expert_outputs)
        lesson_text = lesson.strip() if lesson else ""

        all_texts = wf_texts + expert_texts + ([lesson_text] if lesson_text else [])
        joined_text = "\n".join(all_texts)
        if len(joined_text) > 2500:
            joined_text = joined_text[-2500:]

        summary_prompt = OPERATOR_SUMMARY_PROMPT_TEMPLATE.format(
            goal=task,
            join_text=joined_text,
        )
        action_input_prompt = OPERATOR_ACTION_INPUT_PROMPT_TEMPLATE.format(
            goal=task,
            joined_text=joined_text,
            instructions=instructions,
        )

        # ========== Step 4. 并行调用模型 ==========
        async def summarize_context():
            return await asyncio.to_thread(self._private_reasoner.generate, summary_prompt)

        async def generate_action_input():
            return await asyncio.to_thread(self._private_reasoner.generate, action_input_prompt)

        summary_result, action_result = await asyncio.gather(
            summarize_context(), generate_action_input()
        )

        # ========== Step 5. 尝试解析 action_result ==========
        import json
        try:
            action_input = json.loads(action_result)
        except Exception:
            # 若不是JSON，构造一个容错结构
            action_input = {
                "instruction": str(action_result).strip(),
                "input_data": {}
            }

        # ========== Step 6. 构建上下文 ==========
        combined_context = (
            f"【任务目标】{task}\n"
            f"【上下文摘要】{summary_result}\n"
            f"【第一个Action输入】{action_input}\n"
            f"【原始上下文】\n{joined_text}"
        )

        payload = {
            "task_goal": task,
            "task_context": summary_result,
            "action_input": action_input,
            "summary": summary_result,
            "combined_context": combined_context,
            "timestamp": int(time.time() * 1000),
        }

        msg = WorkflowMessage(
            payload=payload,
            job_id=job.id,
            timestamp=int(time.time() * 1000),
        )

        print(f"[Operator] ✅ summarize_messages: 模型摘要与首Action输入生成完成 ({len(all_texts)} 段上下文)")
        return msg


    def conclude(self, results):
        response = self._private_reasoner.operator_conclude(results)
        return response
