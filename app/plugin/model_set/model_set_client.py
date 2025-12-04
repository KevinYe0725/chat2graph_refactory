import json
from typing import List, Optional

from dbgpt.model.utils.llm_utils import parse_model_request

from app.core.common.type import MessageSourceType

from app.core.model.llm_model import LLMModel
from app.core.prompt.model_service import FUNC_CALLING_PROMPT
from dbgpt.core import ModelRequest, SystemMessage, BaseMessage

from app.core.model.message import ModelMessage
from app.core.model.task import ToolCallContext
from app.core.reasoner.model_service import ModelService
from app.core.sdk.wrapper.model_wrapper import ModelWrapper
from app.core.toolkit.action_model_request import ActionModelRequest
from app.core.toolkit.tool import Tool, FunctionCallResult

"""
WorkflowMessage(
    job_id="job_1234",
    timestamp=1730000000000,
    payload={
        "task_goal": "分析图数据库结构并生成可视化报告",
        "task_context": "数据库包含两类节点 User 与 Company，上一阶段已提取关系。",
        "action_input": {
            "instruction": "请执行 SchemaUnderstanding 以提取节点与边的模式。",
            "input_data": {
                "graph_service": "Neo4jService",
                "schema_limit": 100
            }
        },
        "summary": "数据库包含两类节点 User 与 Company，上一阶段已提取关系。",
        "combined_context": "【任务目标】分析图数据库结构并生成可视化报告\n"
                             "【上下文摘要】数据库包含两类节点 User 与 Company，上一阶段已提取关系。\n"
                             "【第一个Action输入】{'instruction': '请执行 SchemaUnderstanding 以提取节点与边的模式。', 'input_data': {'graph_service': 'Neo4jService', 'schema_limit': 100}}\n"
                             "【原始上下文】\n图数据库包含节点 User, Company\n上一个专家提取了节点关系\n注意节点重复率过高时要归并",
        "timestamp": 1730000000000
    }
)

"""

class ModelSetClient(ModelService):

    def __init__(self, model_name: str):
        super().__init__()
        self._model: LLMModel = self.get_model(model_name)


    async def generate(self,
                       sys_prompt: str,
                       messages: List[ModelMessage],
                       tools: Optional[List[Tool]] = None,
                       tool_call_ctx: Optional[ToolCallContext] = None,
    ) -> ModelMessage:
        message:ModelMessage = messages[0]
        inputs =  json.loads(message.get_payload())

        task: str = inputs["action_input"]["instruction"]
        prev_outputs = inputs["action_input"]["input_data"]
        summary: str = inputs["summary"]
        combined_context: str = inputs["combined_context"]

        sys_prompt = self._model.system_prompt.format(toos = tools,task = task,summary = summary,prev_outputs = prev_outputs)
        prompt =  self.parse_model_request(sys_prompt,task).payload
        model_wrapper: ModelWrapper = ModelWrapper(self._model)
        #注意这里的result需不需要换成带有更多字段的格式
        result = await model_wrapper.generate(prompt)
        func_call_results: Optional[List[FunctionCallResult]] = None
        if tools:
            func_call_results = await self.call_function(
                tools=tools, model_response_text=result, tool_call_ctx=tool_call_ctx
            )

        response: ModelMessage = self._parse_model_response(
            model_response=result,
            messages=messages,
            func_call_results=func_call_results,
        )

        return response

    def _parse_model_response(
        self,
        model_response: str,
        messages: List[ModelMessage],
        func_call_results: Optional[List[FunctionCallResult]] = None,
    ) -> ModelMessage:
        """Parse model response to agent message."""

        # determine the source type of the response
        if messages[-1].get_source_type() == MessageSourceType.MODEL:
            source_type = MessageSourceType.MODEL
        elif messages[-1].get_source_type() == MessageSourceType.ACTOR:
            source_type = MessageSourceType.THINKER
        else:
            source_type = MessageSourceType.ACTOR

        response = ModelMessage(
            payload=model_response,
            job_id=messages[-1].get_job_id(),
            step=messages[-1].get_step() + 1,
            source_type=source_type,
            function_calls=func_call_results,
        )

        return response

    def parse_model_request(self, sys_prompt,task) -> ActionModelRequest:
        model_reuqest =  ActionModelRequest(sys_prompt=sys_prompt,task=task)
        return model_reuqest


