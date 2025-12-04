import json
from typing import Dict, Any, Optional, Callable

from app.core.central_orchestrator.command_bus.global_bus import command_bus
from app.core.central_orchestrator.supervisor.supervisor_pool import SupervisorPool
from app.core.model.command import Command
from app.core.model.message import AgentMessage



class SupervisorManager:
    """
    SupervisorManager 负责：
    1. 接收 Orchestrator 推来的 operator 执行输出
    2. 将输出封装成 AgentMessage 放入 SupervisorPool
    3. 接收 SupervisorPool 的 callback（监督结果）
    4. 根据监督结果生成 Command
    5. 将 Command 交给 CommandManager（command_bus）
    """

    def __init__(self, num_workers: int = 2):
        # Pool 的 callback 回传给 handle_supervisor_output()
        self.pool = SupervisorPool(
            num_workers=num_workers,
            callback=self.handle_supervisor_output
        )

    def on_operator_result(self, job_id: str, payload: Dict[str, Any]):
        """
        由 CentralOrchestrator 调用，通知一个 operator 执行完毕。

        payload 结构应包含：
            - expert_name
            - operator_id
            - operator_task
            - operator_output
            - operator_status
            - predecessors
            - successors
        """

        print(f"[SupervisorManager] 收到 Operator 输出: {payload}")

        # 构建 AgentMessage 传给 SupervisorPool
        message = AgentMessage(
            job_id=job_id,
            payload=json.dumps(payload)
        )

        # 放入线程池 queue
        self.pool.submit(message)

    def handle_supervisor_output(self, job_id: str, result: Dict[str, Any]):
        """
        由 SupervisorPool 回调（每个 worker 执行完一次监督任务后）
        result 是 Supervisor 给出的 JSON：
        {
            "score": 0.7,
            "action": "retry",
            "reason": "...",
            "instruction": "..."
        }
        """

        print(f"[SupervisorManager] 收到监督反馈: job={job_id} result={result}")

        action = result.get("action", "")
        if not action:
            print("[SupervisorManager] 无效监督结果，忽略")
            return

        # 构建 Command 传给 orchestrator
        cmd = Command(
            action=action,
            target=result.get("operator_id", " "),  # Supervisor 内会带上这个字段
            params={
                "score": result.get("score"),
                "reason": result.get("reason"),
                "instruction": result.get("instruction")
            }
        )

        print(f"[SupervisorManager] 发送 Command → {cmd}")
        command_bus.send(cmd)

    def stop(self):
        """关闭 SupervisorPool"""
        self.pool.stop()
