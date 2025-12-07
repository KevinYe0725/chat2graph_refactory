from app.core.model.execution_context import ExecutionContext



class ExecutionContextService:
    def __init__(self) -> None:
        self._execution_contexts: dict[str, ExecutionContext] = {}

    def set_execution_context(self, expert_name: str, context: ExecutionContext) -> None:
        self._execution_contexts[expert_name] = context

    def get_execution_context(self, expert_name: str) -> ExecutionContext:
        return self._execution_contexts[expert_name]