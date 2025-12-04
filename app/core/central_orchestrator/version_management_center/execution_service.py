# app/core/versioning/execution_record_service.py

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from app.core.central_orchestrator.version_management_center.record import WorkflowExecutionRecord, \
    OperatorExecutionRecord, ActionExecutionRecord
from app.core.dal.dao.vmc.action_execution_dao import ActionExecutionDao
from app.core.dal.dao.vmc.operator_execution_dao import OperatorExecutionDao
from app.core.dal.dao.vmc.workflow_execution_dao import WorkflowExecutionDao


class ExecutionRecordService:
    """
    Unified service for querying execution records across:
    - WorkflowExecutionRecord
    - OperatorExecutionRecord
    - ActionExecutionRecord

    Supports full chain reconstruction.
    """

    def __init__(self, db: Session):
        self.db = db
        self.action_dao = ActionExecutionDao(db)
        self.operator_dao = OperatorExecutionDao(db)
        self.workflow_dao = WorkflowExecutionDao(db)

    # ============================================================
    # -------- Workflow-level  Query ------------------------------
    # ============================================================
    def get_workflow_record(self, workflow_version_id: str) -> Optional[WorkflowExecutionRecord]:
        """Get a workflow record by version ID."""
        return self.workflow_dao.get_record(workflow_version_id)

    def list_workflow_records(self, limit: int = 50) -> List[WorkflowExecutionRecord]:
        """List workflow execution histories."""
        return self.workflow_dao.list_records(limit)

    # ============================================================
    # -------- Operator-level  Query -------------------------------
    # ============================================================
    def get_operator_record(self, record_id: str) -> Optional[OperatorExecutionRecord]:
        return self.operator_dao.get_record(record_id)

    def list_operators_by_workflow(self, workflow_version_id: str) -> List[OperatorExecutionRecord]:
        wf = self.workflow_dao.get_record(workflow_version_id)
        if not wf:
            return []
        return self.operator_dao.batch_get_records([ operator_record.record_id for operator_record in wf.operator_records])

    # ============================================================
    # -------- Action-level Query ---------------------------------
    # ============================================================
    def get_action_record(self, record_id: str) -> Optional[ActionExecutionRecord]:
        return self.action_dao.get_record(record_id)

    def list_actions_by_operator(self, operator_record_id: str) -> List[ActionExecutionRecord]:
        op = self.operator_dao.get_record(operator_record_id)
        if not op:
            return []
        return self.action_dao.batch_get_records([record.record_id for record in op.action_records])

    # ============================================================
    # -------- Full Chain Reconstruction ---------------------------
    # ============================================================
    def reconstruct_full_workflow_chain(
        self, workflow_version_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Reconstruct the full execution chain:
        Workflow → Operators → Actions
        """
        wf = self.workflow_dao.get_record(workflow_version_id)
        if not wf:
            return None

        operator_records = self.operator_dao.batch_get_records([ operator_record.record_id for operator_record in wf.operator_records])

        result = {
            "workflow": wf,
            "operators": [],
        }

        for op in operator_records:
            actions = self.action_dao.batch_get_records([record.record_id for record in op.action_records])
            result["operators"].append(
                {
                    "operator": op,
                    "actions": actions,
                }
            )

        return result

    # ============================================================
    # -------- Reverse Lookup -------------------------------------
    # ============================================================
    def locate_from_action(self, action_record_id: str) -> Optional[Dict[str, Any]]:
        """
        Given action → find its operator → find workflow
        """
        action = self.action_dao.get_record(action_record_id)
        if not action:
            return None

        operator = self.operator_dao.find_by_operator_span(action.operator_id, action.span_id)
        if not operator:
            return None

        workflow = self.workflow_dao.get_record(operator.workflow_version_id)

        return {
            "workflow": workflow,
            "operator": operator,
            "action": action,
        }

    # ============================================================
    # -------- Debug / Pretty Print --------------------------------
    # ============================================================
    def pretty_print_workflow(self, workflow_version_id: str) -> None:
        """Print workflow chain in readable form."""
        data = self.reconstruct_full_workflow_chain(workflow_version_id)
        if not data:
            print("Workflow not found")
            return

        print(f"\n🚀 Workflow Version: {workflow_version_id}")
        print(f"Expert: {data['workflow'].expert_name}\n")

        for idx, item in enumerate(data["operators"]):
            operator = item["operator"]
            print(f"  ▶ Operator[{idx}] {operator.operator_config.get('name')}")
            print(f"     span={operator.span_id} trace={operator.trace_id}")
            print(f"     actions: {len(item['actions'])}")
            for a in item["actions"]:
                print(f"       - Action {a.action_type} span={a.span_id}")
            print()