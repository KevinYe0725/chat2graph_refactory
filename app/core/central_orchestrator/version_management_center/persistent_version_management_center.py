from __future__ import annotations

from typing import Dict, Any, List

from app.core.central_orchestrator.version_management_center.record import OperatorExecutionRecord, \
    ActionExecutionRecord, WorkflowExecutionRecord
from app.core.central_orchestrator.version_management_center.version_management_center import VersionManagementCenter
# DAO
from app.core.dal.dao.vmc.action_execution_dao import ActionExecutionDao
from app.core.dal.dao.vmc.operator_execution_dao import OperatorExecutionDao
from app.core.dal.dao.vmc.workflow_execution_dao import WorkflowExecutionDao

# DB session (你项目里已经封装好了)
from app.core.dal.database import DbSession


class PersistentVersionManagementCenter(VersionManagementCenter):
    """
    持久化版本管理中心
    写入策略：
        1. 先写入内存缓存（父类 VersionManagementCenter）
        2. 再写入数据库（Action/Operator/Workflow 三张表）
    """

    def __init__(self):
        super().__init__()

        # DAO 初始化
        session = DbSession()

        self.action_dao = ActionExecutionDao(session)
        self.operator_dao = OperatorExecutionDao(session)
        self.workflow_dao = WorkflowExecutionDao(session)

    # ---------------------------------------------
    # Action 级别持久化
    # ---------------------------------------------
    def log_action(self, record: ActionExecutionRecord) -> None:
        """双写：内存 + DB"""

        # 写入内存
        super().log_action(record)

        # 写入数据库
        with self.action_dao.new_session() as s:
            s.add(self._record_to_action_do(record))

    # ---------------------------------------------
    # Operator 级别持久化
    # ---------------------------------------------
    def log_operator(self, record: OperatorExecutionRecord) -> None:
        super().log_operator(record)

        with self.operator_dao.new_session() as s:
            s.add(self._record_to_operator_do(record))

    # ---------------------------------------------
    # Workflow 级别持久化
    # ---------------------------------------------
    def log_workflow(self, record: WorkflowExecutionRecord) -> None:
        super().log_workflow(record)

        with self.workflow_dao.new_session() as s:
            s.add(self._record_to_workflow_do(record))

    # ========================================================
    # Record → Do 转换器
    # ========================================================

    def _record_to_action_do(self, record: ActionExecutionRecord):
        from app.core.dal.do.vmc.action_execution_do import ActionExecutionDo

        return ActionExecutionDo(
            id=record.record_id,
            action_id=record.action_id,
            operator_id=record.operator_id,
            workflow_version_id=record.workflow_version_id,
            expert_name=record.expert_name,
            timestamp=record.timestamp,

            action_type=record.action_type,
            instruction=record.instruction,
            structured_input=record.structured_input,

            model_name=record.model_name,
            temperature=record.temperature,
            top_p=record.top_p,
            max_tokens=record.max_tokens,

            raw_output_text=record.raw_output_text,
            structured_output=record.structured_output,
            error=record.error,

            input_tokens=record.input_tokens,
            output_tokens=record.output_tokens,
            total_tokens=record.total_tokens,
            latency_ms=record.latency_ms,
            model_latency_ms=record.model_latency_ms,

            score=record.score,
            feedback=record.feedback,
            reasoning_content=record.reasoning_content,

            trace_id=record.trace_id,
            span_id=record.span_id,
            parent_span_id=record.parent_span_id,

            metadata=record.metadata,
        )

    def _record_to_operator_do(self, record: OperatorExecutionRecord):
        from app.core.dal.do.vmc.operator_execution_do import OperatorExecutionDo

        return OperatorExecutionDo(
            id=record.record_id,
            operator_id=record.operator_id,
            workflow_version_id=record.workflow_version_id,
            expert_name=record.expert_name,
            timestamp=record.timestamp,

            job_input=record.job_input,
            previous_operator_outputs=record.previous_operator_outputs,
            previous_expert_outputs=record.previous_expert_outputs,
            lesson=record.lesson,

            operator_config=record.operator_config,

            output_message=record.output_message,
            evaluation=record.evaluation,

            action_record_ids=[a.record_id for a in record.action_records],

            trace_id=record.trace_id,
            span_id=record.span_id,
            parent_span_id=record.parent_span_id,
            operator_name=record.operator_name,
            latency_ms=record.latency_ms,

            metadata=record.metadata,
        )

    def _record_to_workflow_do(self, record: WorkflowExecutionRecord):
        from app.core.dal.do.vmc.workflow_execution_do import WorkflowExecutionDo

        return WorkflowExecutionDo(
            workflow_version_id=record.workflow_version_id,
            expert_name=record.expert_name,
            timestamp=record.timestamp,

            trace_id=record.trace_id,
            span_id=record.span_id,
            parent_span_id=record.parent_span_id,

            operator_record_ids=[op.record_id for op in record.operator_records],

            metadata=record.metadata,
        )