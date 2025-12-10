from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, List, Optional, cast

from app.core.model.artifact import Artifact, ContentType
from app.core.model.job import Job
from app.core.model.message import AgentMessage, GraphMessage, MessageType, WorkflowMessage
from app.core.reasoner.reasoner import Reasoner
from app.core.service.artifact_service import ArtifactService
from app.core.service.job_service import JobService
from app.core.service.message_service import MessageService
from app.core.workflow.operator import Operator
from app.core.workflow.workflow import Workflow
from app.plugin.dbgpt.dbgpt_workflow import DbgptWorkflow


@dataclass
class Profile:

    name: str
    description: str = ""


@dataclass
class AgentConfig:
    profile: Profile
    reasoner: Reasoner
    workflow: Workflow


class Agent(ABC):
    def __init__(
        self,
        agent_config: AgentConfig,
        id: Optional[str] = None,
    ):
        self._id: str = id or agent_config.profile.name + "_id"
        self._profile: Profile = agent_config.profile
        self._workflow: Workflow = agent_config.workflow
        self._reasoner: Reasoner = agent_config.reasoner
        self._new_workflow: Optional[Workflow] = None

        self._message_service: MessageService = MessageService.instance
        self._job_service: JobService = JobService.instance
        self._artifact_service: ArtifactService = ArtifactService.instance

    def get_id(self) -> str:
        return self._id

    def get_profile(self) -> Profile:
        return self._profile

    @abstractmethod
    def execute(self, agent_message: AgentMessage, retry_count: int = 0) -> Any:
        """"""
    def save_output_agent_message(
        self, job: Job, workflow_message: WorkflowMessage, lesson: Optional[str] = None
    ) -> AgentMessage:
        artifact_ids: List[str] = []
        graph_artifacts: List[Artifact] = self._artifact_service.get_artifacts_by_job_id_and_type(
            job_id=job.id,
            content_type=ContentType.GRAPH,
        )
        for graph_artifact in graph_artifacts:
            graph_message = GraphMessage(
                payload=cast(dict, graph_artifact.content),
                job_id=graph_artifact.source_reference.job_id,
                session_id=graph_artifact.source_reference.session_id,
                metadata={"graph_description": graph_artifact.metadata.description},
            )
            graph_message_id = self._message_service.save_message(message=graph_message).get_id()
            artifact_ids.append(graph_message_id)

        self._artifact_service.delete_artifacts_by_job_id(job_id=job.id)

        try:
            existed_expert_message: AgentMessage = cast(
                AgentMessage,
                self._message_service.get_message_by_job_id(
                    job_id=job.id, message_type=MessageType.AGENT_MESSAGE
                )[0],
            )
            expert_message: AgentMessage = AgentMessage(
                id=existed_expert_message.get_id(),
                job_id=job.id,
                payload=workflow_message.scratchpad,
                workflow_messages=[workflow_message],
                artifact_ids=artifact_ids,
                timestamp=existed_expert_message.get_timestamp(),
                lesson=lesson or existed_expert_message.get_lesson(),
            )
        except Exception:
            expert_message = AgentMessage(
                job_id=job.id,
                payload=workflow_message.scratchpad,
                workflow_messages=[workflow_message],
                artifact_ids=artifact_ids,
                lesson=lesson,
            )
        self._message_service.save_message(message=expert_message)

        return expert_message

    def get_all_operators(self) -> List[Operator]:
         return self._workflow.get_operators()