"""Scores the AI's alert answers against the labeled dataset (evals/alerts.jsonl).

Pure functions: unit-tested in CI with hand-written answers; the real run is
evals/run_alert_eval.py.

On a safety map, errors aren't equal. Four are reported as critical:
- under_call:   a real emergency (expected high) answered as medium/low/unusable
- hidden_alert: a campus alert labeled other_campus, so it's left off the map
- false_alarm:  an all-clear or informational alert (expected low) answered high
- wrong_pin:    another campus's incident shown as a pin on this map
"""
from collections import defaultdict
from collections.abc import Callable

FIELDS = ("severity", "scope", "building")


def evaluate(
    cases: list[dict],
    answers: dict[str, dict | None],
    scope_for: Callable[[str, str | None], str],
) -> dict:
    """Accuracy per field, severity confusion matrix, critical errors and every failure.

    `answers` maps case id → {"severity", "scope", "building"}, or None if the AI's
    answer was unusable. Scope is scored as the map shows it, through the same
    `scope_for` the app uses (building_coords.effective_scope).
    Building is scored only for alerts expected on this campus.
    """
    correct = {field: 0 for field in FIELDS}
    counts = {field: 0 for field in FIELDS}
    critical: dict[str, list[str]] = {"under_call": [], "hidden_alert": [], "false_alarm": [], "wrong_pin": []}
    confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    failures: list[dict] = []
    unusable: list[str] = []

    for case in cases:
        cid, expected = case["id"], case["expected"]
        answer = answers.get(cid)
        if answer is None:
            unusable.append(cid)
            got = {"severity": "none", "scope": "none", "building": "none"}
        else:
            scope = scope_for(case["text"], answer["scope"])
            got = {"severity": answer["severity"], "scope": scope, "building": answer["building"]}

        confusion[expected["severity"]][got["severity"]] += 1
        for field in FIELDS:
            if field == "building" and expected["scope"] != "campus":
                continue
            counts[field] += 1
            if got[field] == expected[field]:
                correct[field] += 1
            else:
                failures.append({"id": cid, "field": field, "expected": expected[field], "got": got[field]})

        if expected["severity"] == "high" and got["severity"] != "high":
            critical["under_call"].append(cid)
        if expected["severity"] == "low" and got["severity"] == "high":
            critical["false_alarm"].append(cid)
        if expected["scope"] == "campus" and got["scope"] == "other_campus":
            critical["hidden_alert"].append(cid)
        if expected["scope"] != "campus" and got["scope"] == "campus":
            critical["wrong_pin"].append(cid)

    return {
        "cases": len(cases),
        "counts": counts,
        "accuracy": {f: (correct[f] / counts[f] if counts[f] else 0.0) for f in FIELDS},
        "critical": critical,
        "unusable": unusable,
        "severity_confusion": {e: dict(g) for e, g in confusion.items()},
        "failures": failures,
    }


def render(report: dict) -> str:
    """A short plain-text summary for the terminal."""
    lines = [f"{report['cases']} cases, {len(report['unusable'])} unusable answers"]
    for field, value in report["accuracy"].items():
        lines.append(f"  {field:<9} accuracy {value:6.1%}  (n={report['counts'][field]})")
    lines.append("Critical errors:")
    for kind, ids in report["critical"].items():
        lines.append(f"  {kind:<13} {len(ids):2d}  {' '.join(ids)}")
    lines.append("Severity (expected → got):")
    for expected in ("high", "medium", "low"):
        row = report["severity_confusion"].get(expected, {})
        lines.append(f"  {expected:<7} " + "  ".join(f"{got}:{n}" for got, n in sorted(row.items())))
    if report["failures"]:
        lines.append("Failures:")
        for f in report["failures"]:
            lines.append(f"  {f['id']:<4} {f['field']:<9} expected {f['expected']:<15} got {f['got']}")
    return "\n".join(lines)
