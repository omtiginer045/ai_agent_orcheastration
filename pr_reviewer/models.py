"""Data contracts shared by every agent in the pipeline.

Agents talk to each other only through these types. Each reviewer returns
``Finding`` objects (validated from the JSON its model produced), the judge
returns a ``FinalReport``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

    @property
    def rank(self) -> int:
        """Lower is more severe; used for sorting."""
        return list(Severity).index(self)


@dataclass(frozen=True)
class Finding:
    """One issue a reviewer found in the diff."""

    file: str
    line: int | None
    severity: Severity
    title: str
    description: str
    suggestion: str = ""
    category: str = ""  # which specialist produced it, e.g. "security"

    @classmethod
    def from_dict(cls, data: dict[str, Any], category: str = "") -> "Finding":
        line = data.get("line")
        return cls(
            file=str(data["file"]),
            line=int(line) if line not in (None, "") else None,
            severity=Severity(str(data["severity"]).lower()),
            title=str(data["title"]).strip(),
            description=str(data["description"]).strip(),
            suggestion=str(data.get("suggestion") or "").strip(),
            category=str(data.get("category") or category),
        )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value
        return d


@dataclass
class ReviewResult:
    """Output of one specialist run, successful or not."""

    reviewer: str
    findings: list[Finding] = field(default_factory=list)
    error: str | None = None
    cost_usd: float = 0.0
    duration_ms: int = 0

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass
class FinalReport:
    """What the judge hands back after merging every reviewer's output."""

    summary: str
    findings: list[Finding]
    verdict: str  # "approve" | "comment" | "request_changes"
    reviewer_results: list[ReviewResult] = field(default_factory=list)
    judge_cost_usd: float = 0.0

    @property
    def total_cost_usd(self) -> float:
        return self.judge_cost_usd + sum(r.cost_usd for r in self.reviewer_results)


# JSON Schema the reviewer agents must answer with (Agent SDK ``output_format``).
FINDING_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "file": {"type": "string"},
        "line": {"type": ["integer", "null"]},
        "severity": {"type": "string", "enum": [s.value for s in Severity]},
        "title": {"type": "string"},
        "description": {"type": "string"},
        "suggestion": {"type": "string"},
    },
    "required": ["file", "line", "severity", "title", "description", "suggestion"],
    "additionalProperties": False,
}

REVIEW_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "findings": {"type": "array", "items": FINDING_SCHEMA},
    },
    "required": ["findings"],
    "additionalProperties": False,
}
