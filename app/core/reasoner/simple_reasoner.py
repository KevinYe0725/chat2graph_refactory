from typing import Any, Dict, List

from app.core.model.message import ModelMessage

from app.core.prompt.reasoner import SUPERVISOR_PROMPT_TEMPLATE, OPERATOR_PROMPT_TEMPLATE, \
    OPERATOR_CONCLUDE_PROMPT_TEMPLATE
from app.core.reasoner.model_service_factory import ModelServiceFactory

from app.core.common.system_env import SystemEnv

from app.core.reasoner.model_service import ModelService

from app.core.common.type import MessageSourceType

from app.core.memory.reasoner_memory import ReasonerMemory
from app.core.model.task import Task

from app.core.reasoner.reasoner import Reasoner


class SimpleReasoner(Reasoner):
    """Simple Reasoner."""

    def __init__(
            self,
            model_name: str = MessageSourceType.MODEL.value,
    ):
        super().__init__()

        self._model_name = model_name
        self._model: ModelService = ModelServiceFactory.create(
            model_platform_type=SystemEnv.MODEL_PLATFORM_TYPE
        )

    async def evaluate(self, data: Any) -> Any:
        pass

    async def conclude(self, reasoner_memory: ReasonerMemory) -> str:
        pass

    def init_memory(self, task: Task) -> ReasonerMemory:
        pass

    def get_memory(self, task: Task) -> ReasonerMemory:
        pass

    async def update_knowledge(self, data: Any) -> None:
        pass

    async def reasoning(self, task: Task, context: Dict[str,Any]) -> Any:
        model = context.get("model")
        if model is None:
            print("there is no model, use API to use LLM")
            if context.get("role") == "Supervisor":
                action_description = task.job.context
                prompt = self._format_supervisor_prompt(action_description)
                messages: List[ModelMessage] = []
                response = await self._model.generate(prompt,messages)
                return response
            else:
                role = context.get("role")
                raise ValueError(
                    f"当前没有这个role:{role}"
                )
        else:
            #留给后续的expert底下的action的model的逻辑
            pass

    async def generate(self, prompt: str) -> str:
        messages: List[ModelMessage] = []
        response:ModelMessage = await self._model.generate(prompt,messages)

        return response.get_payload()







    async def infer(self, task: Task) -> str:
        pass

    def _format_supervisor_prompt(self, action_description) -> str:
        return SUPERVISOR_PROMPT_TEMPLATE.format(
            action_description=action_description,
        )

    async def operator_conclude(self, results) -> str:
        prompt = OPERATOR_CONCLUDE_PROMPT_TEMPLATE.format(
            results=results,
        )
        return await self.generate(prompt)


