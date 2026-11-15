"""End-to-end: CLI → orchestrator → specialists → judge → report, with a fake LLM."""

import json
from pathlib import Path

from pr_reviewer.cli import EXIT_ERROR, EXIT_FINDINGS, EXIT_OK, run
from pr_reviewer.runner import AgentResponse

from .fakes import FakeRunner, finding

EXAMPLE = Path(__file__).parent.parent / "examples" / "vulnerable.diff"


def fake_llm(system, prompt):
    if "lead reviewer" in system:  # the judge
        return AgentResponse(cost_usd=0.05, data={
            "summary": "Introduces SQL and shell injection.",
            "verdict": "request_changes",
            "findings": [{**finding(file="app/users.py", line=9, severity="critical", title="SQL injection"),
                          "source_ids": ["security-1"]}],
        })
    if "security" in system:
        return AgentResponse(cost_usd=0.02, data={"findings": [
            finding(file="app/users.py", line=9, severity="critical", title="SQL injection")]})
    return AgentResponse(cost_usd=0.01, data={"findings": []})


async def test_end_to_end_markdown(capsys):
    runner = FakeRunner(fake_llm)
    code = await run(["--diff-file", str(EXAMPLE), "--fail-on", "high"], runner=runner)

    out, err = capsys.readouterr()
    assert code == EXIT_FINDINGS
    assert len(runner.calls) == 5  # 4 specialists + judge
    assert "❌ Request changes" in out and "SQL injection" in out and "`app/users.py:9`" in out
    assert "Reviewing 1 file(s) with 4 reviewer(s)" in err and "✓ security: 1 finding(s)" in err


async def test_json_output_to_file_and_reviewer_subset(tmp_path):
    out = tmp_path / "r.json"
    runner = FakeRunner(fake_llm)
    code = await run(["--diff-file", str(EXAMPLE), "--reviewers", "security", "--format", "json", "-o", str(out)],
                     runner=runner)
    assert code == EXIT_OK  # --fail-on defaults to never
    data = json.loads(out.read_text())
    assert [r["reviewer"] for r in data["reviewers"]] == ["security"]
    assert data["cost_usd"]["total"] == 0.07


async def test_fail_on_threshold_not_reached():
    code = await run(["--diff-file", str(EXAMPLE), "--fail-on", "critical", "--reviewers", "testing"],
                     runner=FakeRunner(fake_llm))
    assert code == EXIT_OK


async def test_all_reviewers_failing_is_an_error(capsys):
    runner = FakeRunner(lambda s, p: AgentResponse(data=None, error="no credentials"))
    assert await run(["--diff-file", str(EXAMPLE)], runner=runner) == EXIT_ERROR
    assert "every reviewer failed" in capsys.readouterr().err


async def test_bad_input(tmp_path, capsys):
    assert await run(["--diff-file", str(EXAMPLE), "--reviewers", "style"], runner=FakeRunner(fake_llm)) == EXIT_ERROR
    assert await run(["--diff-file", str(tmp_path / "missing.diff")], runner=FakeRunner(fake_llm)) == EXIT_ERROR
    empty = tmp_path / "e.diff"
    empty.write_text("")
    assert await run(["--diff-file", str(empty)], runner=FakeRunner(fake_llm)) == EXIT_OK
    assert "diff is empty" in capsys.readouterr().err
