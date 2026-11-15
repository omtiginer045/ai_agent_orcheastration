"""ClaudeAgentRunner against a stubbed ``claude_agent_sdk.query`` (no CLI, no API)."""

from pathlib import Path

import claude_agent_sdk
from claude_agent_sdk import ResultMessage

from pr_reviewer.runner import READ_ONLY_TOOLS, ClaudeAgentRunner


def _result(**kw):
    base = dict(subtype="success", duration_ms=120, duration_api_ms=100, is_error=False,
                num_turns=3, session_id="s", total_cost_usd=0.04, structured_output={"findings": []})
    base.update(kw)
    return ResultMessage(**base)


def _stub_query(monkeypatch, *messages):
    seen = {}

    async def fake_query(*, prompt, options=None, transport=None):
        seen["prompt"], seen["options"] = prompt, options
        for m in messages:
            yield m

    monkeypatch.setattr(claude_agent_sdk, "query", fake_query)
    return seen


async def _run(runner=None):
    return await (runner or ClaudeAgentRunner()).run(
        system_prompt="sys", prompt="p", output_schema={"type": "object"}, cwd=Path("/repo"), effort="high")


async def test_builds_options_and_reads_result(monkeypatch):
    seen = _stub_query(monkeypatch, _result())
    resp = await _run(ClaudeAgentRunner(model="claude-opus-5-5", max_budget_usd=0.5))

    assert resp.error is None and resp.data == {"findings": []}
    assert resp.cost_usd == 0.04 and resp.num_turns == 3
    o = seen["options"]
    assert o.model == "claude-opus-5-5" and o.system_prompt == "sys" and o.effort == "high"
    assert o.tools == READ_ONLY_TOOLS and o.allowed_tools == READ_ONLY_TOOLS
    assert o.cwd == "/repo" and o.max_budget_usd == 0.5 and o.setting_sources == []
    assert o.output_format == {"type": "json_schema", "schema": {"type": "object"}}


async def test_error_result(monkeypatch):
    _stub_query(monkeypatch, _result(is_error=True, subtype="error_max_turns", errors=None, structured_output=None))
    resp = await _run()
    assert resp.data is None and "error_max_turns" in resp.error and resp.cost_usd == 0.04


async def test_missing_structured_output(monkeypatch):
    _stub_query(monkeypatch, _result(structured_output=None))
    assert (await _run()).error == "agent did not return structured output"


async def test_no_result_message(monkeypatch):
    _stub_query(monkeypatch)
    assert (await _run()).error == "agent produced no result message"
