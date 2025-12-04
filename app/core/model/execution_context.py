from uuid import uuid4
from typing import Dict, Any, Optional
import time


class ExecutionContext:
    """保存整个 Workflow → Operator → Action 执行链路的上下文"""

    def __init__(self, workflow_version_id: Optional[str] = None, expert_name: str = ""):
        # ───────────────────────────────
        # Workflow级别
        # ───────────────────────────────
        self.trace_id: str = uuid4().hex                # 全链路根节点 ID
        self.workflow_span_id: str = uuid4().hex        # workflow 的 span
        self.workflow_version_id: Optional[str] = workflow_version_id
        self.expert_name: str = expert_name

        self.start_timestamp: float = time.time()        # workflow 执行开始时间
        self.status: str = "running"                    # running / paused / rollback / finished

        # ───────────────────────────────
        # Operator级别
        # ───────────────────────────────
        self.operator_spans: Dict[str, str] = {}         # op_id → span_id
        self.operator_exec_count: Dict[str, int] = {}    # op_id → 执行次数

        self.current_operator_id: Optional[str] = None

        # ───────────────────────────────
        # Action级别
        # ───────────────────────────────
        self.action_spans: Dict[str, str] = {}           # action_id → span_id
        self.action_exec_count: Dict[str, int] = {}      # action_id → 执行次数

        self.current_action_id: Optional[str] = None

        # ───────────────────────────────
        # Token / Latency 聚合（Supervisor & 评估需要）
        # ───────────────────────────────
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.total_latency_ms: float = 0.0

        # 额外元数据（其他模块可以塞东西）
        self.metadata: Dict[str, Any] = {}

    # ─────────────────────────────────────────────────
    # Helper：生成 OperatorSpan
    # ─────────────────────────────────────────────────
    def new_operator_span(self, op_id: str) -> str:
        span_id = uuid4().hex
        self.operator_spans[op_id] = span_id
        self.operator_exec_count[op_id] = self.operator_exec_count.get(op_id, 0) + 1
        self.current_operator_id = op_id
        return span_id

    def get_operator_parent_span(self) -> str:
        return self.workflow_span_id

    # ─────────────────────────────────────────────────
    # Helper：生成 ActionSpan
    # ─────────────────────────────────────────────────
    def new_action_span(self, action_id: str) -> str:
        span_id = uuid4().hex
        self.action_spans[action_id] = span_id
        self.action_exec_count[action_id] = self.action_exec_count.get(action_id, 0) + 1
        self.current_action_id = action_id
        return span_id

    def get_action_parent_span(self) -> Optional[str]:
        if self.current_operator_id:
            return self.operator_spans.get(self.current_operator_id)
        return None

    # ─────────────────────────────────────────────────
    # 汇总 token / latency
    # ─────────────────────────────────────────────────
    def add_tokens(self, input_tokens: int, output_tokens: int):
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

    def add_latency(self, ms: float):
        self.total_latency_ms += ms