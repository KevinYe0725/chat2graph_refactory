

import threading
from queue import Queue, Empty
from typing import Callable, Optional, Dict, Any

from app.plugin.dbgpt.dbgpt_workflow import DbgptWorkflow

from app.core.workflow.workflow import Workflow

from app.core.agent.agent import AgentConfig, Profile

from app.core.central_orchestrator.supervisor.supervisor import Supervisor
from app.core.model.message import AgentMessage
from app.core.reasoner.simple_reasoner import SimpleReasoner


class SupervisorPool:
    """
    Supervisor 线程池：
    - 维护多个 Supervisor worker
    - 从队列获取任务
    - 执行 supervisor.execute(agent_message)
    - 将结果通过 callback 返回给 SupervisorManager
    """

    def __init__(self, num_workers: int, callback: Callable[[str, Dict[str, Any]], None]):
        """
        :param num_workers: worker 数量
        :param callback: 回调函数，由 SupervisorManager 提供
        """
        self.num_workers = num_workers
        self.callback = callback
        self.running = True

        # 队列存储 AgentMessage
        self.task_queue: Queue[Optional[AgentMessage]] = Queue()
        supervisor_config = AgentConfig(
            profile=Profile(name="supervisor",description="used to inspect every operator"),
            reasoner=SimpleReasoner(),
            workflow = DbgptWorkflow(),
        )
        # worker 线程列表
        self.workers = []

        # 初始化 worker
        for _ in range(num_workers):
            supervisor = Supervisor(supervisor_config)
            t = threading.Thread(target=self._worker_loop, args=(supervisor,))
            t.daemon = True
            self.workers.append(t)
            t.start()

    def submit(self, msg: AgentMessage):
        """将任务提交到队列"""
        self.task_queue.put(msg)

    def _worker_loop(self, supervisor: Supervisor):
        """Worker 主循环"""
        while self.running:
            try:
                msg = self.task_queue.get(timeout=1)
            except Empty:
                continue

            if msg is None:
                continue

            try:
                result = supervisor.execute(msg)
                # 将结果交给 Manager
                self.callback(msg.get_job_id(), result)
            except Exception as e:
                self.callback(msg.get_job_id(), {
                    "error": str(e),
                    "action": "failed"
                })

    def stop(self):
        """关闭线程池"""
        self.running = False

        # 向 queue 投递 None，让线程尽快退出
        for _ in self.workers:
            self.task_queue.put(None)