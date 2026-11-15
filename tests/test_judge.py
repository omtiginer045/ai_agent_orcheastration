import json
from pathlib import Path

from pr_reviewer.agents.judge import JUDGE_OUTPUT_SCHEMA, fallback_merge, run_judge, verdict_for
from pr_reviewer.diff_source import Diff
from pr_reviewer.models import Finding, ReviewResult, Severity
from pr_reviewer.report import to_json, to_markdown
from pr_reviewer.runner import AgentResponse

from .fakes import FakeRunner, finding

DIFF = Diff("diff --git a/app.py b/app.py\n+q = f'SELECT {x}'\n", Path("/repo"))


def F(sev, title="t", file="app.py", line=1, cat="security"):
    return Finding(file, line, Severity(sev), title, "d", "s", cat)


RESULTS = [
    ReviewResult("security", [F("high", "SQL injection")], cost_usd=0.1),
    ReviewResult("readability", [F("medium", "SQL built with f-string", cat="readability"),
                                 F("low", "rename q", line=2, cat="readability")], cost_usd=0.05),
    ReviewResult("testing", error="timed out"),
]


async def test_judge_merges_and_rejects_uncited():
    def respond(system, prompt):
        assert '"id": "security-1"' in prompt and '"id": "readability-2"' in prompt
        assert "testing (timed out)" in prompt
        return AgentResponse(cost_usd=0.2, data={
            "summary": "Adds a raw SQL query.",
            "verdict": "request_changes",
            "findings": [
                {**finding(severity="critical", title="SQL injection"), "source_ids": ["security-1", "readability-1"]},
                {**finding(severity="high", title="invented"), "source_ids": ["nope-9"]},
            ],
        })

    runner = FakeRunner(respond)
    report = await run_judge(DIFF, RESULTS, runner)

    assert [f.title for f in report.findings] == ["SQL injection"]
    assert report.findings[0].category == "readability+security"
    assert report.verdict == "request_changes"
    assert report.total_cost_usd == 0.1 + 0.05 + 0.2
    assert runner.calls[0]["schema"] is JUDGE_OUTPUT_SCHEMA and runner.calls[0]["effort"] == "high"


async def test_judge_cannot_approve_over_blocking_finding():
    runner = FakeRunner(lambda s, p: AgentResponse(data={
        "summary": "fine", "verdict": "approve",
        "findings": [{**finding(severity="high"), "source_ids": ["security-1"]}]}))
    assert (await run_judge(DIFF, RESULTS, runner)).verdict == "request_changes"


async def test_judge_failure_falls_back():
    runner = FakeRunner(lambda s, p: AgentResponse(data=None, error="overloaded", cost_usd=0.01))
    report = await run_judge(DIFF, RESULTS, runner)
    assert "Judge unavailable (overloaded)" in report.summary
    assert [f.severity.value for f in report.findings] == ["high", "medium", "low"]
    assert report.verdict == "request_changes"


async def test_no_findings_skips_judge():
    runner = FakeRunner(lambda s, p: (_ for _ in ()).throw(AssertionError("judge should not run")))
    clean = await run_judge(DIFF, [ReviewResult("security"), ReviewResult("testing")], runner)
    assert clean.verdict == "approve" and clean.findings == []
    partial = await run_judge(DIFF, [ReviewResult("security"), ReviewResult("testing", error="x")], runner)
    assert partial.verdict == "comment" and "testing failed" in partial.summary


def test_fallback_merge_dedupes_keeping_most_severe():
    merged = fallback_merge([ReviewResult("a", [F("low", "Dup")]), ReviewResult("b", [F("high", "dup")])])
    assert len(merged) == 1 and merged[0].severity is Severity.HIGH


def test_verdict_for():
    assert verdict_for([]) == "approve"
    assert verdict_for([F("info")]) == "approve"
    assert verdict_for([F("low")]) == "comment"
    assert verdict_for([F("critical")]) == "request_changes"


async def test_reports_render():
    runner = FakeRunner(lambda s, p: AgentResponse(data=None, error="x"))
    report = await run_judge(DIFF, RESULTS, runner)

    md = to_markdown(report)
    assert "❌ Request changes" in md and "### 1. 🟠 SQL injection" in md and "`app.py:1`" in md
    assert "| testing | ⚠️ timed out |" in md and "Total cost: $0.1500" in md

    data = json.loads(to_json(report))
    assert data["verdict"] == "request_changes" and len(data["findings"]) == 3
    assert data["reviewers"][2] == {"reviewer": "testing", "ok": False, "error": "timed out",
                                    "raw_findings": 0, "duration_ms": 0, "cost_usd": 0.0}
