from uuid import uuid4
from sqlalchemy import Column, String, Float, Text, JSON, DateTime
from sqlalchemy.sql import func

from app.core.dal.database import Do


class OperatorExecutionDo(Do):
    """Operator-level execution record."""

    __tablename__ = "operator_execution"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))

    operator_id = Column(String(128), nullable=False)
    workflow_version_id = Column(String(128), nullable=False)
    expert_name = Column(String(128), nullable=True)

    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    # Inputs
    job_input = Column(JSON, nullable=True)
    previous_operator_outputs = Column(JSON, nullable=True)
    previous_expert_outputs = Column(JSON, nullable=True)
    lesson = Column(Text, nullable=True)

    # Operator config snapshot
    operator_config = Column(JSON, nullable=True)

    # Operator output
    output_message = Column(JSON, nullable=True)
    evaluation = Column(Text, nullable=True)

    # Action record ids (FK list)
    action_record_ids = Column(JSON, nullable=True)

    # trace info
    trace_id = Column(String(128), nullable=True)
    span_id = Column(String(128), nullable=True)
    parent_span_id = Column(String(128), nullable=True)

    # Operator info
    operator_name = Column(String(128), nullable=True)

    # Overall performance
    latency_ms = Column(Float, nullable=True)

    metadata = Column(JSON, nullable=True)