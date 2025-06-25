# agent_base.py
from typing import Any

class AgentBase:
    def __init__(self, name: str):
        self.name = name

    def run(self, input_data: Any, stage: str = "") -> Any:
        raise NotImplementedError("Agents must implement the run method.")
