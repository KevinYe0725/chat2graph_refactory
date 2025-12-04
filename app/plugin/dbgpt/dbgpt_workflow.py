from typing import Dict, List, Optional, Tuple, Any

from app.core.central_orchestrator.central_orchestrator import CentralOrchestrator
from app.core.central_orchestrator.version_management_center.record import WorkflowExecutionRecord
from app.core.central_orchestrator.version_management_center.vmc_provider import vmc
from app.core.workflow.operator import Operator

from app.core.workflow.eval_operator import EvalOperator
from dbgpt.core.awel import (  # type: ignore
    DAG,
    InputOperator,
    JoinOperator,
    SimpleCallDataInputSource,
)
import networkx as nx  # type: ignore

from app.core.common.async_func import run_async_function
from app.core.model.job import Job
from app.core.model.message import WorkflowMessage
from app.core.reasoner.reasoner import Reasoner
from app.core.workflow.workflow import Workflow
from app.plugin.dbgpt.dbgpt_map_operator import DbgptMapOperator


class DbgptWorkflow(Workflow):
    """DB-GPT workflow"""

    def __init__(self, operator_graph: Optional[nx.DiGraph] = None, evaluator:Optional[EvalOperator] = None, operator_task_dict:Optional[dict[str,Any]] = None):
        self._tail_map_op: Optional[DbgptMapOperator] = None
        self._reasoner: Optional[Reasoner] = None
        super().__init__()
        if operator_task_dict:
            self._operator_graph = operator_graph
        if operator_task_dict:
            self._evaluator = evaluator
        if operator_task_dict:
            self._operator_task_dict = operator_task_dict
        self._last_operator_outputs = {}
        self._last_job = None
        self._last_previous_expert_outputs = []
        self._last_lesson = None
        self._stopped = False


    def _build_workflow(self, reasoner: Reasoner) -> DbgptMapOperator:
        """Build the DB-GPT workflow."""
        if reasoner is None:
            raise ValueError("Reasoner is required to build the workflow.")
        # 缓存当前 reasoner，方便手动执行 workflow 时使用
        self._reasoner = reasoner
        if self._operator_graph.number_of_nodes() == 0:
            raise ValueError("There is no operator in the workflow.")
        #融合流水线上的消息
        def _merge_workflow_messages(
            *args,
        ) -> Tuple[Job, List[WorkflowMessage], List[WorkflowMessage], Optional[str]]:
            """Combine the outputs from the previous MapOPs and the InputOP."""
            job: Optional[Job] = None
            previous_expert_outputs: List[WorkflowMessage] = []
            previous_operator_outputs: List[WorkflowMessage] = []
            lesson: Optional[str] = None

            for arg in args:
                if isinstance(arg, tuple):
                    # the Tuple[Job, List[WorkflowMessage], Optional[str]] comes from
                    # the job assigned to expert, outputs of previous experts,
                    # and lesson learned (provided by the successor expert)
                    for item in arg:
                        if isinstance(item, Job):
                            job = item
                        elif isinstance(item, list):
                            if all(isinstance(i, WorkflowMessage) for i in item):
                                previous_expert_outputs.extend(item)
                            else:
                                raise ValueError(
                                    "Unknown data type in workflow message list: "
                                    f"{', '.join(str(type(i)) for i in item)}"
                                )
                        elif isinstance(item, str):
                            lesson = item
                        elif item is not None:
                            raise ValueError(f"Unknown data type in tuple: {type(item)}")
                elif isinstance(arg, WorkflowMessage):
                    # the workflow message from the previous operator
                    previous_operator_outputs.append(arg)
                else:
                    raise ValueError(f"Unknown data type: {type(arg)}")

            if not job:
                raise ValueError("No job provided in the workflow.")

            return job, previous_expert_outputs, previous_operator_outputs, lesson
        #根据operator graph创建一个完整的workflow
        with DAG("dbgpt_workflow"):
            #全局input的operator，所以其实每一个op都是需要这个作为前置的输入的
            input_op = InputOperator(input_source=SimpleCallDataInputSource())
            map_ops: Dict[str, DbgptMapOperator] = {}  # op_id -> map_op

            # 第一步：将所有的节点映射出来，然后添加上他们的reasoner
            for op_id in self._operator_graph.nodes():
                base_op = self._operator_graph.nodes[op_id]["operator"]
                map_ops[op_id] = DbgptMapOperator(operator=base_op, reasoner=reasoner)

            # 第二步，开始构建整个workflow
            for op_id in nx.topological_sort(self._operator_graph):
                current_op: DbgptMapOperator = map_ops[op_id]
                #返回当前点的入边
                in_edges = list(self._operator_graph.in_edges(op_id))
                #存在入边，说明不是起点，最起码需要全局input和前置节点的输出通过join的合并函数作为下一步的input
                if in_edges:
                    join_op = JoinOperator(combine_function=_merge_workflow_messages)

                    # connect all previous MapOPs to JoinOP
                    for src_id, _ in in_edges:
                        map_ops[src_id] >> join_op

                    input_op >> join_op

                    # connect the JoinOP to the current MapOP
                    join_op >> current_op
                else:
                    # if no previous MapOPs, connect the InputOP to the current MapOP
                    input_op >> current_op

            # third step: get the tail of the workflow which contains the operators
            # 第三步：确保只有一个尾operator，并且获取他本身
            tail_map_op_ids = [
                n for n in self._operator_graph.nodes() if self._operator_graph.out_degree(n) == 0
            ]
            assert len(tail_map_op_ids) == 1, "The workflow should have only one tail operator."
            _tail_map_op: DbgptMapOperator = map_ops[tail_map_op_ids[0]]

            # 第四步：在结尾添加一个evaluate op
            #依旧是和上面一样的组建操作
            if self._evaluator:
                eval_map_op = DbgptMapOperator(operator=self._evaluator, reasoner=reasoner)
                join_op = JoinOperator(combine_function=_merge_workflow_messages)

                _tail_map_op >> join_op
                input_op >> join_op
                join_op >> eval_map_op

                self._tail_map_op = eval_map_op
            else:
                self._tail_map_op = _tail_map_op
            #返回尾节点
            return self._tail_map_op


    #DAG图的反依赖驱动，只要尾节点call了，就会一步步递推依赖向前，然后最终实现从头节点开始驱动
    def _execute_workflow(
        self,
        workflow: DbgptMapOperator,
        job: Job,
        workflow_messages: Optional[List[WorkflowMessage]] = None,
        lesson: Optional[str] = None,
    ) -> WorkflowMessage:
        """Execute the workflow."""

        central_orchestrator = CentralOrchestrator.instance
        ctx = central_orchestrator.get_execution_context(job.assigned_expert_name)

        # 生成新的 workflow version & workflow span
        ctx.new_workflow_version()
        ctx.new_workflow_span()
        workflow_record = WorkflowExecutionRecord(
            workflow_version_id=ctx.workflow_version_id,
            expert_name=job.assigned_expert_name,
            trace_id=ctx.trace_id,
            span_id=ctx.workflow_span_id,
            operator_records=[]
        )
        ctx.current_workflow_record = workflow_record
        ans_msg:WorkflowMessage = run_async_function(self._execute_workflow_new_version, workflow, job, workflow_messages, lesson)
        final_workflow_record = ctx.current_workflow_record
        final_workflow_record.metadata["status"] = "success"

        vmc.log_workflow(final_workflow_record)
        return ans_msg

    async def _execute_workflow_new_version(self,
        workflow: DbgptMapOperator,
        job: Job,
        workflow_messages: Optional[List[WorkflowMessage]] = None,
        lesson: Optional[str] = None,) -> WorkflowMessage:
        """Execute the workflow."""

        self._stopped = False

        if self._operator_graph.number_of_nodes() == 0:
            raise ValueError("There is no operator in the workflow.")

        if self._reasoner is None:
            raise RuntimeError("Reasoner is not set. Make sure _build_workflow was called first.")

        # previous_expert_outputs 对应 _merge_workflow_messages 中的 previous_expert_outputs
        previous_expert_outputs: List[WorkflowMessage] = workflow_messages or []

        # 保存每个 operator 的输出，key 为 op_id
        operator_outputs: Dict[str, WorkflowMessage] = {}

        self._last_operator_outputs = operator_outputs
        self._last_job = job
        self._last_previous_expert_outputs = previous_expert_outputs
        self._last_lesson = lesson

        for op_id in nx.topological_sort(self._operator_graph):
            if self._stopped:
                raise RuntimeError("Workflow execution has been stopped.")
            await self._run_single_operator(
                op_id=op_id,
                job=job,
                operator_outputs=operator_outputs,
                previous_expert_outputs=previous_expert_outputs,
                lesson=lesson,
            )

        # 找到尾结点（下游没有其它 Operator 的结点）
        tail_map_op_ids = [
            n for n in self._operator_graph.nodes() if self._operator_graph.out_degree(n) == 0
        ]
        assert len(tail_map_op_ids) == 1, "The workflow should have only one tail operator."
        tail_op_id = tail_map_op_ids[0]

        tail_output = operator_outputs[tail_op_id]

        # 如果存在 evaluator，则再执行一次 evaluator，将其输出作为最终 WorkflowMessage
        if self._evaluator:
            eval_output: WorkflowMessage = await self._evaluator.execute(
                reasoner=self._reasoner,
                job=job,
                workflow_messages=list(operator_outputs.values()),
                previous_expert_outputs=previous_expert_outputs,
                lesson=lesson,
            )
            return eval_output

        return tail_output

    async def _run_single_operator(self, op_id, job, operator_outputs, previous_expert_outputs, lesson=None):
        base_op = self._operator_graph.nodes[op_id]["operator"]
        in_edges = list(self._operator_graph.in_edges(op_id))
        previous_operator_outputs = []
        for src_id, _ in in_edges:
            if src_id in operator_outputs:
                previous_operator_outputs.append(operator_outputs[src_id])
        op_output = await base_op.execute(
            reasoner=self._reasoner,
            job=job,
            workflow_messages=previous_operator_outputs,
            previous_expert_outputs=previous_expert_outputs,
            lesson=lesson,
        )
        operator_outputs[op_id] = op_output
        self._last_operator_outputs = operator_outputs
        return op_output

    async def rollback(self, to_op_id):
        if not self._last_job:
            raise RuntimeError("Cannot rollback: workflow has not been executed yet.")
        if to_op_id not in self._operator_graph.nodes():
            raise ValueError(f"Operator {to_op_id} does not exist in the workflow.")
        affected_nodes = set(nx.descendants(self._operator_graph, to_op_id))
        affected_nodes.add(to_op_id)
        operator_outputs = dict(self._last_operator_outputs)
        self._stopped = False
        for op_id in nx.topological_sort(self._operator_graph):
            if op_id not in affected_nodes:
                continue
            if self._stopped:
                raise RuntimeError("Workflow execution has been stopped during rollback.")
            await self._run_single_operator(
                op_id=op_id,
                job=self._last_job,
                operator_outputs=operator_outputs,
                previous_expert_outputs=self._last_previous_expert_outputs,
                lesson=self._last_lesson,
            )
        self._last_operator_outputs = operator_outputs
        tail_ids = [n for n in self._operator_graph.nodes() if self._operator_graph.out_degree(n) == 0]
        tail_id = tail_ids[0]
        tail_output = operator_outputs[tail_id]
        if self._evaluator:
            eval_output = await self._evaluator.execute(
                reasoner=self._reasoner,
                job=self._last_job,
                workflow_messages=list(operator_outputs.values()),
                previous_expert_outputs=self._last_previous_expert_outputs,
                lesson=self._last_lesson,
            )
            return eval_output
        return tail_output

    def stop(self):
        self._stopped = True
