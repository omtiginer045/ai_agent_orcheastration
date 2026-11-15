"""The specialist reviewers. Each one looks at the same diff through one lens.

Adding a reviewer is just adding a ``Specialist`` here; the orchestrator picks
it up automatically.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Specialist:
    name: str
    focus: str  # what this reviewer is responsible for
    checklist: tuple[str, ...]
    effort: str = "medium"


SPECIALISTS: tuple[Specialist, ...] = (
    Specialist(
        name="security",
        focus="security vulnerabilities and unsafe handling of untrusted data",
        checklist=(
            "injection: SQL, shell/command, path traversal, template, LDAP, XSS",
            "authentication / authorization gaps and missing access checks",
            "secrets, tokens or credentials committed or logged",
            "unsafe deserialization, eval/exec, disabled TLS verification",
            "SSRF, open redirects, insecure file permissions",
            "dependency or configuration changes that weaken security",
        ),
        effort="high",
    ),
    Specialist(
        name="performance",
        focus="performance and resource usage",
        checklist=(
            "algorithmic complexity regressions (nested loops over large data, O(n^2) lookups)",
            "N+1 queries, queries inside loops, missing pagination or indexes",
            "blocking I/O on async paths, missing concurrency where it matters",
            "unbounded memory growth, caches without eviction, leaked resources",
            "repeated expensive work that could be hoisted or cached",
        ),
    ),
    Specialist(
        name="readability",
        focus="readability, maintainability and correctness of the code as written",
        checklist=(
            "logic bugs, off-by-one errors, wrong conditions, unhandled None/empty cases",
            "unclear names, misleading comments, dead code",
            "functions doing too much, duplicated logic that should be shared",
            "error handling that swallows failures or hides the cause",
            "inconsistency with conventions used elsewhere in the repository",
        ),
    ),
    Specialist(
        name="testing",
        focus="test coverage and test quality for the changed behavior",
        checklist=(
            "new or changed behavior with no test exercising it",
            "edge cases and failure paths that are not tested",
            "tests that assert nothing meaningful or test the mock instead of the code",
            "flaky patterns: sleeps, real network, time or ordering dependence",
            "existing tests that the change likely breaks",
        ),
    ),
)


def get_specialists(names: list[str] | None = None) -> list[Specialist]:
    """All specialists, or only the named ones (order preserved)."""
    if not names:
        return list(SPECIALISTS)
    by_name = {s.name: s for s in SPECIALISTS}
    unknown = [n for n in names if n not in by_name]
    if unknown:
        raise ValueError(f"unknown reviewer(s): {', '.join(unknown)}; available: {', '.join(by_name)}")
    return [by_name[n] for n in names]
