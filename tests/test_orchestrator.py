import asyncio
import time
from pathlib import Path

import pytest

from pr_reviewer.agents import get_specialists
from pr_reviewer.diff_source import Diff
from pr_reviewer.orchestrator import OrchestratorConfig, run_reviewers
from pr_reviewer.runner import AgentResponse

from .fakes import finding

DIFF = Diff("diff --git a/app.py b/app.py\n+x = 1\n", Path("/repo"))


def _name_of(system_prompt: str) -> str:
    """Which specialist a call belongs to, recovered from its focus text."""
    for s in get_specialists():
        if s.focus in system_prompt:
            return s.name
    raise AssertionError("unknown specialist prompt")


class ScriptedRunner:
    """Per-specialist behavior: delay, crash, or a finding titled with its name."""

    def __init__(self, delay=0.0, crash=(), hang=(), agent_error=()):
        self.delay, self.crash, self.hang, self.agent_error = delay, set(crash), set(hang), set(agent_error)
        self.active = self.peak = 0

    async def run(self, *, system_prompt, prompt, output_schema, cwd, effort="medium"):
        name = _name_of(system_prompt)
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            await asyncio.sleep(10 if name in self.hang else self.delay)
            if name in self.crash:
                raise RuntimeError("boom")
            if name in self.agent_error:
                return AgentResponse(data=None, error="overloaded")
            return AgentResponse(data={"findings": [finding(title=name)]}, cost_usd=0.01)
        finally:
            self.active -= 1


async def test_runs_in_parallel_and_preserves_order():
    runner = ScriptedRunner(delay=0.2)
    t0 = time.monotonic()
    results = await run_reviewers(DIFF, get_specialists(), runner)
    elapsed = time.monotonic() - t0

    assert elapsed < 0.6  # 4 x 0.2s sequentially would be 0.8s
    assert runner.peak == 4
    assert [r.reviewer for r in results] == ["security", "performance", "readability", "testing"]
    assert all(r.ok and r.findings[0].title == r.reviewer for r in results)


async def test_concurrency_limit():
    runner = ScriptedRunner(delay=0.05)
    await run_reviewers(DIFF, get_specialists(), runner, OrchestratorConfig(max_concurrency=2))
    assert runner.peak == 2


async def test_failures_are_isolated():
    runner = ScriptedRunner(crash={"security"}, hang={"performance"}, agent_error={"testing"})
    results = await run_reviewers(DIFF, get_specialists(), runner, OrchestratorConfig(reviewer_timeout_s=0.2))
    by = {r.reviewer: r for r in results}

    assert by["security"].error == "RuntimeError: boom"
    assert by["performance"].error.startswith("timed out")
    assert by["testing"].error == "overloaded"
    assert by["readability"].ok and len(by["readability"].findings) == 1


async def test_progress_events():
    events = []
    await run_reviewers(DIFF, get_specialists(["security", "testing"]), ScriptedRunner(),
                        on_progress=lambda name, ev, res: events.append((name, ev, res is not None)))
    assert sorted(events) == [("security", "done", True), ("security", "start", False),
                              ("testing", "done", True), ("testing", "start", False)]


async def test_rejects_empty_diff_and_no_reviewers():
    with pytest.raises(ValueError, match="empty"):
        await run_reviewers(Diff("  \n", Path(".")), get_specialists(), ScriptedRunner())
    with pytest.raises(ValueError, match="no reviewers"):
        await run_reviewers(DIFF, [], ScriptedRunner())
