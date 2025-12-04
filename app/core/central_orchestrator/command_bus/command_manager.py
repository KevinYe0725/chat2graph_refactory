import inspect
import asyncio
import uuid
from queue import PriorityQueue
from typing import Callable, List, Any, Tuple

from app.core.model.command import Command


#管理Command，并且可以去执行
class CommandManager:
    def __init__(self):
        self.command_queue: PriorityQueue[Tuple[int, int, Command]] = PriorityQueue()
        self._seq: int = 0
        self.dead_letter_queue: List[Command] = []
        self.command_validators: List[Callable] = []
        self._handlers: dict[str, Callable] = {}
        self.handler_failure_hooks: List[Callable] = []

    def register_handlers_from(self, obj):
        for attr_name in dir(obj):
            attr = getattr(obj, attr_name)
            if callable(attr) and getattr(attr, "_is_command_handler", False):
                action = getattr(attr, "_command_action")
                self._handlers[action] = attr
                print(f"[CommandManager] 自动注册指令处理器: action='{action}' → {obj.__class__.__name__}.{attr_name}")

    def _prepare_trace_info(self, command: Command, parent_command: Command | None = None):
        """
        对 command 自动填充 trace_id / parent_id / span_id
        """

        # 如果是新任务，没有 trace_id → 自动生成
        if not getattr(command, "trace_id", None):
            command.trace_id = str(uuid.uuid4())

        # 如果有 parent_command → 继承 trace 并写 parent_id
        if parent_command is not None:
            command.parent_id = parent_command.id
            command.trace_id = parent_command.trace_id  # 继承全链路 trace
        else:
            # 如果没有 parent，但外部给了 parent_id，则保持
            command.parent_id = getattr(command, "parent_id", None)

        # 每次接收 command 时都生成新的 span_id（分段追踪）
        command.span_id = str(uuid.uuid4())

        return command

    def receive(self, command: Command, parent_command: Command | None = None):
        print(f"[CommandManager] 接收到命令: {command.action}")

        # 自动生成 trace 信息
        command = self._prepare_trace_info(command, parent_command)

        if self._validate(command):
            priority = getattr(command, "priority", 0)
            self._seq += 1
            self.command_queue.put((priority, self._seq, command))

    def register_validator(self, command_validator_fn: Callable):
        self.command_validators.append(command_validator_fn)

    def _validate(self, command: Command) -> bool:
        for validator in self.command_validators:
            if not validator(command):
                print(f"[Validator] Command 无效: {command}")
                return False
        return True

    def dispatch(self):
        while not self.command_queue.empty():
            priority, _, command = self.command_queue.get()
            action = command.action
            handler = self._handlers.get(action)
            if handler is None:
                raise ValueError(f"未知的 command.action='{action}'，未找到对应处理器")
            sig = inspect.signature(handler)
            bound_args = {}

            for name, param in sig.parameters.items():
                if name in command.params:
                    bound_args[name] = command.params[name]
                elif param.default is not inspect._empty:
                    bound_args[name] = param.default
                else:
                    raise ValueError(
                        f"调用 subscriber 失败：缺少必需参数 '{name}'"
                    )

            try:
                handler(**bound_args)
                command.final_result = "已完成"
                print(f"[CommandManager] 命令已派发: {command.id}")

            except Exception as e:
                print(f"[Subscriber Error] 执行失败: {e}")

                # retry 逻辑
                if getattr(command, "retry_count", 0) < getattr(command, "max_retries", 3):
                    command.retry_count = getattr(command, "retry_count", 0) + 1
                    print(f"[Retry] 第 {command.retry_count} 次重试: {command.id}")
                    self._seq += 1
                    self.command_queue.put((priority, self._seq, command))
                    continue

                # failure hook
                for hook in self.handler_failure_hooks:
                    hook(command, handler, e)

                print(f"[Failed] Command {command.id} 最终失败")
                self.dead_letter_queue.append(command)

    async def dispatch_async(self):
        """在 async 场景下，支持 async subscriber"""
        while not self.command_queue.empty():
            priority, _, command = self.command_queue.get()
            action = command.action
            handler = self._handlers.get(action)
            if handler is None:
                raise ValueError(f"未知的 command.action='{action}'，未找到对应处理器")
            sig = inspect.signature(handler)
            bound_args = {}

            for name, param in sig.parameters.items():
                if name in command.params:
                    bound_args[name] = command.params[name]
                elif param.default is not inspect._empty:
                    bound_args[name] = param.default
                else:
                    raise ValueError(
                        f"调用 subscriber 失败：缺少必需参数 '{name}'"
                    )

            try:
                if inspect.iscoroutinefunction(handler):
                    await handler(**bound_args)
                else:
                    handler(**bound_args)
                command.final_result = "已完成"
                print(f"[CommandManager] 命令已派发: {command.id}")

            except Exception as e:
                print(f"[Subscriber Error] 执行失败: {e}")

                # retry 逻辑
                if getattr(command, "retry_count", 0) < getattr(command, "max_retries", 3):
                    command.retry_count = getattr(command, "retry_count", 0) + 1
                    print(f"[Retry] 第 {command.retry_count} 次重试: {command.id}")
                    self._seq += 1
                    self.command_queue.put((priority, self._seq, command))
                    continue

                # failure hook
                for hook in self.handler_failure_hooks:
                    hook(command, handler, e)

                print(f"[Failed] Command {command.id} 最终失败")
                self.dead_letter_queue.append(command)