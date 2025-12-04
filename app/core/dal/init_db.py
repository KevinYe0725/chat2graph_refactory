from app.core.dal.database import Do, engine
from app.core.dal.do.artifact_do import ArtifactDo
from app.core.dal.do.file_descriptor_do import FileDescriptorDo
from app.core.dal.do.graph_db_do import GraphDbDo
from app.core.dal.do.job_do import JobDo
from app.core.dal.do.knowledge_do import KnowledgeBaseDo
from app.core.dal.do.message_do import MessageDo
from app.core.dal.do.session_do import SessionDo
from app.core.dal.do.vmc.action_execution_do import ActionExecutionDo
from app.core.dal.do.vmc.operator_execution_do import OperatorExecutionDo
from app.core.dal.do.vmc.workflow_execution_do import WorkflowExecutionDo


def init_db() -> None:
    """Initialize database tables."""
    # Do.metadata.drop_all(bind=engine)

    # create tables in order

    Do.metadata.create_all(
        bind=engine,
        tables=[
            GraphDbDo.__table__,
            FileDescriptorDo.__table__,
            KnowledgeBaseDo.__table__,
            SessionDo.__table__,
            JobDo.__table__,
            MessageDo.__table__,
            ArtifactDo.__table__,
            ActionExecutionDo.__table__,
            OperatorExecutionDo.__table__,
            WorkflowExecutionDo.__table__,
        ],
        checkfirst=True,
    )

    Do.metadata.create_all(bind=engine)
