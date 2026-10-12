from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvalRecord:
    record_id: str
    input: str
    expected: str | None = None
    context: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
