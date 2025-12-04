import networkx as nx
from typing import Dict, Any

from app.core.service.operator_service import OperatorService
from app.core.workflow.operator import Operator
from app.core.workflow.eval_operator import EvalOperator


class DynamicWorkflowParseError(ValueError):
    """动态 Workflow 解析错误"""
    pass

class WorkflowParser:

    def parse_dynamic_workflow(self,raw: dict[str, Any]):
        """
        将 LLM 构造的精简 JSON 转为:
        - operators: Dict[str, Operator]
        - graph: nx.DiGraph
        - evaluator: Optional[Operator]

        期望 JSON 结构（精简版）：
        {
          "workflow": {
            "operators": [
              {
                "id": "op1",
                "name": "retrieve_knowledge",
                "task": "负责 xxx",
                "next": ["op2"]
              },
              ...
            ],
            "evaluator": {
                "id": "eval1",
                "name": "simple_evaluator"
            }
          }
        }
        """

        if "workflow" not in raw:
            raise DynamicWorkflowParseError('Missing "workflow" key.')

        workflow = raw["workflow"]
        ops_raw = workflow.get("operators")

        if not isinstance(ops_raw, list) or len(ops_raw) == 0:
            raise DynamicWorkflowParseError('"workflow.operators" must be a non-empty list.')

        operator_service = OperatorService.instance

        # ------------------------------------------------------------
        # 1) 创建 Operators（用 operator_service 检查合法性）
        # ------------------------------------------------------------
        operators: Dict[str, Operator] = {}
        operator_task_dict: Dict[str, Dict[str, Any]] = {}
        for idx, op in enumerate(ops_raw):
            if not isinstance(op, dict):
                raise DynamicWorkflowParseError(f"Operator at index {idx} must be an object.")

            op_id = op.get("id")
            op_name = op.get("name")
            op_task = op.get("task")
            op_next = op.get("next", [])

            # ---- 校验字段 ----
            if not isinstance(op_id, str) or not op_id.strip():
                raise DynamicWorkflowParseError(f"Operator at index {idx} missing valid 'id'.")

            if not isinstance(op_name, str) or not operator_service.is_operator_registered(op_id):
                raise DynamicWorkflowParseError(
                    f"Unknown operator name: {op_name!r} (not registered in OperatorService)."
                )

            if not isinstance(op_task, str) or not op_task.strip():
                raise DynamicWorkflowParseError(f"Operator {op_id} missing valid 'task' field.")

            if not isinstance(op_next, list):
                raise DynamicWorkflowParseError(f"'next' for operator {op_id} must be list.")

            # ---- 构建 Operator 实例（不创建自定义类，用你现有的 Operator） ----
            operator: Operator = operator_service.create_operator_instance(
                operator_name=op_name,
                operator_id=op_id,
                task=op_task
            )

            operators[op_id] =  operator
            operator_task_dict[op_id] = {"operator": operator, "task": op_task}

        # ------------------------------------------------------------
        # 2) 构建 DAG（nx.DiGraph）
        # ------------------------------------------------------------
        graph = nx.DiGraph()

        # 添加节点
        for op_id, operator in operators.items():
            graph.add_node(op_id, operator=operator)


        # 添加边
        for op in ops_raw:
            op_id = op["id"]
            for nxt in op.get("next", []):
                if nxt not in operators:
                    raise DynamicWorkflowParseError(
                        f"Operator {op_id!r} references unknown next node {nxt!r}."
                    )
                graph.add_edge(op_id, nxt)

        # 校验 DAG
        if not nx.is_directed_acyclic_graph(graph):
            raise DynamicWorkflowParseError("Dynamic workflow graph is not a DAG.")

        # ------------------------------------------------------------
        # 3) evaluator（可选）
        # ------------------------------------------------------------
        evaluator_raw = workflow.get("evaluator")
        evaluator = None

        if evaluator_raw:
            eval_id = evaluator_raw.get("id")
            eval_name = evaluator_raw.get("name")

            if not isinstance(eval_name, str) or not operator_service.is_operator_registered(eval_id):
                raise DynamicWorkflowParseError(f"Unknown evaluator operator name: {eval_name}")

            evaluator = operator_service.create_evaluator_instance(
                operator_name=eval_name,
                operator_id=eval_id
            )

        # ------------------------------------------------------------
        # 4) 返回结果
        # ------------------------------------------------------------
        return {
            "operators_tasks_dict": operator_task_dict,
            "graph": graph,
            "evaluator": evaluator,
        }