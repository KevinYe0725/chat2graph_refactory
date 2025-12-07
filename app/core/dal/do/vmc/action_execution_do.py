from uuid import uuid4
from sqlalchemy import Column, String, Float, Text, Integer, JSON, DateTime
from sqlalchemy.sql import func

from app.core.dal.database import Do


class ActionExecutionDo(Do):
    """Action-level execution record (persisted)."""

    __tablename__ = "action_execution"

    # Primary Key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))

    # Core identifiers
    action_id = Column(String(128), nullable=False)
    operator_id = Column(String(128), nullable=False)
    workflow_version_id = Column(String(128), nullable=False)
    expert_name = Column(String(128), nullable=True)

    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    # Input side
    action_type = Column(String(64), nullable=True)
    instruction = Column(Text, nullable=True)
    structured_input = Column(JSON, nullable=True)

    # Model params snapshot
    model_name = Column(String(128), nullable=True)
    temperature = Column(Float, nullable=True)
    top_p = Column(Float, nullable=True)
    max_tokens = Column(Integer, nullable=True)

    # Output side
    raw_output_text = Column(Text, nullable=True)
    structured_output = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)

    # Performance metrics
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    latency_ms = Column(Float, nullable=True)
    model_latency_ms = Column(Float, nullable=True)

    # RLHF supervision
    score = Column(Float, nullable=True)
    feedback = Column(Text, nullable=True)
    reasoning_content = Column(Text, nullable=True)

    # trace info
    trace_id = Column(String(128), nullable=True)
    span_id = Column(String(128), nullable=True)
    parent_span_id = Column(String(128), nullable=True)

    # extra metadata
