from dataclasses import dataclass
from typing import List


@dataclass
class StructMessage:
    summary_text: str             # 自然语言摘要
    key_points: List[str]         # 提炼的关键点
    related_jobs: List[str]       # 与任务相关的 job id 或主题
    expert_lessons: str           # lesson 内容（整合）
    combined_context: str         # 拼接的上下文文本（供下游模型使用）
