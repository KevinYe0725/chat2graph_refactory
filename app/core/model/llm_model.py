from dataclasses import dataclass
from typing import Optional

from app.core.common.system_env import SystemEnv


@dataclass
class LLMModel:
    name: str
    model_type: str   # openai / local / huggingface / mcp
    temperature: float = 0.7
    api_key: Optional[str] = None
    endpoint: Optional[str] = None
    model_path: Optional[str] = None
    system_prompt: Optional[str] = None
    top_k: int = SystemEnv.DEFAULT_TOP_K
