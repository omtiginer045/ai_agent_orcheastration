import pytest

from pr_reviewer.models import Finding, FinalReport, ReviewResult, Severity


def test_finding_from_dict_normalizes():
    f = Finding.from_dict(
        {"file": "a.py", "line": "12", "severity": "HIGH", "title": " t ", "description": "d"},
        category="security",
    )
    assert f.line == 12
    assert f.severity is Severity.HIGH
    assert f.title == "t"
    assert f.category == "security"
    assert f.suggestion == ""


def test_finding_null_line():
    f = Finding.from_dict({"file": "a.py", "line": None, "severity": "low", "title": "t", "description": "d"})
    assert f.line is None


def test_finding_rejects_bad_severity():
    with pytest.raises(ValueError):
        Finding.from_dict({"file": "a", "line": 1, "severity": "urgent", "title": "t", "description": "d"})


def test_severity_rank_order():
    assert sorted([Severity.LOW, Severity.CRITICAL, Severity.MEDIUM], key=lambda s: s.rank) == [
        Severity.CRITICAL, Severity.MEDIUM, Severity.LOW,
    ]


def test_roundtrip_to_dict():
    f = Finding("a.py", 3, Severity.MEDIUM, "t", "d", "s", "perf")
    assert Finding.from_dict(f.to_dict()) == f


def test_total_cost():
    r = FinalReport("s", [], "approve", [ReviewResult("a", cost_usd=0.1), ReviewResult("b", cost_usd=0.2)], 0.05)
    assert r.total_cost_usd == pytest.approx(0.35)
