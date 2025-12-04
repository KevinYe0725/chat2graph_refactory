

from typing import Any, Awaitable, Callable, Protocol, runtime_checkable


@runtime_checkable
class CommandHandlerFunc(Protocol):
    """Protocol for command handler functions.

    这里不强制参数签名，只约束为可调用对象，并允许返回同步或异步结果。
    """
    def __call__(self, *args: Any, **kwargs: Any) -> Any | Awaitable[Any]:
        ...


def command_handler(action: str) -> Callable[[CommandHandlerFunc], CommandHandlerFunc]:

    def decorator(func: CommandHandlerFunc) -> CommandHandlerFunc:
        # 打上标记，方便之后通过反射扫描
        setattr(func, "_is_command_handler", True)
        setattr(func, "_command_action", action)
        return func

    return decorator