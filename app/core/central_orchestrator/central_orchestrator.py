from pygments.lexer import words

from app.core.central_orchestrator.command_bus.command_handler import command_handler
from app.core.central_orchestrator.supervisor.supervisor_manager import SupervisorManager
from app.core.common.singleton import Singleton
from app.core.model.execution_context import ExecutionContext
from app.core.service.operator_service import OperatorService

from app.core.workflow.workflow import Workflow


class CentralOrchestrator(metaclass=Singleton):
    def __init__(self):
        # 存储所有 workflow：expert → workflow
        self._workflows: dict[str, Workflow] = {}
        self.supervisor_manager = SupervisorManager() # 外部注入 SupervisorManager
        self._operator_service:OperatorService = OperatorService.instance
        self._execution_contexts:dict[str, ExecutionContext] = {}
        import threading
        self._condition = threading.Condition()
        self._can_continue = False


    #注册workflow
    def register_workflow(self, workflow: Workflow, expert_name: str) -> None:
        self._workflows[expert_name] = workflow



    #在operator运行结束后，主动去notify supervisor来对结果进行评定
    def notify_operator_result(self, expert_name:str, operator_id: str, answer: str, task: str, job_id: str) -> None:
        workflow = self._workflows[expert_name]
        predecessors = list(workflow.operator_graph.predecessors(operator_id))
        successors = list(workflow.operator_graph.successors(operator_id))
        payload = {
            "expert_name": expert_name,
            "operator_id": operator_id,
            "operator_task": task,
            "operator_output": answer,
            "operator_status": "success",
            # workflow 上下游语义结构
            "predecessors": predecessors,
            "successors": successors,
        }

        # 调用 SupervisorManager
        self.supervisor_manager.on_operator_result(job_id, payload)

    #operator通过这里获取注册好的task（用于跳过内部库函数无法修改的问题）
    def get_running_operator_task(self, expert_name:str, op_id: str) -> str:
        running_workflow = self._workflows[expert_name]
        task = running_workflow.operator_task_dict[op_id]["task"]
        return task


    def wait_for_continue(self):
        """Called by Expert to wait until Orchestrator allows further execution."""
        with self._condition:
            while not self._can_continue:
                self._condition.wait()
            # reset flag
            self._can_continue = False

    def allow_continue(self):
        """Called by Orchestrator after supervisor review to let Expert proceed."""
        with self._condition:
            self._can_continue = True
            self._condition.notify_all()


    @command_handler(action="rollback")
    def rollback(self, expert_name: str,to_op_id) -> None:
        workflow = self._workflows[expert_name]
        workflow.rollback(to_op_id)

    def set_execution_context(self, expert_name:str, context: ExecutionContext) -> None:
        self._execution_contexts[expert_name] = context

    def get_execution_context(self,expert_name:str) -> ExecutionContext:
        return self._execution_contexts[expert_name]