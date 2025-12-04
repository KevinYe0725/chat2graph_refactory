import random
from typing import List, Optional, Dict

from app.core.agent.agent import Agent
from app.core.common.singleton import Singleton
from app.core.workflow.operator_config import OperatorConfig


class OperatorService(metaclass=Singleton):
    def __init__(self):
        self._registry = OperatorRegistry()

    def is_operator_registered(self, op_id: str) -> bool:
        return self._registry.get(op_id) is not None

    def find_operator(self, op_id: str) -> Optional[OperatorConfig]:
        return self._registry.get(op_id)

    def get_operator_config(self, op_id: str) -> Optional[OperatorConfig]:
        return self._registry.get(op_id)

    def create_operator_instance(self, operator_name: str, operator_id: str, task: str):
        config = self._registry.get(operator_id)
        if config is None:
            raise ValueError(f"Operator {operator_name} not registered.")
        from app.core.workflow.operator import Operator
        return Operator(config=config)

    def create_evaluator_instance(self, operator_name: str, operator_id: str):
        config = self._registry.get(operator_id)
        if config is None:
            raise ValueError(f"Evaluator {operator_name} not registered.")
        from app.core.workflow.eval_operator import EvalOperator
        return EvalOperator(config=config)
    """负责 Operator 的存储、检索、动态组合与克隆的全局服务。"""



    def register_operator(self, op: OperatorConfig):
        """注册 Operator 到全局池"""
        self._registry.register(op)

    def list_operators(self) -> List[OperatorConfig]:
        """列出所有 Operator"""
        return self._registry.all()

    #通过关键字获取某些op，但是我们缺少desc字段
    def find_by_keyword(self, keyword: str) -> List[OperatorConfig]:
        """按关键字查找（比如在指令或描述中搜索）"""
        return [
            op for op in self._registry.all()
            if keyword.lower() in op.instruction.lower()
               or keyword.lower() in getattr(op, "desc", "").lower()
        ]

    #clone一个operator，并且可以对其有一定的修改
    def clone_operator(self, op_id: str, **overrides) -> Optional[OperatorConfig]:
        """克隆一个 operator（支持参数覆盖）"""
        base_op = self._registry.get(op_id)
        if not base_op:
            return None
        # 浅拷贝 + 局部覆盖
        new_op = OperatorConfig(
            name=base_op.name,
            instruction=overrides.get("instruction", base_op.instruction),
            output_schema=overrides.get("output_schema", base_op.output_schema),
            actions=overrides.get("actions", base_op.actions.copy()),
        )
        return new_op

    def build_dynamic_workflow(self, strategy: str = "random", count: int = 2) -> List[List[OperatorConfig]]:
        """按策略自动生成 workflow"""
        ops = self._registry.all()
        if not ops:
            return []
        if strategy == "random":
            selected = random.sample(ops, min(count, len(ops)))
            return [selected]
        # 未来可以接入 Reasoner 或 Planner 策略
        #当前测略仍然还未接入
        return [[ops[0]]]


    def register_operator_for_agent(self, op: OperatorConfig, agent: Agent):
        self._registry.register_operator_for_agent(op,agent)

    def get_operator_for_agent(self, agent: Agent) -> Optional[List[OperatorConfig]]:
        return self._registry.get_operators_for_agent(agent)


class OperatorRegistry:
    # 使用dict保存op，用说明instruction作为key
    def __init__(self):
        self._operators: Dict[str, OperatorConfig] = {}
        self._operator_map: Dict[str, List[OperatorConfig]] = {}

    def register(self, op: OperatorConfig):
        if op.id not in self._operators:
            self._operators[op.id] = op

    def get(self, op_id: str) -> Optional[OperatorConfig]:
        return self._operators.get(op_id)

    def all(self) -> List[OperatorConfig]:
        return list(self._operators.values())

    def register_operator_for_agent(self, op: OperatorConfig, agent: Agent):
        if agent.get_profile().name not in self._operator_map:
            self._operator_map[agent.get_profile().name] = []
        self._operator_map[agent.get_profile().name].append(op)
        self.register(op)

    def get_operators_for_agent(self, agent: Agent) -> Optional[List[OperatorConfig]]:
        if agent.get_profile().name not in self._operator_map:
             return None
        return self._operator_map[agent.get_profile().name]


