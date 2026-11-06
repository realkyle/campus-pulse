"""Scoring of AI answers against the labeled alert dataset (no API calls)."""
from evals.metrics import evaluate

ai_scope_as_is = lambda text, scope: scope  # noqa: E731


def case(cid, severity="high", scope="campus", building="UW1", text="alert"):
    return {"id": cid, "text": text, "expected": {"severity": severity, "scope": scope, "building": building}}


def answer(severity="high", scope="campus", building="UW1"):
    return {"severity": severity, "scope": scope, "building": building}


def test_perfect_answers():
    cases = [case("a"), case("b", "low", "university_wide", "CAMPUS")]
    report = evaluate(cases, {"a": answer(), "b": answer("low", "university_wide", "CAMPUS")}, ai_scope_as_is)
    assert report["accuracy"] == {"severity": 1.0, "scope": 1.0, "building": 1.0}
    assert report["critical"] == {"under_call": [], "hidden_alert": [], "false_alarm": [], "wrong_pin": []}
    assert report["unusable"] == []


def test_under_call_of_a_real_emergency_is_critical():
    report = evaluate([case("a", "high")], {"a": answer("medium")}, ai_scope_as_is)
    assert report["critical"]["under_call"] == ["a"]
    assert report["accuracy"]["severity"] == 0.0


def test_false_alarm_is_critical():
    report = evaluate([case("a", "low")], {"a": answer("high")}, ai_scope_as_is)
    assert report["critical"]["false_alarm"] == ["a"]


def test_medium_low_mixups_are_errors_but_not_critical():
    report = evaluate([case("a", "medium"), case("b", "low")], {"a": answer("low"), "b": answer("medium")}, ai_scope_as_is)
    assert report["accuracy"]["severity"] == 0.0
    assert all(ids == [] for ids in report["critical"].values())


def test_campus_alert_labeled_other_campus_is_hidden():
    report = evaluate([case("a")], {"a": answer(scope="other_campus")}, ai_scope_as_is)
    assert report["critical"]["hidden_alert"] == ["a"]


def test_other_campus_alert_labeled_campus_is_a_wrong_pin():
    report = evaluate([case("a", scope="other_campus", building="CAMPUS")], {"a": answer(scope="campus")}, ai_scope_as_is)
    assert report["critical"]["wrong_pin"] == ["a"]


def test_scope_is_scored_as_the_map_would_show_it():
    # Scored through the same scope function the app uses.
    mentions = lambda text, scope: "campus" if "Bothell" in text else scope  # noqa: E731
    report = evaluate([case("a", text="Fire on the Bothell campus")], {"a": answer(scope="other_campus")}, mentions)
    assert report["accuracy"]["scope"] == 1.0
    assert report["critical"]["hidden_alert"] == []


def test_building_only_scored_for_campus_alerts():
    cases = [case("a", building="DISC"), case("b", scope="other_campus", building="CAMPUS")]
    answers = {"a": answer(building="LIB"), "b": answer(scope="other_campus", building="UW1")}
    report = evaluate(cases, answers, ai_scope_as_is)
    assert report["accuracy"]["building"] == 0.0   # 0 of 1 campus case
    assert report["counts"]["building"] == 1


def test_unusable_answer_counts_as_wrong_everywhere():
    report = evaluate([case("a", "high")], {"a": None}, ai_scope_as_is)
    assert report["unusable"] == ["a"]
    assert report["critical"]["under_call"] == ["a"]
    assert report["accuracy"] == {"severity": 0.0, "scope": 0.0, "building": 0.0}


def test_severity_confusion_matrix():
    cases = [case("a", "high"), case("b", "high"), case("c", "low")]
    report = evaluate(cases, {"a": answer("high"), "b": answer("low"), "c": None}, ai_scope_as_is)
    assert report["severity_confusion"] == {"high": {"high": 1, "low": 1}, "low": {"none": 1}}


def test_failures_list_names_field_expected_and_got():
    report = evaluate([case("a", "high", building="DISC")], {"a": answer("low", building="LIB")}, ai_scope_as_is)
    assert {"id": "a", "field": "severity", "expected": "high", "got": "low"} in report["failures"]
    assert {"id": "a", "field": "building", "expected": "DISC", "got": "LIB"} in report["failures"]


def test_dataset_is_well_formed():
    from building_coords import BUILDING_CODES
    from evals.run_alert_eval import load_cases

    cases = load_cases()
    assert len(cases) >= 30
    assert len({c["id"] for c in cases}) == len(cases)
    for c in cases:
        e = c["expected"]
        assert e["severity"] in {"low", "medium", "high"}, c["id"]
        assert e["scope"] in {"campus", "university_wide", "other_campus"}, c["id"]
        assert e["building"] in (*BUILDING_CODES, "CAMPUS"), c["id"]
        assert c["text"] and c["rationale"], c["id"]
