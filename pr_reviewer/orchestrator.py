"""Fan-out: run every specialist on the same diff concurrently.

Guarantees:
- Specialists run in parallel, bounded by ``max_concurrency``.
- One reviewer failing (exception, timeout, agent error) never takes down
  the others; its failure is recorded on its ``ReviewResult``.
- Results come back in the same order as the specialists were given.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Callable

from .agents import Specialist, run_reviewer
from .diff_source import Diff
from .models import ReviewResult
from .runner import AgentRunner

# Progress hook: (reviewer name, event, result-or-None). Events: "start", "done".
ProgressCallback = Callable[[str, str, "ReviewResult | None"], None]


@dataclass
class OrchestratorConfig:
    max_concurrency: int = 4
    reviewer_timeout_s: float = 600.0


async def _run_one(
    specialist: Specialist,
    diff: Diff,
    runner: AgentRunner,
    config: OrchestratorConfig,
    semaphore: asyncio.Semaphore,
    on_progress: ProgressCallback | None,
) -> ReviewResult:
    async with semaphore:
        if on_progress:
            on_progress(specialist.name, "start", None)
        started = time.monotonic()
        try:
            result = await asyncio.wait_for(
                run_reviewer(specialist, diff, runner), timeout=config.reviewer_timeout_s
            )
        except asyncio.TimeoutError:
            result = ReviewResult(specialist.name, error=f"timed out after {config.reviewer_timeout_s:g}s")
        except asyncio.CancelledError:
            raise  # let cancellation of the whole review propagate
        except Exception as exc:  # isolate: one crashed agent must not sink the review
            result = ReviewResult(specialist.name, error=f"{type(exc).__name__}: {exc}")
        if not result.duration_ms:
            result.duration_ms = int((time.monotonic() - started) * 1000)
        if on_progress:
            on_progress(specialist.name, "done", result)
        return result


async def run_reviewers(
    diff: Diff,
    specialists: list[Specialist],
    runner: AgentRunner,
    config: OrchestratorConfig | None = None,
    on_progress: ProgressCallback | None = None,
) -> list[ReviewResult]:
    if diff.is_empty:
        raise ValueError("diff is empty: nothing to review")
    if not specialists:
        raise ValueError("no reviewers selected")
    config = config or OrchestratorConfig()
    semaphore = asyncio.Semaphore(max(1, config.max_concurrency))
    return list(
        await asyncio.gather(
            *(_run_one(s, diff, runner, config, semaphore, on_progress) for s in specialists)
        )
    )
