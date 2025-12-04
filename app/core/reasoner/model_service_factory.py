from app.core.common.type import ModelPlatformType
from app.core.reasoner.model_service import ModelService
from app.plugin.aisuite.aisuite_llm_client import AiSuiteLlmClient
from app.plugin.lite_llm.lite_llm_client import LiteLlmClient
from app.plugin.model_set.model_set_client import ModelSetClient


class ModelServiceFactory:
    """Model service factory."""

    @classmethod
    def create(cls, model_platform_type: ModelPlatformType, **kwargs) -> ModelService:
        """Create a model service."""
        if model_platform_type == ModelPlatformType.LITELLM:
            return LiteLlmClient()
        if model_platform_type == ModelPlatformType.AISUITE:
            return AiSuiteLlmClient()
        # TODO: add more platforms, so the **kwargs can be used to pass the necessary parameters
        raise ValueError(f"Cannot create model service of type {model_platform_type}")


    @classmethod
    def get_model_for_action(cls, model_name):
        return ModelSetClient(model_name)