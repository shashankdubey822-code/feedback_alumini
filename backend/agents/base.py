from abc import ABC, abstractmethod
from typing import Any, Dict

class BaseAgent(ABC):
    """
    Base class for all 15 subagents in the ultra-deep feedback analysis system.
    """
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the agent's specific task.
        :param payload: Input data dictionary
        :return: Processed data dictionary or status
        """
        pass

class SupervisorAgent(BaseAgent):
    """
    Base class for the 2 supervisor agents that orchestrate the workflow.
    """
    
    def __init__(self, name: str, description: str):
        super().__init__(name, description)
        self.subagents = []

    def register_subagent(self, agent: BaseAgent):
        """Register a subagent under this supervisor."""
        self.subagents.append(agent)

    @abstractmethod
    def orchestrate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Orchestrate the registered subagents in sequence or parallel.
        """
        pass

    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.orchestrate(payload)
