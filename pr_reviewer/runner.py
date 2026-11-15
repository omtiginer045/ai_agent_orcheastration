"""The single seam between our orchestration code and the LLM.

Every agent (specialists and judge) goes through an ``AgentRunner``. The real
one drives the Claude Agent SDK; tests swap in a fake so the orchestration
logic can be exercised without network calls or API spend.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

DEFAULT_MODEL = "claude-opus-5-5"

# Reviewers may look around the repo for context, but never modify it or run commands.
READ_ONLY_TOOLS = ["Read", "Grep", "Glob"]


@dataclass
class AgentResponse:
    data: dict[str, Any] | None  # structured output matching the requested schema
    cost_usd: float = 0.0
    duration_ms: int = 0
    num_turns: int = 0
    error: str | None = None


class AgentRunner(Protocol):
    async def run(
        self,
        *,
        system_prompt: str,
        prompt: str,
        output_schema: dict[str, Any],
        cwd: Path,
        effort: str = "medium",
    ) -> AgentResponse: ...


@dataclass
class ClaudeAgentRunner:
    """Runs one agent as a Claude Agent SDK ``query()`` with structured output."""

    model: str = DEFAULT_MODEL
    tools: list[str] = field(default_factory=lambda: list(READ_ONLY_TOOLS))
    max_turns: int = 20
    max_budget_usd: float | None = 1.0  # per agent run

    async def run(
        self,
        *,
        system_prompt: str,
        prompt: str,
        output_schema: dict[str, Any],
        cwd: Path,
        effort: str = "medium",
    ) -> AgentResponse:
        # Imported lazily so the rest of the package (and the tests) work
        # without the SDK's CLI being present.
        from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

        options = ClaudeAgentOptions(
            model=self.model,
            system_prompt=system_prompt,
            tools=self.tools,           # the only tools that exist for this agent
            allowed_tools=self.tools,   # ...and they run without permission prompts
            cwd=str(cwd),
            max_turns=self.max_turns,
            max_budget_usd=self.max_budget_usd,
            effort=effort,  # type: ignore[arg-type]
            output_format={"type": "json_schema", "schema": output_schema},
            setting_sources=[],  # isolation: ignore the reviewed repo's .claude settings
        )

        result: ResultMessage | None = None
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, ResultMessage):
                result = message

        if result is None:
            return AgentResponse(data=None, error="agent produced no result message")

        error = None
        if result.is_error:
            error = "; ".join(result.errors or []) or f"agent failed ({result.subtype})"
        elif not isinstance(result.structured_output, dict):
            error = "agent did not return structured output"

        return AgentResponse(
            data=result.structured_output if error is None else None,
            cost_usd=result.total_cost_usd or 0.0,
            duration_ms=result.duration_ms,
            num_turns=result.num_turns,
            error=error,
        )
