from concurrent.futures import Future, ThreadPoolExecutor
import json
import time
from time import sleep
from typing import Dict, List, Optional, Set, Union

import networkx as nx  # type: ignore

from app.core.agent.agent import Agent, AgentConfig
from app.core.agent.builtin_leader_state import BuiltinLeaderState
from app.core.agent.expert import Expert
from app.core.agent.leader_state import LeaderState
from app.core.central_orchestrator.central_orchestrator import CentralOrchestrator
from app.core.common.async_func import run_in_thread
from app.core.common.system_env import SystemEnv
from app.core.common.type import ChatMessageRole, JobStatus, WorkflowStatus
from app.core.common.util import parse_jsons
from app.core.model.job import Job, SubJob
from app.core.model.job_graph import JobGraph
from app.core.model.message import AgentMessage, HybridMessage, TextMessage, WorkflowMessage
from app.core.prompt.job_decomposition import (
    JOB_DECOMPOSITION_OUTPUT_SCHEMA,
    TASK_AND_PROFILE_PROMPT,
    subjob_required_keys,
)


class Leader(Agent):
    def __init__(
        self,
        agent_config: AgentConfig,
        id: Optional[str] = None,
        leader_state: Optional[LeaderState] = None,
    ):
        super().__init__(agent_config=agent_config, id=id)
        self._leader_state: LeaderState = leader_state or BuiltinLeaderState()


    #分割原始任务为 任务图
    def execute(self, agent_message: AgentMessage, retry_count: int = 0) -> JobGraph:
        life_cycle: Optional[int] = None
        job_id = agent_message.get_job_id()

        try:
            job: Job = self._job_service.get_original_job(original_job_id=job_id)
            original_job_id: str = job_id
        except ValueError as e:
            job : SubJob = self._job_service.get_subjob(subjob_id=job_id)
            life_cycle = job.life_cycle
            if not job.original_job_id:
                raise ValueError("The subjob is not assigned to an original job.") from e
            original_job_id = job.original_job_id

        # check if the job is already assigned to an expert
        assigned_expert_name: Optional[str] = job.assigned_expert_name
        if assigned_expert_name:
            expert = self.state.get_expert_by_name(assigned_expert_name)
            subjob = SubJob(
                original_job_id=original_job_id,
                session_id=job.session_id,
                goal=job.goal,
                context=job.goal + "\n" + job.context,
                expert_id=expert.get_id(),
                life_cycle=life_cycle or SystemEnv.LIFE_CYCLE,
                assigned_expert_name=assigned_expert_name,
            )
            self._job_service.save_job(job=subjob)
            job_graph: JobGraph = JobGraph()
            job_graph.add_vertex(subjob.id)
            return job_graph

        expert_profiles = [e.get_profile() for e in self.state.list_experts()]
        expert_names = [p.name for p in expert_profiles]
        role_list = "\n".join(
            [
                f"Expert name: {profile.name}\nDescription: {profile.description}"
                for profile in expert_profiles
            ]
        )

        job_decomp_prompt = TASK_AND_PROFILE_PROMPT.format(task=job.goal, role_list=role_list)
        decomp_job = Job(
            id=job.id,
            session_id=job.session_id,
            goal=job.goal,
            context=job.context + f"\n\n{job_decomp_prompt}",
        )

        job_dict: Optional[Dict[str, Dict[str, str]]] = None

        try:
            workflow_message = self._workflow.execute(job=decomp_job, reasoner=self._reasoner)
            results: List[Union[Dict[str, Dict[str, str]], json.JSONDecodeError]] = parse_jsons(
                text=workflow_message.scratchpad,
                start_marker=r"^\s*<decomposition>\s*",
                end_marker="</decomposition>",
            )

            if len(results) == 0:
                raise ValueError("The job decomposition result is empty.")
            result = results[0]
            if isinstance(result, json.JSONDecodeError):
                raise result
            self._validate_job_dict(result, expert_names)
            job_dict = result

        except (ValueError, json.JSONDecodeError, Exception) as e:
            print(
                f"\033[38;5;196m[WARNING]: Initial decomposition failed or validation error: "
                f"{e}\033[0m"
            )
            if isinstance(e, ValueError | json.JSONDecodeError):
                print("\033[38;5;208m[INFO]: Retrying decomposition with lesson...\033[0m")
                lesson = (
                    "LLM output format (<decomposition> format) specification is crucial "
                    "for reliable parsing and validation. Ensure the JSON structure is correct, "
                    f"all required keys are present: {subjob_required_keys}, dependencies are "
                    f"valid task IDs, and assigned_expert is one of {expert_names}. Do not forget "
                    " <decomposition> prefix and </decomposition> suffix when you generate the "
                    "subtasks dict block in <final_output>...</final_output>.\nExpected format: "
                    f"{JOB_DECOMPOSITION_OUTPUT_SCHEMA}\nError info: " + str(e)
                )
                try:
                    workflow_message = self._workflow.execute(
                        job=decomp_job,
                        reasoner=self._reasoner,
                        lesson=lesson,
                    )
                    results = parse_jsons(
                        text=workflow_message.scratchpad,
                        start_marker=r"^\s*<decomposition>\s*",
                        end_marker="</decomposition>",
                    )
                    if len(results) == 0:
                        raise ValueError(
                            "The job decomposition result is empty after retry."
                        ) from e
                    result = results[0]
                    if isinstance(result, json.JSONDecodeError):
                        raise result from e
                    self._validate_job_dict(result, expert_names)
                    job_dict = result

                except (ValueError, json.JSONDecodeError) as retry_e:
                    self.fail_job_graph(
                        job_id=job_id,
                        error_info=(
                            f"The job `{original_job_id}` could not be decomposed correctly "
                            f"after retry. Please try again.\nError info: {retry_e}"
                        ),
                    )
                    job_dict = {}
            else:
                self.fail_job_graph(
                    job_id=job_id,
                    error_info=(
                        f"The job `{original_job_id}` could not be executed due to an "
                        f"unexpected error during leader task decomposition. Error info: {e}"
                    ),
                )
                job_dict = {}

        if not job_dict:
            current_status = self._job_service.get_job_result(job_id=job_id).status
            if current_status not in (JobStatus.FAILED, JobStatus.STOPPED):
                self.fail_job_graph(
                    job_id,
                    "Decomposition failed to produce a valid and non-empty subtask dictionary.",
                )
            return JobGraph()
        job_graph = JobGraph()
        if self._job_service.get_job_result(job_id=job_id).has_result():
            return job_graph
        temp_to_unique_id_map: Dict[str, str] = {}
        try:
            for subjob_id, subjob_dict in job_dict.items():
                expert_name = subjob_dict["assigned_expert"]
                expert = self.state.get_expert_by_name(
                    expert_name
                )
                subjob = SubJob(
                    original_job_id=original_job_id,
                    session_id=job.session_id,
                    goal=subjob_dict["goal"],
                    context=(
                        subjob_dict["context"]
                        + "\nThe completion criteria is determined: "
                        + subjob_dict["completion_criteria"]
                    ),
                    expert_id=expert.get_id(),
                    life_cycle=life_cycle or SystemEnv.LIFE_CYCLE,
                    thinking=subjob_dict["thinking"],
                    assigned_expert_name=expert_name,
                )
                temp_to_unique_id_map[subjob_id] = subjob.id

                self._job_service.save_job(job=subjob)
                job_graph.add_vertex(subjob.id)

            for subjob_id, subjob_dict in job_dict.items():
                current_unique_id = temp_to_unique_id_map[subjob_id]
                for dep_id in subjob_dict.get(
                    "dependencies", []
                ):
                    dep_unique_id = temp_to_unique_id_map[dep_id]
                    job_graph.add_edge(
                        dep_unique_id, current_unique_id
                    )
        except Exception as e:
            self.fail_job_graph(
                job_id=job_id,
                error_info=(
                    f"The job `{original_job_id}` decomposition was validated, but an error "
                    f"occurred during subjob creation or linking.\nError info: {e}"
                ),
            )
            return JobGraph()
        if not nx.is_directed_acyclic_graph(job_graph.get_graph()):
            self.fail_job_graph(
                job_id=job_id,
                error_info=(
                    f"The job `{original_job_id}` decomposition resulted in a cyclic graph, "
                    f"indicating an issue with dependency logic despite validation."
                ),
            )
            return JobGraph()

        return job_graph

    def execute_original_job(self, original_job: Job) -> None:

        # 将job状态修改成RUNNING，并且存入数据库
        original_job_result = self._job_service.get_job_result(job_id=original_job.id)
        if original_job_result.status == JobStatus.CREATED:
            original_job_result.status = JobStatus.RUNNING
            self._job_service.save_job_result(job_result=original_job_result)
        else:
            raise ValueError(
                f"Original job {original_job.id} already has a final or running status: "
                f"{original_job_result.status.value}."
            )
        #分割任务
        decomposed_job_graph: JobGraph = self.execute(
            agent_message=AgentMessage(
                job_id=original_job.id,
            )
        )
        #将任务图保存，作为一张保存好的说明书，随时可以拿出来看
        #虽然这里是使用replace函数，但是没有old graph 所以直接当作保存该graph
        self._job_service.replace_subgraph(
            original_job_id=original_job.id, new_subgraph=decomposed_job_graph
        )

        self.execute_job_graph(original_job_id=original_job.id)
    def execute_job_graph_new_version(self, original_job_id: str) -> None:
        job_graph: JobGraph = self._job_service.get_job_graph(original_job_id)
        pending_job_ids: Set[str] = set(job_graph.vertices())
        preparing_jobs:Dict[str, Future] = {}
        waiting_job_ids: Set[str] = set()
        running_jobs: Dict[str, Future] = {}
        expert_results: Dict[str, WorkflowMessage] = {}
        job_inputs: Dict[str, AgentMessage] = {}
        with ThreadPoolExecutor() as executor:
            while pending_job_ids or preparing_jobs or waiting_job_ids or running_jobs:
                ready_job_ids: Set[str] = set()
                # step1: 并行执行构建后续任务子图
                for job_id in list(pending_job_ids):
                    expert_id = self._job_service.get_subjob(job_id).expert_id
                    assert expert_id is not None, "该任务没有分配Expert"
                    expert = self.state.get_expert_by_id(expert_id)
                    preparing_jobs[job_id] = executor.submit(
                        self._expert_build_workflow, expert, AgentMessage(job_id=job_id)
                    )
                    pending_job_ids.remove(job_id)
                # step2：将构建好子图的Expert任务放入preparing_jobs中
                finished_preparing = []
                for job_id, future in preparing_jobs.items():
                    if future.done():
                        waiting_job_ids.add(job_id)
                        finished_preparing.append(job_id)

                for job_id in finished_preparing:
                    preparing_jobs.pop(job_id, None)
                # step3：遍历waiting_job_ids，将其按依赖顺序执行（前置节点全部结束即可开始），放入ready_job_ids
                for job_id in waiting_job_ids:
                    expert_id = self._job_service.get_subjob(job_id).expert_id
                    all_predecessors_complete = all(
                        pred not in waiting_job_ids and pred not in running_jobs
                        for pred in job_graph.predecessors(job_id)
                    )
                    if all_predecessors_complete:
                        job: SubJob = self._job_service.get_subjob(job_id)
                        pred_messages: List[WorkflowMessage] = [
                            expert_results[pred_id] for pred_id in job_graph.predecessors(job_id)
                        ]
                        job_inputs[job_id] = AgentMessage(
                            job_id=job_id, workflow_messages=pred_messages
                        )
                        ready_job_ids.add(job_id)

                # step4：执行ready_job_ids中的任务
                for job_id in ready_job_ids:
                    expert_id = self._job_service.get_subjob(job_id).expert_id
                    assert expert_id, "The subjob is not assigned to an expert."
                    expert = self.state.get_expert_by_id(expert_id=expert_id)

                    running_jobs[job_id] = executor.submit(
                        self._execute_job, expert, job_inputs[job_id]
                    )
                    waiting_job_ids.remove(job_id)
                if not running_jobs and pending_job_ids:
                    raise ValueError(
                        "由于job_graph产出的依赖问题，导致有些任务没有办法被执行"
                    )

                completed_job_ids = []
                for job_id, future in running_jobs.items():
                    if future.done():
                        completed_job_ids.append(job_id)
                for completed_job_id in completed_job_ids:
                    future = running_jobs[completed_job_id]
                    agent_result: AgentMessage = future.result()
                    if (
                            agent_result.get_workflow_result_message().status
                            == WorkflowStatus.INPUT_DATA_ERROR
                    ):
                        waiting_job_ids.add(completed_job_id)
                        predecessors = list(job_graph.predecessors(completed_job_id))
                        waiting_job_ids.update(predecessors)
                        if predecessors:
                            for pred_id in predecessors:
                                if pred_id in expert_results:
                                    del expert_results[pred_id]
                                    self._job_service.remove_subjob(
                                        original_job_id=completed_job_id, job_id=pred_id
                                    )
                                input_agent_message = job_inputs[pred_id]
                                lesson = agent_result.get_lesson()
                                assert lesson is not None
                                input_agent_message.lesson = lesson
                                job_inputs[pred_id] = input_agent_message
                    elif (
                            agent_result.get_workflow_result_message().status
                            == WorkflowStatus.JOB_TOO_COMPLICATED_ERROR
                    ):
                        old_job_graph: JobGraph = JobGraph()
                        old_job_graph.add_vertex(completed_job_id)
                        new_job_graqph: JobGraph = self.execute(agent_message=agent_result)
                        self._job_service.replace_subgraph(
                            original_job_id=original_job_id,
                            new_subgraph=new_job_graqph,
                            old_subgraph=old_job_graph,
                        )
                        job_graph = self._job_service.get_job_graph(original_job_id)
                        del running_jobs[completed_job_id]
                        expert_results[completed_job_id] = (
                            agent_result.get_workflow_result_message()
                        )
                        for new_subjob_id in new_job_graqph.vertices():
                            pending_job_ids.add(new_subjob_id)
                            if job_graph.predecessors(new_subjob_id):
                                pred_messages = [
                                    expert_results[pred_id]
                                    for pred_id in job_graph.predecessors(new_subjob_id)
                                ]
                                job_inputs[new_subjob_id] = AgentMessage(
                                    job_id=new_subjob_id,
                                    workflow_messages=pred_messages,
                                )
                    else:
                        expert_results[completed_job_id] = (
                            agent_result.get_workflow_result_message()
                        )

                    del running_jobs[completed_job_id]
                if not completed_job_ids and running_jobs:
                    time.sleep(0.5)


    def execute_job_graph(self, original_job_id: str) -> None:
        job_graph: JobGraph = self._job_service.get_job_graph(original_job_id)
        pending_job_ids: Set[str] = set(job_graph.vertices())
        running_jobs: Dict[str, Future] = {}
        expert_results: Dict[str, WorkflowMessage] = {}
        job_inputs: Dict[str, AgentMessage] = {}

        #使用线程池执行当前的初始化子图
        with ThreadPoolExecutor() as executor:
            while pending_job_ids or running_jobs:
                #准备好了的job
                ready_job_ids: Set[str] = set()
                #遍历pending_job_ids，找到前置节点已经全部完成的job_id加入到ready_job_ids中
                for job_id in pending_job_ids:
                    all_predecessors_completed = all(
                        pred not in pending_job_ids and pred not in running_jobs
                        for pred in job_graph.predecessors(job_id)
                    )
                    if all_predecessors_completed:
                        job: SubJob = self._job_service.get_subjob(job_id)
                        pred_messages: List[WorkflowMessage] = [
                            expert_results[pred_id] for pred_id in job_graph.predecessors(job_id)
                        ]
                        job_inputs[job.id] = AgentMessage(
                            job_id=job.id, workflow_messages=pred_messages
                        )
                        ready_job_ids.add(job_id)

                # 执行ready jobs，并且加入running_jobs
                for job_id in ready_job_ids:
                    expert_id = self._job_service.get_subjob(job_id).expert_id
                    assert expert_id, "The subjob is not assigned to an expert."
                    expert = self.state.get_expert_by_id(expert_id=expert_id)
                    running_jobs[job_id] = executor.submit(
                        self._execute_job, expert, job_inputs[job_id]
                    )
                    pending_job_ids.remove(job_id)
                if not running_jobs and pending_job_ids:
                    raise ValueError(
                        "Deadlock detected or invalid job graph: some jobs cannot be executed due "
                        "to dependencies."
                    )
                completed_job_ids = []
                for job_id, future in running_jobs.items():
                    if future.done():
                        completed_job_ids.append(job_id)
                for completed_job_id in completed_job_ids:
                    future = running_jobs[completed_job_id]
                    agent_result: AgentMessage = future.result()
                    if (
                        agent_result.get_workflow_result_message().status
                        == WorkflowStatus.INPUT_DATA_ERROR
                    ):
                        pending_job_ids.add(completed_job_id)
                        predecessors = list(job_graph.predecessors(completed_job_id))
                        pending_job_ids.update(predecessors)
                        if predecessors:
                            for pred_id in predecessors:
                                if pred_id in expert_results:
                                    del expert_results[pred_id]
                                    self._job_service.remove_subjob(
                                        original_job_id=original_job_id, job_id=pred_id
                                    )
                                input_agent_message = job_inputs[pred_id]
                                lesson = agent_result.get_lesson()
                                assert lesson is not None
                                input_agent_message.add_lesson(lesson)
                                job_inputs[pred_id] = input_agent_message

                    elif (
                        agent_result.get_workflow_result_message().status
                        == WorkflowStatus.JOB_TOO_COMPLICATED_ERROR
                    ):
                        old_job_graph: JobGraph = JobGraph()
                        old_job_graph.add_vertex(completed_job_id)
                        new_job_graqph: JobGraph = self.execute(agent_message=agent_result)
                        self._job_service.replace_subgraph(
                            original_job_id=original_job_id,
                            new_subgraph=new_job_graqph,
                            old_subgraph=old_job_graph,
                        )
                        job_graph = self._job_service.get_job_graph(original_job_id)
                        del running_jobs[completed_job_id]
                        expert_results[completed_job_id] = (
                            agent_result.get_workflow_result_message()
                        )

                        for new_subjob_id in new_job_graqph.vertices():
                            pending_job_ids.add(new_subjob_id)
                            if job_graph.predecessors(new_subjob_id):
                                pred_messages = [
                                    expert_results[pred_id]
                                    for pred_id in job_graph.predecessors(new_subjob_id)
                                ]
                                job_inputs[new_subjob_id] = AgentMessage(
                                    job_id=new_subjob_id,
                                    workflow_messages=pred_messages,
                                )

                    else:
                        expert_results[completed_job_id] = (
                            agent_result.get_workflow_result_message()
                        )

                    del running_jobs[completed_job_id]
                if not completed_job_ids and running_jobs:
                    time.sleep(0.5)

    def stop_job_graph(self, job_id: str, stop_info: str) -> None:
        try:
            original_job: Job = self._job_service.get_original_job(original_job_id=job_id)
        except ValueError as e:
            job: SubJob = self._job_service.get_subjob(subjob_id=job_id)
            if not job.original_job_id:
                raise ValueError("The subjob is not assigned to an original job.") from e
            original_job = self._job_service.get_original_job(original_job_id=job.original_job_id)
        self._save_failed_or_stopped_message(original_job=original_job, message_payload=stop_info)
        self._stop_running_subjobs(original_job_id=original_job.id)
        original_job_result = self._job_service.get_job_result(job_id=original_job.id)
        if not original_job_result.has_result():
            original_job_result.status = JobStatus.STOPPED
            self._job_service.save_job_result(job_result=original_job_result)

    def fail_job_graph(self, job_id: str, error_info: str) -> None:
        error_info += f"\n\nCheck the error details in path: '{SystemEnv.APP_ROOT}/logs/server.log'"
        job_result = self._job_service.get_job_result(job_id=job_id)

        if not job_result.has_result():
            try:
                original_job: Job = self._job_service.get_original_job(original_job_id=job_id)
            except ValueError as e:
                job: SubJob = self._job_service.get_subjob(subjob_id=job_id)
                if not job.original_job_id:
                    raise ValueError("The subjob is not assigned to an original job.") from e
                original_job = self._job_service.get_original_job(
                    original_job_id=job.original_job_id
                )
            self._save_failed_or_stopped_message(
                original_job=original_job, message_payload=error_info
            )
            job_result.status = JobStatus.FAILED
            self._job_service.save_job_result(job_result=job_result)
            self._stop_running_subjobs(original_job_id=original_job.id)
            original_job_result = self._job_service.get_job_result(job_id=original_job.id)
            original_job_result.status = JobStatus.FAILED
            self._job_service.save_job_result(job_result=original_job_result)

    def recover_original_job(self, original_job_id: str) -> None:
        original_job = self._job_service.get_original_job(original_job_id=original_job_id)
        original_job_result = self._job_service.get_job_result(job_id=original_job_id)
        if original_job_result.status == JobStatus.STOPPED:
            subjobs = self._job_service.get_subjobs(original_job_id=original_job_id)
            if len(subjobs) == 0:
                original_job_result.status = JobStatus.CREATED
                self._job_service.save_job_result(job_result=original_job_result)
                run_in_thread(self.execute_original_job, original_job=original_job)

            else:
                original_job_result.status = JobStatus.RUNNING
                self._job_service.save_job_result(job_result=original_job_result)

                for sub_job in subjobs:
                    sub_job_result = self._job_service.get_job_result(job_id=sub_job.id)
                    if sub_job_result.status == JobStatus.STOPPED:
                        sub_job_result.status = JobStatus.CREATED
                        self._job_service.save_job_result(job_result=sub_job_result)
                run_in_thread(self.execute_job_graph, original_job_id=original_job_id)

    def _stop_running_subjobs(self, original_job_id: str) -> None:
        subjob_ids = self._job_service.get_subjob_ids(original_job_id=original_job_id)
        for subjob_id in subjob_ids:
            subjob_result = self._job_service.get_job_result(job_id=subjob_id)
            if subjob_result.status == JobStatus.RUNNING:
                subjob_result.status = JobStatus.STOPPED
                self._job_service.save_job_result(job_result=subjob_result)

    def _save_failed_or_stopped_message(self, original_job: Job, message_payload: str) -> None:
        error_payload = (
            f"An error occurred during the execution of the job:\n\n{message_payload}\n\n"
            f'Please check the job `{original_job.id}` ("{original_job.goal[:10]}...") '
            "for more details. Or you can re-try to send your message."
        )
        original_job_id = original_job.id
        try:
            error_text_message: TextMessage = (
                self._message_service.get_text_message_by_job_id_and_role(
                    original_job_id, ChatMessageRole.SYSTEM
                )
            )
            error_text_message.set_payload(error_payload)
            self._message_service.save_message(message=error_text_message)
        except ValueError:
            error_text_message = TextMessage(
                payload=error_payload,
                job_id=original_job_id,
                session_id=original_job.session_id,
                assigned_expert_name=original_job.assigned_expert_name,
                role=ChatMessageRole.SYSTEM,
            )
            self._message_service.save_message(message=error_text_message)
            error_hybrid_message: HybridMessage = HybridMessage(
                instruction_message=error_text_message,
                job_id=original_job_id,
                role=ChatMessageRole.SYSTEM,
            )
            self._message_service.save_message(message=error_hybrid_message)

        # color: red
        print(f"\033[38;5;196m[ERROR]: {error_payload}\033[0m")

    def _expert_build_workflow(self, expert: Expert, agent_message: AgentMessage) -> None:
        expert.execute_new_version(agent_message=agent_message)

    def _execute_job(self, expert: Expert, agent_message: AgentMessage) -> AgentMessage:
        #执行expert 返回Expert的结果
        agent_result_message: AgentMessage = expert.execute(agent_message=agent_message)

        #获取流水线结果
        workflow_result: WorkflowMessage = agent_result_message.get_workflow_result_message()

        #判定该Expert的流水线结果，然后进行下一步判定和后续操作
        if workflow_result.status == WorkflowStatus.SUCCESS:
            return agent_result_message
        if workflow_result.status == WorkflowStatus.EXECUTION_ERROR:
            self.fail_job_graph(
                job_id=agent_message.get_job_id(),
                error_info=agent_result_message.get_lesson() or "Error info was missing.",
            )
            return agent_result_message
        if workflow_result.status == WorkflowStatus.INPUT_DATA_ERROR:
            return agent_result_message
        if workflow_result.status == WorkflowStatus.JOB_TOO_COMPLICATED_ERROR:
            subjob: SubJob = self._job_service.get_subjob(subjob_id=agent_message.get_job_id())
            subjob.life_cycle -= 1
            subjob.is_legacy = True
            self._job_service.save_job(job=subjob)
            if subjob.life_cycle == 0:
                raise ValueError(
                    f"Job {subjob.id} runs out of life cycle. "
                    f"(initial life cycle: {SystemEnv.LIFE_CYCLE})"
                )

            replaced_job_graph: JobGraph = JobGraph()
            replaced_job_graph.add_vertex(subjob.id)
            new_job_graqph: JobGraph = self.execute(agent_message=agent_result_message)
            self._job_service.replace_subgraph(
                original_job_id=subjob.id,
                new_subgraph=new_job_graqph,
                old_subgraph=replaced_job_graph,
            )

        raise ValueError(
            f"Job {agent_message.get_job_id()} failed with an unexpected status: "
            f"{workflow_result.status.value}. Please check the job graph status."
        )

    def _validate_job_dict(
        self, job_dict: Dict[str, Dict[str, str]], expert_names: List[str]
    ) -> None:
        if not isinstance(job_dict, dict):
            raise ValueError("Decomposition result must be a dictionary.")

        if not job_dict:
            raise ValueError("Decomposition result dictionary cannot be empty.")

        all_task_ids = set(job_dict.keys())

        for task_id, task_data in job_dict.items():
            if not isinstance(task_data, dict):
                raise ValueError(f"Task '{task_id}' data must be a dictionary.")

            missing_keys = subjob_required_keys - set(task_data.keys())
            if missing_keys:
                raise ValueError(f"Task '{task_id}' is missing required keys: {missing_keys}")

            for key_to_convert in ["goal", "context", "completion_criteria", "thinking"]:
                if key_to_convert in task_data:
                    if isinstance(task_data[key_to_convert], list):
                        task_data[key_to_convert] = "\n".join(map(str, task_data[key_to_convert]))
                    elif isinstance(task_data[key_to_convert], dict):
                        task_data[key_to_convert] = json.dumps(task_data[key_to_convert])

            for key in ["goal", "context", "completion_criteria", "assigned_expert", "thinking"]:
                if not isinstance(task_data[key], str):
                    raise ValueError(f"Task '{task_id}' key '{key}' must be a string.")

            if not isinstance(task_data["dependencies"], list):
                raise ValueError(f"Task '{task_id}' key 'dependencies' must be a list.")

            for dep_id in task_data["dependencies"]:
                if dep_id not in all_task_ids:
                    raise ValueError(
                        f"Task '{task_id}' has an invalid dependency: '{dep_id}' does not exist."
                    )
            expert_name = task_data["assigned_expert"]
            if expert_name not in expert_names:
                raise ValueError(
                    f"Task '{task_id}' assigned expert '{expert_name}' not found "
                    f"in available experts: {expert_names}"
                )

            if not task_data["thinking"].strip():
                print(
                    f"\033[38;5;208m[WARNING]: Task '{task_id}' has empty 'thinking' field.\033[0m"
                )

    @property
    def state(self) -> LeaderState:
        return self._leader_state
