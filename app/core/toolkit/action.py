from dataclasses import dataclass, field
from typing import List
from app.core.toolkit.tool import Tool


@dataclass
class Action:
    """The action in the toolkit.

    Attributes:
        id (str): The unique identifier of the action.
        name (str): The name of the action.
        description (str): The description of the action.
        next_action_ids (List[str]): The ids of the next actions in the toolkit.
        tools (List[Tool]): The tools can be used in the action.
    """

    id: str
    name: str
    description: str
    next_action_ids: List[str] = field(default_factory=list)
    tools: List[Tool] = field(default_factory=list)
    model_name: str = "model-0"
    model_type: str = "API"

    def copy(self) -> "Action":
        """Create a copy of the action."""
        return Action(
            id=self.id,
            name=self.name,
            description=self.description,
            next_action_ids=list(self.next_action_ids),
            tools=[tool.copy() for tool in self.tools],
        )

    # async def run(self, inputs: Dict[str, Any]) -> ModelMessage:
    #     # === 1) 准备模型服务 ===
    #     model_service: ModelService = ModelServiceFactory.get_model_for_action(
    #         self.model_name,
    #     )
    #     sys_prompt = ""
    #
    #     # === 2) 解析输入 ===
    #     task: str = inputs["task"]
    #     message_obj: WorkflowMessage = inputs["message"]
    #     job = inputs["job"]
    #     payload = message_obj.get_payload()
    #     if isinstance(payload, str):
    #         payload = json.loads(payload)
    #
    #     # 将本 action 的任务写入 payload
    #     payload["action_input"]["instruction"] = task
    #     message_str = json.dumps(payload, ensure_ascii=False)
    #
    #     init_message = ModelMessage(
    #         payload=message_str,
    #         job_id=inputs["job_id"],
    #         source_type=MessageSourceType.THINKER,
    #         step=1,
    #     )
    #     messages: List[ModelMessage] = [init_message]
    #
    #     # === 3) 获取执行上下文 ===
    #
    #     expert_name: str = job.assigned_expert_name
    #     ctx = execution_context_service.get_execution_context(expert_name)
    #
    #     action_id = self.id
    #     action_span_id = ctx.new_action_span(action_id)
    #     parent_span_id = ctx.get_action_parent_span()
    #
    #     # === 4) 调用模型 ===
    #     start_time = time.time()
    #     result: ModelMessage = await model_service.generate(
    #         sys_prompt=sys_prompt,
    #         messages=messages,
    #         tools=self.tools,
    #     )
    #     end_time = time.time()
    #
    #     # === 5) 提取模型输出 ===
    #     payload_str: str = result.get_payload()
    #     payload_json = json.loads(payload_str)
    #
    #     output_text = payload_json.get("text")
    #     stats = payload_json.get("tokens", {})
    #     input_tokens = stats.get("input", 0)
    #     output_tokens = stats.get("output", 0)
    #     total_tokens = stats.get("total", input_tokens + output_tokens)
    #
    #     latency_ms = (end_time - start_time) * 1000
    #
    #     # === 6) 构建 ActionExecutionRecord ===
    #     record = ActionExecutionRecord(
    #         action_id=action_id,
    #         operator_id=inputs["operator_id"],
    #         workflow_version_id=ctx.workflow_version_id,
    #         expert_name=expert_name,
    #
    #         instruction=self.description,
    #         structured_input=inputs.get("action_input", {}),
    #
    #         raw_output_text=output_text,
    #         structured_output=output_text,
    #         error=None,
    #
    #         input_tokens=input_tokens,
    #         output_tokens=output_tokens,
    #         total_tokens=total_tokens,
    #         latency_ms=latency_ms,
    #
    #         trace_id=ctx.trace_id,
    #         span_id=action_span_id,
    #         parent_span_id=parent_span_id,
    #     )
    #
    #     # === 7) 发送记录到 VMC ===
    #     vmc.log_action(record)
    #
    #     return result

    def to_dict(self) -> dict:
        """Convert the action to a dict."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "next_action_ids": list(self.next_action_ids),
            "tools" : [tool.to_dict() for tool in self.tools],
            "model_type": self.model_type,
            "model_name": self.model_name,

        }