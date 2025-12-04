from typing import Dict, Any


class ActionModelRequest:
    def __init__(
        self,
        sys_prompt: str,
        task: str,
    ):
        self._payload = [
            {"role": "system","content": sys_prompt},
            {"role": "user" ,"content": task}
        ]

    @property
    def payload(self) -> list[dict[str, str]]:
        return self._payload