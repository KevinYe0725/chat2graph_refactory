import asyncio
import time
import json
from functools import lru_cache
from typing import Any, Dict, List, Callable
from dataclasses import asdict

from app.core.model.job import Job

from app.core.model.message import WorkflowMessage, ModelMessage

from app.core.toolkit.action import Action

from app.core.common.singleton import Singleton
from openai.types.fine_tuning.alpha.grader_run_response import Metadata


class ActionService(metaclass=Singleton):
    """统一的 Action 管理与执行服务"""

    def __init__(self):
        self.registry = ActionRegistry()

    # ---------- 注册 ----------
    def register(self, action: Action, version: str = "1.0"):
        self.registry.add(action, version)

    # ---------- 创建 ----------
    @lru_cache(maxsize=64)
    def create(self, name: str) -> Action:
        """复制出独立实例（防止状态污染）"""
        template = self.registry.get(name)
        instance = template.copy()
        print(f"[ActionService] 🧩 创建 Action 实例：{name}")
        return instance

    # ---------- 执行 ----------
    #这个执行操作明天还是要重写的🤣
    def execute(self, name: str, **kwargs):
        """执行 Action 内部绑定的所有 Tool.function()"""
        action = self.create(name)
        start = time.time()

        results = []
        try:
            for tool in action.tools:
                func = tool.function
                print(f"[ActionService] ⚙️ 调用工具: {tool.name} ({tool.description})")
                result = func(**kwargs)
                results.append(
                    {
                        "tool_name": tool.name,
                        "output": result,
                        "tool_type": tool.tool_type.name,
                    }
                )

            elapsed = time.time() - start
            print(f"[ActionService] ✅ Action '{name}' 执行完成，用时 {elapsed:.3f}s")
            return {
                "status": "success",
                "action": name,
                "results": results,
                "time": elapsed,
            }

        except Exception as e:
            elapsed = time.time() - start
            print(f"[ActionService] ❌ Action '{name}' 执行失败: {e}")
            return {"status": "fail", "error": str(e), "time": elapsed}

    # ---------- 辅助 ----------
    def list_actions(self):
        return self.registry.list()

    def export_registry(self):
        return self.registry.export()




# ============================================================
# ActionRegistry
# ============================================================

class ActionRegistry:
    """管理所有 Action 模板定义（dataclass Action）"""

    def __init__(self):
        self._registry: Dict[str, Dict[str, Any]] = {}

    def add(self, action: Action, version: str = "1.0"):
        """注册 Action 定义"""
        if action.name not in self._registry:
            self._registry[action.name] = {"action": action, "version": version}
            print(f"[ActionRegistry] ✅ 注册 Action '{action.name}' (v{version})")
        else:
            print(f"{action.name} have been registered")

    def get(self, name: str) -> Action:
        if name not in self._registry:
            raise KeyError(f"[ActionRegistry] 未找到 Action '{name}'")
        return self._registry[name]["action"]

    def list(self):
        return list(self._registry.keys())

    def remove(self, name: str):
        if name in self._registry:
            del self._registry[name]
            print(f"[ActionRegistry] ❎ 取消注册 Action '{name}'")

    def export(self) -> str:
        """导出为 JSON"""
        return json.dumps(
            {k: v["action"].to_dict() for k, v in self._registry.items()},
            indent=2,
            ensure_ascii=False,
        )




class ActionPipeline:
    """按 order 顺序执行 + 层内并行的 Action 执行引擎（以 name 作为主键）"""

    def __init__(self, actions_dag: Dict[str, Dict[str, Any]], summarized_input_message: WorkflowMessage,job_id: str,operator_id:str, job: Job):
        """
        Args:
            actions_dag: build_dag() 的输出，键可为任意（但内部字段使用 name / order / depends_on）
            action_service: ActionService 实例，用于创建 Action 实例
        """
        # 转换成以 name 为主键的结构
        self.job_id = job_id
        self.actions_dag: Dict[str, Dict[str, Any]] = {
            node["name"]: node for node in actions_dag.values()
        }
        self.action_service:ActionService = ActionService.instance
        self.results: Dict[str, Any] = {}
        self.tasks: Dict[str, str] = self._get_task()
        self.ordered_layers = self._group_by_order()
        self.input_messages: WorkflowMessage = summarized_input_message
        self.operator_id = operator_id
        self.job:Job = job

    def _group_by_order(self) -> Dict[int, List[str]]:
        """按 order 分层（返回每层的 Action 名称列表）"""
        layers: Dict[int, List[str]] = {}
        for name, node in self.actions_dag.items():
            order = node.get("order", 0)
            layers.setdefault(order, []).append(name)
        return dict(sorted(layers.items()))

    def _get_task(self):
        tasks :Dict[str, str] = {}
        for name, node in self.actions_dag.items():
            tasks[name] = node.get("task", name)
        return tasks
    async def run(self, inputs: Dict[str, Any] = None) -> str:
        """顺序执行 DAG，每一层内并行"""
        if inputs is None:
            inputs = {"job_id": self.job_id}

        for order, names in self.ordered_layers.items():
            print(f"\n🧩 执行第 {order} 层 Actions：{names}")
            tasks = [ self._run_action(name, inputs) for name in names]
            results:List[ModelMessage] = await asyncio.gather(*tasks)
            i = 0
            self.input_messages.get_payload()["action_input"]["input_data"] =  {}
            for  result in results:
                self.results[names[i]] = result
                self.input_messages.get_payload()["action_input"]["input_data"][names[i]] = result.get_payload()
                i= i+1
        print("\n🎉 Pipeline 执行完成！")
        answer:str = json.dumps(self.results, indent=2, ensure_ascii=False)
        return answer

    async def _run_action(self, name: str, inputs: Dict[str, Any]) -> ModelMessage:
        print(f"🚀 [ActionPipeline] 执行 {name}")
        action = self.action_service.create(name)
        inputs["task"] = self.tasks[name]
        inputs["job"] = self.job
        inputs["message"] = self.input_messages
        inputs["operator_id"] = self.operator_id
        result: ModelMessage = await action.run(inputs)
        print(f"✅ [{name}] 输出: {result}")
        return result


