"""Render a FinalReport as Markdown (for humans / PR comments) or JSON (for tools)."""

from __future__ import annotations

import json

from .models import FinalReport, Severity

_ICON = {
    Severity.CRITICAL: "🔴", Severity.HIGH: "🟠", Severity.MEDIUM: "🟡", Severity.LOW: "🔵", Severity.INFO: "⚪",
}
_VERDICT = {"approve": "✅ Approve", "comment": "💬 Comment", "request_changes": "❌ Request changes"}


def to_markdown(report: FinalReport) -> str:
    lines = ["# PR Review", "", f"**Verdict:** {_VERDICT.get(report.verdict, report.verdict)}", "", report.summary, ""]

    if report.findings:
        counts = ", ".join(
            f"{_ICON[s]} {n} {s.value}"
            for s in Severity
            if (n := sum(f.severity is s for f in report.findings))
        )
        lines += [f"## Findings ({counts})", ""]
        for i, f in enumerate(report.findings, 1):
            loc = f"`{f.file}:{f.line}`" if f.line else f"`{f.file}`"
            lines += [f"### {i}. {_ICON[f.severity]} {f.title}", "", f"{loc} · {f.severity.value} · {f.category}", "",
                      f.description, ""]
            if f.suggestion:
                lines += [f"**Suggestion:** {f.suggestion}", ""]
    else:
        lines += ["No findings.", ""]

    lines += ["## Reviewers", "", "| Reviewer | Status | Raw findings | Time | Cost |", "|---|---|---|---|---|"]
    for r in report.reviewer_results:
        status = "ok" if r.ok else f"⚠️ {r.error}"
        lines.append(f"| {r.reviewer} | {status} | {len(r.findings)} | {r.duration_ms / 1000:.1f}s | ${r.cost_usd:.4f} |")
    lines += ["", f"Judge cost: ${report.judge_cost_usd:.4f} · **Total cost: ${report.total_cost_usd:.4f}**", ""]
    return "\n".join(lines)


def to_json(report: FinalReport) -> str:
    return json.dumps(
        {
            "verdict": report.verdict,
            "summary": report.summary,
            "findings": [f.to_dict() for f in report.findings],
            "reviewers": [
                {"reviewer": r.reviewer, "ok": r.ok, "error": r.error, "raw_findings": len(r.findings),
                 "duration_ms": r.duration_ms, "cost_usd": r.cost_usd}
                for r in report.reviewer_results
            ],
            "cost_usd": {"judge": report.judge_cost_usd, "total": report.total_cost_usd},
        },
        indent=2,
        ensure_ascii=False,
    )
