from dataclasses import dataclass


@dataclass
class KnowledgeConfig:
    """Knowledge loading configuration."""

    chunk_size: int = 512
    chunk_overlap: int = 50

    def to_dict(self):
        """Convert to dict."""
        return self.__dict__
