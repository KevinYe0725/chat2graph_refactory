from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, Any
import uuid


def _uuid() -> str:
    return str(uuid.uuid4())


# ============================================================
# 1️⃣ ActionExecutionRecord —— 最小执行单位（模型调用）
# ============================================================

@dataclass(frozen=True)
class ActionExecutionRecord:
    record_id: str = field(default_factory=_uuid)

    # 定位信息
    action_id: str = ""                # ActionConfig.id
    operator_id: str = ""
    workflow_version_id: str = ""
    expert_name: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # 输入侧
    action_type: str = ""              # "llm" / "tool" / "graph_query" ...
    instruction: Optional[str] = None  # Prompt / instruction
    structured_input: Dict[str, Any] = field(default_factory=dict)

    # 模型相关
    model_name: Optional[str] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None

    # 输出侧
    raw_output_text: Optional[str] = None
    structured_output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    # 性能指标
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    latency_ms: Optional[float] = None        # 整体耗时
    model_latency_ms: Optional[float] = None  # 模型推理耗时（若模型提供）

    # 监督信号（用于 RLHF）
    score: Optional[float] = None             # 0~1 或 supervisor评分
    feedback: Optional[str] = None            # 人类/模型的评语
    reasoning_content: Optional[str] = None   # 可选：模型隐藏推理（若保留）

    # trace 信息
    trace_id: str = ""
    span_id: str = ""
    parent_span_id: Optional[str] = None

    # 自定义拓展
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# 2️⃣ OperatorExecutionRecord —— 聚合多个 Action
# ============================================================

@dataclass(frozen=True)
class OperatorExecutionRecord:
    record_id: str = field(default_factory=_uuid)

    operator_id: str = ""
    workflow_version_id: str = ""
    expert_name: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Operator 输入上下文
    job_input: Dict[str, Any] = field(default_factory=dict)
    previous_operator_outputs: List[Any] = field(default_factory=list)
    previous_expert_outputs: List[Any] = field(default_factory=list)
    lesson: Optional[str] = None

    # operator 配置快照
    operator_config: Dict[str, Any] = field(default_factory=dict)

    # operator 输出
    output_message: Any = None                # WorkflowMessage
    evaluation: Optional[str] = None          # operator 级别评价

    # action 粒度的记录
    action_records: List[ActionExecutionRecord] = field(default_factory=list)
    parent_span_id: Optional[str] = None

    # operator 名称
    operator_name: Optional[str] = None

    # operator 耗时（可选）
    latency_ms: Optional[float] = None
    # trace 信息
    trace_id: str = ""
    span_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# 3️⃣ WorkflowExecutionRecord —— 聚合多个 Operator
# ============================================================

@dataclass(frozen=True)
class WorkflowExecutionRecord:
    workflow_version_id: str = ""
    expert_name: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    trace_id: str = ""
    span_id: str = ""
    operator_records: List[OperatorExecutionRecord] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)