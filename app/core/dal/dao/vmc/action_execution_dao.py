from typing import List, Optional
from sqlalchemy.orm import Session

from app.core.central_orchestrator.version_management_center.record import ActionExecutionRecord
from app.core.dal.dao.dao import Dao
from app.core.dal.do.vmc.action_execution_do import ActionExecutionDo


class ActionExecutionDao(Dao[ActionExecutionDo]):
    """DAO for ActionExecutionDo"""

    def __init__(self, session: Session):
        super().__init__(ActionExecutionDo, session)

    # ===========================
    # Record ↔ DO 转换
    # ===========================

    def to_record(self, do: ActionExecutionDo) -> ActionExecutionRecord:
        return ActionExecutionRecord(
            record_id=do.id,
            action_id=do.action_id,
            operator_id=do.operator_id,
            workflow_version_id=do.workflow_version_id,
            expert_name=do.expert_name,
            timestamp=do.timestamp,
            action_type=do.action_type,
            instruction=do.instruction,
            structured_input=do.structured_input,
            model_name=do.model_name,
            temperature=do.temperature,
            top_p=do.top_p,
            max_tokens=do.max_tokens,
            raw_output_text=do.raw_output_text,
            structured_output=do.structured_output,
            error=do.error,
            input_tokens=do.input_tokens,
            output_tokens=do.output_tokens,
            total_tokens=do.total_tokens,
            latency_ms=do.latency_ms,
            model_latency_ms=do.model_latency_ms,
            score=do.score,
            feedback=do.feedback,
            reasoning_content=do.reasoning_content,
            trace_id=do.trace_id,
            span_id=do.span_id,
            parent_span_id=do.parent_span_id,
            metadata=do.metadata or {},
        )

    def from_record(self, record: ActionExecutionRecord) -> dict:
        return {
            "id": record.record_id,
            "action_id": record.action_id,
            "operator_id": record.operator_id,
            "workflow_version_id": record.workflow_version_id,
            "expert_name": record.expert_name,
            "action_type": record.action_type,
            "instruction": record.instruction,
            "structured_input": record.structured_input,
            "model_name": record.model_name,
            "temperature": record.temperature,
            "top_p": record.top_p,
            "max_tokens": record.max_tokens,
            "raw_output_text": record.raw_output_text,
            "structured_output": record.structured_output,
            "error": record.error,
            "input_tokens": record.input_tokens,
            "output_tokens": record.output_tokens,
            "total_tokens": record.total_tokens,
            "latency_ms": record.latency_ms,
            "model_latency_ms": record.model_latency_ms,
            "score": record.score,
            "feedback": record.feedback,
            "reasoning_content": record.reasoning_content,
            "trace_id": record.trace_id,
            "span_id": record.span_id,
            "parent_span_id": record.parent_span_id,
            "metadata": record.metadata,
        }

    # ===========================
    # Persist Record
    # ===========================
    def save_record(self, record: ActionExecutionRecord) -> ActionExecutionDo:
        data = self.from_record(record)
        try:
            self.get_by_id(record.record_id)  # try update
            return self.update(**data)
        except ValueError:
            return self.create(**data)

    # ===========================
    # Query Helpers
    # ===========================

    def list_by_operator(self, operator_id: str) -> List[ActionExecutionRecord]:
        results = self.list(operator_id=operator_id)
        return [self.to_record(do) for do in results]

    def list_by_workflow_version(self, version: str) -> List[ActionExecutionRecord]:
        results = self.list(workflow_version_id=version)
        return [self.to_record(do) for do in results]

    def list_by_trace_id(self, trace_id: str) -> List[ActionExecutionRecord]:
        results = self.list(trace_id=trace_id)
        return [self.to_record(do) for do in results]

    def get_record(self, record_id: str) -> Optional[ActionExecutionRecord]:
        """Get a single action execution record by primary id."""
        obj = self.get_by_id(record_id)
        return self.to_record(obj) if obj else None

    def batch_get_records(self, record_ids: List[str]) -> List[ActionExecutionRecord]:
        """Batch fetch action execution records by a list of ids."""
        if not record_ids:
            return []
        objs = (
            self.session.query(ActionExecutionDo)
            .filter(ActionExecutionDo.id.in_(record_ids))
            .all()
        )
        return [self.to_record(o) for o in objs]

    def find_by_operator_span(self, operator_id: str, span_id: str) -> Optional[ActionExecutionRecord]:
        """Find an action execution record by operator_id + parent_span_id."""
        obj = (
            self.session.query(ActionExecutionDo)
            .filter_by(operator_id=operator_id, parent_span_id=span_id)
            .first()
        )
        return self.to_record(obj) if obj else None