import time
from typing import Dict, Any, Optional

class SensoryMemory:
    """
    Sensory Memory represents the volatile, immediate layer of an agent's memory.
    It captures the raw sensory inputs (e.g., user messages, environmental observations,
    active sub-goals) before they are processed, filtered, and moved into Short-Term Memory.
    """
    def __init__(self):
        self.raw_observation: Optional[str] = None
        self.active_goal: Optional[str] = None
        self.timestamp: float = 0.0
        self.metadata: Dict[str, Any] = {}

    def update(self, raw_input: str, active_goal: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        """
        Register a new sensory event.
        """
        self.raw_observation = raw_input
        self.active_goal = active_goal
        self.timestamp = time.time()
        self.metadata = metadata or {}

    def clear(self):
        """
        Flush sensory memory.
        """
        self.raw_observation = None
        self.active_goal = None
        self.timestamp = 0.0
        self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_observation": self.raw_observation,
            "active_goal": self.active_goal,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }
