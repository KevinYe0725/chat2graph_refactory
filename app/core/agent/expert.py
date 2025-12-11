import json
import traceback
from typing import List, cast, Optional, Union, Dict, Any

from app.core.workflow.operator_config import OperatorConfig

from app.core.central_orchestrator.central_orchestrator import CentralOrchestrator
from app.plugin.dbgpt.dbgpt_workflow import DbgptWorkflow

from app.core.workflow.dynamic_workflow_parser import WorkflowParser
from app.core.workflow.workflow import Workflow

from app.core.common.util import parse_jsons


from app.core.agent.agent import Agent
from app.core.common.system_env import SystemEnv
from app.core.common.type import JobStatus, WorkflowStatus
from app.core.model.job import SubJob, Job
from app.core.model.message import AgentMessage, MessageType, WorkflowMessage
from app.core.prompt.dynamic_workflow import DYNAMIC_WORKFLOW_PROMPT
from app.core.service.operator_service import OperatorService


class Expert(Agent):
    #Expert执行自己的子任务 Point1 —— Fuck_Start
    #传入Agent的消息，返回自己的消息
    def execute_new_version(self, agent_message: AgentMessage, retry_count: int = 0):
        life_cycle: Optional[int] = None
        job_id = agent_message.get_job_id()
        job: Job = self._job_service.get_original_job(original_job_id=job_id)
        assert job is not None
        operator_service: OperatorService = OperatorService.instance
        rec_operators: List[OperatorConfig] = operator_service.get_operator_for_agent(agent=self)
        operator_list  = "\n".join(
                [
                    f"operator_name: {rec_operator.name}\ninstruction: {rec_operator.instruction}\n"
                    for rec_operator in rec_operators
                ]
        )
        dynamic_workflow_prompt = DYNAMIC_WORKFLOW_PROMPT.format(operator_list=operator_list,goal = job.goal)
        dynamic_workflow_job = Job(
            id=job.id,
            session_id=job.session_id,
            goal=job.goal,
            context=job.context + f"\n\n{dynamic_workflow_prompt}",
        )
        workflow_message = self._workflow.execute(job=dynamic_workflow_job, reasoner=self._reasoner)
        results: List[Union[Dict[str, Any], json.JSONDecodeError]] = parse_jsons(
            text=workflow_message.scratchpad,
            start_marker=r"^\s*<decomposition>\s*",
            end_marker="</decomposition>",
        )
        if len(results) == 0:
            raise ValueError("The job decomposition result is empty.")
        result = results[0]
        if isinstance(result, json.JSONDecodeError):
            raise result
        dynamic_workflow_dict = result
        workflow_parser: WorkflowParser = WorkflowParser()
        answer_dict = workflow_parser.parse_dynamic_workflow(raw=dynamic_workflow_dict)
        self._new_workflow = DbgptWorkflow(operator_graph=answer_dict["graph"],evaluator=answer_dict["evaluator"],operator_task_dict=answer_dict["operator_task_dict"])
        central_orchestrator = CentralOrchestrator.instance
        central_orchestrator.register_workflow(workflow=self._new_workflow,expert_name=self._profile.name)


    def execute(self, agent_message: AgentMessage, retry_count: int = 0) -> AgentMessage:
        job_id = agent_message.get_job_id()
        #从数据库中获取到自己任务的说明书
        job: SubJob = self._job_service.get_subjob(subjob_id=job_id)
        job_result = self._job_service.get_job_result(job_id=job.id)
        #该子任务已经有了结果🤔
        # 为什么？🧐
        if job_result.has_result():
            if job_result.status == JobStatus.FINISHED:
                print(
                    f"\033[38;5;46m[Success]: Job {job.id} already completed successfully.\033[0m"
                )
                return cast(
                    AgentMessage,
                    self._message_service.get_message_by_job_id(
                        job_id=job.id,
                        message_type=MessageType.AGENT_MESSAGE,
                    )[0],
                )
            print(
                f"\033[38;5;208m[Warning]: Job {job.id} already has a final status: "
                f"{job_result.status.value}.\033[0m"
            )
            if self._new_workflow.evaluator:
                return self.save_output_agent_message(
                    job=job,
                    workflow_message=WorkflowMessage(
                        payload={
                            "scratchpad": f"Job {job.id} already has a final status: "
                            f"{job_result.status.value}.",
                            "evaluation": "No further execution needed.",
                            "lesson": "",  # no lesson to add since it already has a final status
                        },
                        job_id=job.id,
                    ),
                )
            return self.save_output_agent_message(
                job=job,
                workflow_message=WorkflowMessage(
                    payload={
                        "scratchpad": f"Job {job.id} already has a final status: "
                        f"{job_result.status.value}.",
                    },
                    job_id=job.id,
                ),
            )
        job_result.status = JobStatus.RUNNING
        self._job_service.save_job_result(job_result=job_result)
        #获取之前Agent的流水线消息
        workflow_messages: List[WorkflowMessage] = agent_message.get_workflow_messages()
        try:
            #将之前的流水线信息放入当前的流水线，进行下一层的执行
            workflow_message: WorkflowMessage = self._new_workflow.execute(
                job=job,
                reasoner=self._reasoner,
                workflow_messages=workflow_messages,
                lesson=agent_message.get_lesson(),
            )
            central_orchestrator: CentralOrchestrator = CentralOrchestrator.instance
            central_orchestrator.wait_for_continue()
        except Exception as e:
            workflow_message = WorkflowMessage(
                payload={
                    "scratchpad": f"The current job {job.id} failed: "
                    f"{str(e)}\n{traceback.format_exc()}\n",
                    "status": WorkflowStatus.EXECUTION_ERROR,
                    "evaluation": f"There occurs some errors during the execution: {str(e)}",
                    "lesson": "",
                },
            )

        self._message_service.save_message(message=workflow_message)

        if workflow_message.status == WorkflowStatus.SUCCESS:
            expert_message = self.save_output_agent_message(
                job=job, workflow_message=workflow_message
            )
            job_result = self._job_service.get_job_result(job_id=job.id)
            if not job_result.has_result():
                job_result.status = JobStatus.FINISHED
                self._job_service.save_job_result(job_result=job_result)

                print(f"\033[38;5;46m[Success]: Job {job.id} completed successfully.\033[0m")

            return expert_message
        if workflow_message.status == WorkflowStatus.EXECUTION_ERROR:
            print(f"\033[38;5;208m[EXECUTION_ERROR]: Job {job.id} failed.\033[0m")
            print(f"\033[38;5;208mEvaluation: {workflow_message.evaluation}\033[0m")
            print(f"\033[38;5;208mLesson: {workflow_message.lesson}\033[0m")
            lesson = workflow_message.evaluation + "\n" + workflow_message.lesson
            agent_message.add_lesson(lesson)
            max_retry_count = SystemEnv.MAX_RETRY_COUNT
            if retry_count >= max_retry_count:
                expert_message = self.save_output_agent_message(
                    job=job, workflow_message=workflow_message, lesson=lesson
                )
                return expert_message
            return self.execute(agent_message=agent_message, retry_count=retry_count + 1)
        if workflow_message.status == WorkflowStatus.INPUT_DATA_ERROR:
            print(f"\033[38;5;208m[INPUT_DATA_ERROR]: Job {job.id} failed.\033[0m")
            print(f"\033[38;5;208mEvaluation: {workflow_message.evaluation}\033[0m")
            print(f"\033[38;5;208mLesson: {workflow_message.lesson}\033[0m")
            lesson = "The output data is not valid"
            expert_message = self.save_output_agent_message(
                job=job, workflow_message=workflow_message, lesson=lesson
            )

            return expert_message
        if workflow_message.status == WorkflowStatus.JOB_TOO_COMPLICATED_ERROR:
            # color: orange
            print(f"\033[38;5;208m[JOB_TOO_COMPLICATED_ERROR]: Job {job.id} failed.\033[0m")
            print(f"\033[38;5;208mEvaluation: {workflow_message.evaluation}\033[0m")
            print(f"\033[38;5;208mLesson: {workflow_message.lesson}\033[0m")
            lesson = "The job is too complicated to be executed by the expert"
            expert_message = self.save_output_agent_message(
                job=job, workflow_message=workflow_message, lesson=lesson
            )

            return expert_message
        raise Exception("The workflow status is not defined.")

