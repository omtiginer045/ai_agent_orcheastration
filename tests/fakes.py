"""A scripted AgentRunner for tests: no network, no API spend."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from pr_reviewer.runner import AgentResponse


@dataclass
class FakeRunner:
    """Answers each call with ``respond(system_prompt, prompt)``.

    ``respond`` may return an AgentResponse, or raise to simulate a crash.
    Every call is recorded in ``calls``.
    """

    respond: Callable[[str, str], AgentResponse]
    delay: float = 0.0
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def run(self, *, system_prompt, prompt, output_schema, cwd: Path, effort="medium"):
        self.calls.append(
            {"system_prompt": system_prompt, "prompt": prompt, "schema": output_schema, "cwd": cwd, "effort": effort}
        )
        if self.delay:
            await asyncio.sleep(self.delay)
        return self.respond(system_prompt, prompt)


def finding(file="app.py", line=1, severity="medium", title="t", description="d", suggestion="s"):
    return {"file": file, "line": line, "severity": severity, "title": title,
            "description": description, "suggestion": suggestion}
