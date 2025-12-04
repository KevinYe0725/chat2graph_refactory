from dataclasses import dataclass, field
from typing import List, Dict
from uuid import uuid4

from app.core.toolkit.action import Action


@dataclass
class OperatorConfig:
    """Operator configuration."""
    name: str
    instruction: str
    actions: List[Action]
    id: str = field(default_factory=lambda: str(uuid4()))
    output_schema: str = ""
    threshold: float = 0.5
    hops: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "instruction": self.instruction,
            "actions": self.actions,
            "threshold": self.threshold,
            "hops": self.hops,
            "output_schema": self.output_schema,
            "id": self.id,
        }