from pathlib import Path

import pytest

from pr_reviewer.agents import get_specialists, run_reviewer
from pr_reviewer.agents.reviewer import build_prompt, build_system_prompt
from pr_reviewer.diff_source import Diff
from pr_reviewer.models import REVIEW_OUTPUT_SCHEMA, Severity
from pr_reviewer.runner import AgentResponse

from .fakes import FakeRunner, finding

DIFF = Diff("diff --git a/app.py b/app.py\n+eval(user_input)\n", Path("/repo"))


def test_get_specialists_default_and_filter():
    assert [s.name for s in get_specialists()] == ["security", "performance", "readability", "testing"]
    assert [s.name for s in get_specialists(["testing", "security"])] == ["testing", "security"]


def test_get_specialists_unknown():
    with pytest.raises(ValueError, match="unknown reviewer"):
        get_specialists(["style"])


def test_prompts_contain_focus_and_diff():
    sec = get_specialists(["security"])[0]
    sp = build_system_prompt(sec)
    assert sec.focus in sp and "injection" in sp and "untrusted" in sp
    p = build_prompt(DIFF)
    assert "- app.py" in p and "eval(user_input)" in p


async def test_run_reviewer_parses_findings():
    runner = FakeRunner(lambda s, p: AgentResponse(
        data={"findings": [finding(severity="critical", title="eval on input")]}, cost_usd=0.02, duration_ms=50))
    sec = get_specialists(["security"])[0]
    r = await run_reviewer(sec, DIFF, runner)

    assert r.ok and r.cost_usd == 0.02
    assert r.findings[0].severity is Severity.CRITICAL
    assert r.findings[0].category == "security"
    call = runner.calls[0]
    assert call["schema"] is REVIEW_OUTPUT_SCHEMA
    assert call["cwd"] == Path("/repo") and call["effort"] == "high"


async def test_run_reviewer_keeps_good_findings_when_one_is_malformed():
    runner = FakeRunner(lambda s, p: AgentResponse(data={"findings": [finding(), {"file": "x"}]}))
    r = await run_reviewer(get_specialists(["readability"])[0], DIFF, runner)
    assert len(r.findings) == 1
    assert "1 malformed" in r.error


async def test_run_reviewer_propagates_agent_error():
    runner = FakeRunner(lambda s, p: AgentResponse(data=None, error="rate limited", cost_usd=0.01))
    r = await run_reviewer(get_specialists(["performance"])[0], DIFF, runner)
    assert not r.ok and r.error == "rate limited" and r.findings == [] and r.cost_usd == 0.01
