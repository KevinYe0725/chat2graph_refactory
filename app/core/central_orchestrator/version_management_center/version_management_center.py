from typing import List, Optional, Any, Dict

from app.core.common.singleton import Singleton

from app.core.central_orchestrator.version_management_center.record import OperatorExecutionRecord, \
    ActionExecutionRecord, WorkflowExecutionRecord


class VersionManagementCenter(metaclass=Singleton):
    """
    Version Management Center (VMC).

    负责记录 Action / Operator / Workflow 三层执行版本。
    当前实现为内存数据库，将来可接 PostgreSQL / Milvus / Qdrant / S3 / MinIO。
    """

    def __init__(self) -> None:
        # Action 记录
        self._action_by_id: Dict[str, ActionExecutionRecord] = {}
        self._actions_by_action_id: Dict[str, List[ActionExecutionRecord]] = {}
        self._actions_by_operator_id: Dict[str, List[ActionExecutionRecord]] = {}
        self._actions_by_trace_id: Dict[str, List[ActionExecutionRecord]] = {}

        # Operator 记录
        self._operator_by_id: Dict[str, OperatorExecutionRecord] = {}
        self._operator_by_operator_id: Dict[str, List[OperatorExecutionRecord]] = {}
        self._operator_by_workflow_version: Dict[str, List[OperatorExecutionRecord]] = {}

        # Workflow 记录
        self._workflow_by_version: Dict[str, WorkflowExecutionRecord] = {}
        # Workflow trace/span 索引
        self._workflow_by_trace_id: Dict[str, WorkflowExecutionRecord] = {}
        self._workflow_by_span_id: Dict[str, WorkflowExecutionRecord] = {}

    # ---------------------------------------------------------
    # Action 级别
    # ---------------------------------------------------------

    def log_action(self, record: ActionExecutionRecord) -> None:
        self._action_by_id[record.record_id] = record

        self._actions_by_action_id.setdefault(record.action_id, []).append(record)
        self._actions_by_operator_id.setdefault(record.operator_id, []).append(record)
        self._actions_by_trace_id.setdefault(record.trace_id, []).append(record)

    def get_action_record(self, record_id: str) -> Optional[ActionExecutionRecord]:
        return self._action_by_id.get(record_id)

    def get_actions_by_action_id(self, action_id: str) -> List[ActionExecutionRecord]:
        return list(self._actions_by_action_id.get(action_id, []))

    def get_actions_by_operator_id(self, operator_id: str) -> List[ActionExecutionRecord]:
        return list(self._actions_by_operator_id.get(operator_id, []))

    def get_actions_by_trace_id(self, trace_id: str) -> List[ActionExecutionRecord]:
        return list(self._actions_by_trace_id.get(trace_id, []))

    # ---------------------------------------------------------
    # Operator 级别
    # ---------------------------------------------------------

    def log_operator(self, record: OperatorExecutionRecord) -> None:
        self._operator_by_id[record.record_id] = record

        self._operator_by_operator_id.setdefault(record.operator_id, []).append(record)
        self._operator_by_workflow_version.setdefault(record.workflow_version_id, []).append(record)

        workflow = self._workflow_by_version.get(record.workflow_version_id)
        if workflow:
            workflow.operator_records.append(record)

    def get_operator_record(self, record_id: str) -> Optional[OperatorExecutionRecord]:
        return self._operator_by_id.get(record_id)

    def get_operator_history(self, operator_id: str) -> List[OperatorExecutionRecord]:
        records = list(self._operator_by_operator_id.get(operator_id, []))
        return sorted(records, key=lambda r: r.timestamp)

    def get_operators_by_workflow(self, workflow_version_id: str) -> List[OperatorExecutionRecord]:
        records = list(self._operator_by_workflow_version.get(workflow_version_id, []))
        return sorted(records, key=lambda r: r.timestamp)

    # ---------------------------------------------------------
    # Workflow 级别
    # ---------------------------------------------------------

    def log_workflow(self, record: WorkflowExecutionRecord) -> None:
        self._workflow_by_version[record.workflow_version_id] = record
        self._workflow_by_trace_id[record.trace_id] = record
        self._workflow_by_span_id[record.span_id] = record

    def get_workflow_record(self, workflow_version_id: str) -> Optional[
        WorkflowExecutionRecord]:
        return self._workflow_by_version.get(workflow_version_id)

    def get_workflow_by_trace_id(self, trace_id: str) -> Optional[WorkflowExecutionRecord]:
        return self._workflow_by_trace_id.get(trace_id)

    # ---------------------------------------------------------
    # RLHF / 训练数据集导出
    # ---------------------------------------------------------

    def export_rlhf_samples(
        self,
        *,
        model_name: Optional[str] = None,
        min_score: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """导出 Action 粒度的 RLHF 样本。"""

        samples: List[Dict[str, Any]] = []
        for rec in self._action_by_id.values():
            if model_name and rec.model_name != model_name:
                continue
            if min_score is not None and (rec.score is None or rec.score < min_score):
                continue

            sample = {
                "prompt": rec.instruction,
                "input": rec.structured_input,
                "output": rec.raw_output_text,
                "structured_output": rec.structured_output,
                "score": rec.score,
                "feedback": rec.feedback,
                "tokens": {
                    "input": rec.input_tokens,
                    "output": rec.output_tokens,
                    "total": rec.total_tokens,
                },
                "latency_ms": rec.latency_ms,
                "model": rec.model_name,
                "trace_id": rec.trace_id,
                "operator_id": rec.operator_id,
                "workflow_version_id": rec.workflow_version_id,
                "timestamp": rec.timestamp.isoformat(),
            }
            samples.append(sample)

        return samples