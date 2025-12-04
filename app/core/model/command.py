from dataclasses import dataclass, field
from typing import Optional, Dict
import time
import uuid

@dataclass
class Command:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action: str = ""                 # 动作类型（run, retry, reassign, stop, feedback等）
    target: str = ""                 # 目标节点ID或模块
    params: Dict = field(default_factory=dict)  # 附加参数
    func_name: str = " "
    priority: int = 0
    retry_count: int = 0
    max_retries: int = 3
    source: str = ""                 # 来源模块（Expert, Supervisor, Leader, Gate）
    reason: Optional[str] = None     # 决策原因
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))  # 全链路追踪 ID
    parent_id: Optional[str] = None
    span_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    status: str = "pending"          # pending/running/retrying/failed/success/dead
    final_result: Optional[str] = None
    error: Optional[str] = None      # 失败原因
