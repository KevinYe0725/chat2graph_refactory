from typing import Optional, List
from sqlalchemy.orm import Session

from app.core.central_orchestrator.version_management_center.record import WorkflowExecutionRecord
from app.core.dal.dao.dao import Dao
from app.core.dal.dao.vmc.operator_execution_dao import OperatorExecutionDao
from app.core.dal.do.vmc.workflow_execution_do import WorkflowExecutionDo


class WorkflowExecutionDao(Dao[WorkflowExecutionDo]):
    """DAO for WorkflowExecutionDo"""

    def __init__(self, session: Session):
        super().__init__(WorkflowExecutionDo, session)
        self.operator_dao = OperatorExecutionDao(session)

    def to_record(self, do: WorkflowExecutionDo) -> WorkflowExecutionRecord:
        return WorkflowExecutionRecord(
            workflow_version_id=do.workflow_version_id,
            expert_name=do.expert_name,
            timestamp=do.timestamp,
            trace_id=do.trace_id,
            span_id=do.span_id,
            operator_records=[self.operator_dao.get_record(operator_id)
                              for operator_id in do.operator_record_ids
                             ] , # operator DAO 将填充
            metadata=do.metadata or {},
        )

    def from_record(self, record: WorkflowExecutionRecord) -> dict:
        return {
            "workflow_version_id": record.workflow_version_id,
            "trace_id": record.trace_id,
            "span_id": record.span_id,
            "parent_span_id": None,
            "expert_name": record.expert_name,
            "operator_record_ids": [op.record_id for op in record.operator_records],
            "metadata": record.metadata,
        }

    def save_record(self, record: WorkflowExecutionRecord) -> WorkflowExecutionDo:
        data = self.from_record(record)
        try:
            self.get_by_id(record.workflow_version_id)
            return self.update(**data)
        except ValueError:
            return self.create(**data)

    # Query helpers
    def get_by_trace_id(self, trace_id: str) -> Optional[WorkflowExecutionRecord]:
        obj = self.session.query(WorkflowExecutionDo).filter_by(trace_id=trace_id).first()
        return self.to_record(obj) if obj else None

    def get_record(self, workflow_version_id: str) -> Optional[WorkflowExecutionRecord]:
        """Return a single workflow execution record."""
        obj = self.get_by_id(workflow_version_id)
        return self.to_record(obj) if obj else None

    def list_records(self, limit: int = 50) -> List[WorkflowExecutionRecord]:
        """List workflow execution records (recent first)."""
        objs = (
            self.session.query(WorkflowExecutionDo)
            .order_by(WorkflowExecutionDo.timestamp.desc())
            .limit(limit)
            .all()
        )
        return [self.to_record(o) for o in objs]

    def batch_get_records(self, workflow_version_ids: List[str]) -> List[WorkflowExecutionRecord]:
        """Batch fetch workflow execution records."""
        if not workflow_version_ids:
            return []
        objs = (
            self.session.query(WorkflowExecutionDo)
            .filter(WorkflowExecutionDo.workflow_version_id.in_(workflow_version_ids))
            .all()
        )
        return [self.to_record(o) for o in objs]