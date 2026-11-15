"""The whole review in one call: fan out to specialists, fan in through the judge."""

from __future__ import annotations

from .agents import Specialist, get_specialists, run_judge
from .diff_source import Diff
from .models import FinalReport
from .orchestrator import OrchestratorConfig, ProgressCallback, run_reviewers
from .runner import AgentRunner


async def review(
    diff: Diff,
    runner: AgentRunner,
    specialists: list[Specialist] | None = None,
    config: OrchestratorConfig | None = None,
    on_progress: ProgressCallback | None = None,
) -> FinalReport:
    results = await run_reviewers(diff, specialists or get_specialists(), runner, config, on_progress)
    if on_progress:
        on_progress("judge", "start", None)
    report = await run_judge(diff, results, runner)
    if on_progress:
        on_progress("judge", "done", None)
    return report
