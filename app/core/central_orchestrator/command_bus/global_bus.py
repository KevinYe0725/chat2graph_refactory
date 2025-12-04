# 全局唯一 CommandManager 实例
from app.core.central_orchestrator.command_bus.command_manager import CommandManager

# 构建唯一实例
command_bus = CommandManager()
