"""Command line entry point: ``pr-review``.

Examples:
    pr-review --base main                     # review current branch vs main
    pr-review --diff-file change.patch --format json -o review.json
    git diff | pr-review --stdin --reviewers security,testing
    pr-review --base main --fail-on high      # exit 1 if any high/critical finding (CI gate)
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from . import diff_source, pipeline, report
from .agents import SPECIALISTS, get_specialists
from .models import FinalReport, Severity
from .orchestrator import OrchestratorConfig
from .runner import DEFAULT_MODEL, AgentRunner, ClaudeAgentRunner

EXIT_OK, EXIT_FINDINGS, EXIT_ERROR = 0, 1, 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pr-review", description="Multi-agent PR review with the Claude Agent SDK.")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--base", help="review HEAD (or --head) against this git ref")
    src.add_argument("--diff-file", type=Path, help="review a unified diff / patch file")
    src.add_argument("--stdin", action="store_true", help="read the diff from stdin")
    p.add_argument("--head", default="HEAD", help="git ref under review (with --base; default HEAD)")
    p.add_argument("--repo", type=Path, default=Path("."), help="repository root agents may read (default .)")
    p.add_argument("--reviewers", help=f"comma-separated subset of: {', '.join(s.name for s in SPECIALISTS)}")
    p.add_argument("--format", choices=["md", "json"], default="md")
    p.add_argument("-o", "--output", type=Path, help="write the report here instead of stdout")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--max-budget", type=float, default=1.0, help="USD cap per agent run (default 1.0)")
    p.add_argument("--timeout", type=float, default=600.0, help="seconds per reviewer (default 600)")
    p.add_argument("--concurrency", type=int, default=4)
    p.add_argument("--fail-on", choices=[s.value for s in Severity] + ["never"], default="never",
                   help="exit 1 if any finding is at least this severe")
    return p


async def _load_diff(args) -> diff_source.Diff:
    if args.base:
        return await diff_source.from_git(args.repo, args.base, args.head)
    if args.diff_file:
        return diff_source.from_file(args.diff_file, args.repo)
    return diff_source.from_stdin(args.repo)


def _progress(name: str, event: str, result) -> None:
    if event == "start":
        print(f"  … {name} reviewing", file=sys.stderr)
    elif result is None:
        print(f"  ✓ {name} done", file=sys.stderr)
    elif result.ok:
        print(f"  ✓ {name}: {len(result.findings)} finding(s), {result.duration_ms / 1000:.1f}s", file=sys.stderr)
    else:
        print(f"  ✗ {name}: {result.error}", file=sys.stderr)


def exit_code_for(final: FinalReport, fail_on: str) -> int:
    if fail_on == "never":
        return EXIT_OK
    threshold = Severity(fail_on).rank
    return EXIT_FINDINGS if any(f.severity.rank <= threshold for f in final.findings) else EXIT_OK


async def run(argv: list[str] | None = None, runner: AgentRunner | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        specialists = get_specialists(args.reviewers.split(",") if args.reviewers else None)
        diff = await _load_diff(args)
    except (ValueError, OSError, diff_source.DiffError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    if diff.is_empty:
        print("Nothing to review: the diff is empty.", file=sys.stderr)
        return EXIT_OK

    runner = runner or ClaudeAgentRunner(model=args.model, max_budget_usd=args.max_budget)
    config = OrchestratorConfig(max_concurrency=args.concurrency, reviewer_timeout_s=args.timeout)
    print(f"Reviewing {len(diff.files)} file(s) with {len(specialists)} reviewer(s)…", file=sys.stderr)
    final = await pipeline.review(diff, runner, specialists, config, _progress)

    rendered = report.to_json(final) if args.format == "json" else report.to_markdown(final)
    if args.output:
        args.output.write_text(rendered)
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(rendered)
    if all(not r.ok for r in final.reviewer_results):
        print("error: every reviewer failed; see the report for details.", file=sys.stderr)
        return EXIT_ERROR
    return exit_code_for(final, args.fail_on)


def main() -> None:
    sys.exit(asyncio.run(run()))


if __name__ == "__main__":
    main()
