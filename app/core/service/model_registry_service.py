from typing import Dict, List

from app.core.common.singleton import Singleton
from app.core.model.agentic_config import ModelConfig
from app.core.model.llm_model import LLMModel


class ModelRegistryService(metaclass=Singleton):
    """
    一个全局的模型注册器，用来管理所有 ModelService。
    作用：
      1. 在应用启动时初始化所有 model（从 AgenticConfig.models）
      2. 按 model_name 获取对应的 ModelService（Action 会用到）
    """

    _registry: Dict[str, LLMModel] = {}

    @classmethod
    def init(cls, model_configs: List[ModelConfig]):
        """
        在应用启动时调用一次，注册所有模型
        """
        cls._registry.clear()

        for cfg in model_configs:
            model = LLMModel(
                name=cfg.name,
                model_type=cfg.model_type,
                api_key=cfg.api_key,
                endpoint=cfg.endpoint,
                model_path=cfg.model_path,
                temperature=cfg.temperature,
                top_k=cfg.top_k,
                system_prompt=cfg.system_prompt,
            )
            cls._registry[cfg.name] = model

    @property
    def models(self) -> Dict[str, LLMModel]:
        return self._registry
