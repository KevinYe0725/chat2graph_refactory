import json
from typing import Any, Optional, Dict

from app.core.model.task import Task

from app.core.agent.agent import Agent, AgentConfig
from app.core.model.message import AgentMessage
from app.core.prompt.reasoner import SUPERVISOR_PROMPT_TEMPLATE
from app.core.reasoner.reasoner import Reasoner
from app.core.reasoner.simple_reasoner import SimpleReasoner

"""
"expert_name": "...",
                "expert_goal": "...",
                "operator_id": "...",
                "operator_name": "...",
                "operator_task": "...",
                "operator_output": "...",
                "operator_status": "success or failed",

                "predecessors": ["op1"],
                "successors": ["op3"]
            
"""
# 根据该审查节点
class Supervisor(Agent):
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.reasoner = SimpleReasoner()

    def execute(self, agent_message: AgentMessage, retry_count: int = 0) -> Any:
        context: Dict[str, Any] = self._build_context()
        payload: dict[str, Any] = json.loads(agent_message.get_payload())
        prompt = SUPERVISOR_PROMPT_TEMPLATE.format(
            role = context.get("role"),
            expert_name = payload.get("expert_name"),
            expert_goal = payload.get("expert_goal"),
            operator_id = payload.get("operator_id"),
            operator_name = payload.get("operator_name"),
            operator_task = payload.get("operator_task"),
            operator_output = payload.get("operator_output"),
            operator_status = payload.get("operator_status"),
            predecessors = payload.get("predecessors"),
            successors = payload.get("successors"),
        )
        response = self.reasoner.generate(prompt)
    # 构建task，以用于告诉他要supervisor他需要做什么，得获取到某个action的相关信息，所以需要注册好的action🤔
    # 得先去完成构建流程才可以做这些

    # context 需要包含role，
    def _build_context(self) -> Dict[str, Any]:
        context: Dict[str, Any] = {"role": "supervisor"}
        return context
