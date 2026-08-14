"""Record types for the memory store."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Memory:
    id: int
    content: str
    tags: list[str] = field(default_factory=list)
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SearchResult:
    memory: Memory
    score: float

    def to_dict(self) -> dict[str, Any]:
        payload = self.memory.to_dict()
        payload["score"] = round(self.score, 4)
        return payload
