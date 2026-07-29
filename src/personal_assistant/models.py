from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class AgentResponse:
    agent: str
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    suggestions: list[str] = field(default_factory=list)
    requires_confirmation: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
