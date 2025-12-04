from uuid import uuid4
from sqlalchemy import Column, String, JSON, DateTime
from sqlalchemy.sql import func

from app.core.dal.database import Do


class WorkflowExecutionDo(Do):
    """Workflow-level execution record."""

    __tablename__ = "workflow_execution"

    workflow_version_id = Column(String(128), primary_key=True)

    trace_id = Column(String(128), nullable=False)
    span_id = Column(String(128), nullable=False)
    parent_span_id = Column(String(128), nullable=True)  # always root = None

    expert_name = Column(String(128), nullable=True)

    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    # list of OperatorExecutionDo ids
    operator_record_ids = Column(JSON, nullable=True)

    metadata = Column(JSON, nullable=True)