from abc import ABC, abstractmethod
import threading
from typing import Dict, List

from app.core.agent.agent import AgentConfig
from app.core.agent.expert import Expert


class LeaderState(ABC):

    def __init__(self):
        self._expert_instances: Dict[str, Expert] = {}  # expert_id -> instance
        self._expert_creation_lock: threading.Lock = threading.Lock()

    @abstractmethod
    def get_expert_by_name(self, expert_name: str) -> Expert:
        """"""

    @abstractmethod
    def get_expert_by_id(self, expert_id: str) -> Expert:
        """ """

    @abstractmethod
    def list_experts(self) -> List[Expert]:
        """ """

    @abstractmethod
    def create_expert(self, agent_config: AgentConfig) -> Expert:
        """Add an expert profile to the registry."""

    @abstractmethod
    def add_expert(self, expert: Expert) -> None:
        """Add the expert"""

    @abstractmethod
    def remove_expert(self, expert_id: str) -> None:
        """Remove the expert"""
