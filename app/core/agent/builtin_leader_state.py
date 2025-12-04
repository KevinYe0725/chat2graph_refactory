from typing import List

from app.core.agent.agent import AgentConfig
from app.core.agent.expert import Expert
from app.core.agent.leader_state import LeaderState


class BuiltinLeaderState(LeaderState):


    def get_expert_by_name(self, expert_name: str) -> Expert:

        for expert in self._expert_instances.values():
            if expert.get_profile().name == expert_name:
                return expert
        raise ValueError(f"Expert {expert_name} not exists in the leader state.")

    def get_expert_by_id(self, expert_id: str) -> Expert:
        return self._expert_instances[expert_id]

    def list_experts(self) -> List[Expert]:
        return list(self._expert_instances.values())

    def create_expert(self, agent_config: AgentConfig) -> Expert:
        with self._expert_creation_lock:
            expert = Expert(agent_config=agent_config)
            expert_id = expert.get_id()
            self._expert_instances[expert_id] = expert
            return expert

    def add_expert(self, expert: Expert) -> None:
        self._expert_instances[expert.get_id()] = expert

    def remove_expert(self, expert_id: str) -> None:
        self._expert_instances.pop(expert_id, None)
