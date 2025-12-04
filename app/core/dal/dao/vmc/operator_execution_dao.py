from typing import List, Optional

from numpy.core.records import record
from sqlalchemy.orm import Session

from app.core.central_orchestrator.version_management_center.record import OperatorExecutionRecord
from app.core.dal.dao.dao import Dao
from app.core.dal.dao.vmc.action_execution_dao import ActionExecutionDao
from app.core.dal.do.vmc.operator_execution_do import OperatorExecutionDo


class OperatorExecutionDao(Dao[OperatorExecutionDo]):
    """DAO for OperatorExecutionDo"""

    def __init__(self, session: Session):
        super().__init__(OperatorExecutionDo, session)
        self.action_dao:ActionExecutionDao = ActionExecutionDao.instance

    def to_record(self, do: OperatorExecutionDo) -> OperatorExecutionRecord:
        return OperatorExecutionRecord(
            record_id=do.id,
            operator_id=do.operator_id,
            workflow_version_id=do.workflow_version_id,
            expert_name=do.expert_name,
            timestamp=do.timestamp,
            job_input=do.job_input or {},
            previous_operator_outputs=do.previous_operator_outputs or [],
            previous_expert_outputs=do.previous_expert_outputs or [],
            lesson=do.lesson,
            operator_config=do.operator_config or {},
            output_message=do.output_message,
            evaluation=do.evaluation,
            action_records=[self.action_dao.get_record(record_id=record_id) for record_id in do.action_record_ids],  # 由 Action DAO 注入
            parent_span_id=do.parent_span_id,
            operator_name=do.operator_name,
            latency_ms=do.latency_ms,
            trace_id=do.trace_id,
            span_id=do.span_id,
            metadata=do.metadata or {},
        )

    def from_record(self, record: OperatorExecutionRecord) -> dict:
        return {
            "id": record.record_id,
            "operator_id": record.operator_id,
            "workflow_version_id": record.workflow_version_id,
            "expert_name": record.expert_name,
            "job_input": record.job_input,
            "previous_operator_outputs": record.previous_operator_outputs,
            "previous_expert_outputs": record.previous_expert_outputs,
            "lesson": record.lesson,
            "operator_config": record.operator_config,
            "output_message": record.output_message,
            "evaluation": record.evaluation,
            "action_record_ids": [a.record_id for a in record.action_records],
            "trace_id": record.trace_id,
            "span_id": record.span_id,
            "parent_span_id": record.parent_span_id,
            "operator_name": record.operator_name,
            "latency_ms": record.latency_ms,
            "metadata": record.metadata,
        }

    def save_record(self, record: OperatorExecutionRecord) -> OperatorExecutionDo:
        data = self.from_record(record)
        try:
            self.get_by_id(record.record_id)
            return self.update(**data)
        except ValueError:
            return self.create(**data)

    def get_record(self, record_id: str) -> Optional[OperatorExecutionRecord]:
        """Get a single operator execution record by its primary id."""
        obj = self.get_by_id(record_id)
        return self.to_record(obj) if obj else None

    def batch_get_records(self, record_ids: List[str]) -> List[OperatorExecutionRecord]:
        """Batch fetch operator execution records by a list of ids."""
        if not record_ids:
            return []
        objs = (
            self.session.query(OperatorExecutionDo)
            .filter(OperatorExecutionDo.id.in_(record_ids))
            .all()
        )
        return [self.to_record(o) for o in objs]

    def find_by_operator_span(self, operator_id: str, span_id: str) -> Optional[OperatorExecutionRecord]:
        """Find an operator execution record by operator_id + span_id (for reverse lookup from action)."""
        obj = (
            self.session.query(OperatorExecutionDo)
            .filter_by(operator_id=operator_id, span_id=span_id)
            .first()
        )
        return self.to_record(obj) if obj else None

    # Query Helpers
    def list_by_workflow_version(self, version: str) -> List[OperatorExecutionRecord]:
        results = self.list(workflow_version_id=version)
        return [self.to_record(do) for do in results]

    def list_by_trace_id(self, trace_id: str) -> List[OperatorExecutionRecord]:
        results = self.list(trace_id=trace_id)
        return [self.to_record(do) for do in results]