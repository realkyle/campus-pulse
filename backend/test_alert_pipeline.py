"""Tests for AlertPipeline: GPT is called once per alert text, failures retry."""
from alert_pipeline import AlertPipeline
from building_coords import effective_scope
from nlp_summarizer import AlertSummary, AlertTriage

CENTER = (0.0, 0.0)


def raw(alert_id: str, text: str = "Police activity near UW1.") -> dict:
    return {"id": alert_id, "raw_text": text, "published": "2026-01-01T00:00:00Z"}


class FakeFeed:
    def __init__(self, alerts: list[dict], ok: bool = True) -> None:
        self.alerts = alerts
        self.ok = ok

    def __call__(self):
        return self.alerts, self.ok


class FakeAI:
    """Stands in for summarize() and triage(); counts calls and can fail on demand."""

    def __init__(self, severity: str = "medium", scope: str = "campus") -> None:
        self.severity = severity
        self.scope = scope
        self.fail = False
        self.summarize_calls: list[str] = []
        self.triage_calls: list[str] = []

    def summarize(self, raw_text: str):
        self.summarize_calls.append(raw_text)
        if self.fail:
            return None, False
        return AlertSummary(
            building_name="UW1", incident_type="Police Activity",
            severity=self.severity, recommended_action="Avoid the area.", scope=self.scope,
        ), True

    def triage(self, raw_text: str, summary: AlertSummary):
        self.triage_calls.append(raw_text)
        return AlertTriage(headline="Avoid UW1", safety_brief="Stay away.")


def make_pipeline(feed: FakeFeed, ai: FakeAI) -> AlertPipeline:
    return AlertPipeline(
        fetch=feed,
        summarize=ai.summarize,
        triage=ai.triage,
        resolve_coordinates=lambda building: (1.0, 2.0),
        fallback_coordinates=CENTER,
        scope_for=effective_scope,
    )


def test_each_alert_is_summarized_once():
    feed, ai = FakeFeed([raw("a"), raw("b", "Fire alarm in UW2.")]), FakeAI()
    pipeline = make_pipeline(feed, ai)

    first = pipeline.refresh()
    second = pipeline.refresh()

    assert len(ai.summarize_calls) == 2
    assert [p.id for p in first.alerts] == ["a", "b"]
    assert second.alerts == first.alerts


def test_only_new_alerts_are_summarized():
    feed, ai = FakeFeed([raw("a")]), FakeAI()
    pipeline = make_pipeline(feed, ai)
    pipeline.refresh()

    feed.alerts = [raw("a"), raw("b", "Fire alarm in UW2.")]
    result = pipeline.refresh()

    assert ai.summarize_calls == ["Police activity near UW1.", "Fire alarm in UW2."]
    assert [p.id for p in result.alerts] == ["a", "b"]


def test_alerts_gone_from_feed_are_forgotten():
    feed, ai = FakeFeed([raw("a")]), FakeAI()
    pipeline = make_pipeline(feed, ai)
    pipeline.refresh()

    feed.alerts = []
    assert pipeline.refresh().alerts == []

    feed.alerts = [raw("a")]  # reappears: no longer cached, so summarized again
    pipeline.refresh()
    assert len(ai.summarize_calls) == 2


def test_ai_failure_gives_fallback_pin_and_retries_next_time():
    feed, ai = FakeFeed([raw("a", "Police activity near UW1 on the Bothell campus.")]), FakeAI()
    ai.fail = True
    pipeline = make_pipeline(feed, ai)

    failed = pipeline.refresh()
    pin = failed.alerts[0]
    assert failed.ai_available is False
    assert (pin.building_name, pin.severity, pin.scope, pin.coordinates) == ("CAMPUS", "medium", "campus", list(CENTER))
    assert pin.raw_text == "Police activity near UW1 on the Bothell campus."

    ai.fail = False
    recovered = pipeline.refresh()
    assert recovered.ai_available is True
    assert recovered.alerts[0].building_name == "UW1"
    assert len(ai.summarize_calls) == 2


def test_high_severity_is_triaged_once():
    feed, ai = FakeFeed([raw("a")]), FakeAI(severity="high")
    pipeline = make_pipeline(feed, ai)

    pipeline.refresh()
    result = pipeline.refresh()

    assert len(ai.triage_calls) == 1
    assert result.alerts[0].headline == "Avoid UW1"


def test_lower_severity_is_not_triaged():
    feed, ai = FakeFeed([raw("a")]), FakeAI(severity="low")
    make_pipeline(feed, ai).refresh()
    assert ai.triage_calls == []


def test_feed_status_is_passed_through():
    feed, ai = FakeFeed([], ok=False), FakeAI()
    result = make_pipeline(feed, ai).refresh()
    assert result.feed_available is False
    assert result.alerts == []


# ── Scope ─────────────────────────────────────────────────────────────────────

def test_campus_alert_is_pinned():
    pin = make_pipeline(FakeFeed([raw("a")]), FakeAI(scope="campus")).refresh().alerts[0]
    assert (pin.scope, pin.coordinates) == ("campus", [1.0, 2.0])


def test_university_wide_alert_is_listed_without_a_pin():
    pin = make_pipeline(FakeFeed([raw("a", "Earthquake drill at all campuses.")]), FakeAI(scope="university_wide")).refresh().alerts[0]
    assert (pin.scope, pin.coordinates) == ("university", None)


def test_other_campus_alert_is_left_out_and_not_reanalyzed():
    feed, ai = FakeFeed([raw("a", "Street closed near another campus.")]), FakeAI(scope="other_campus")
    pipeline = make_pipeline(feed, ai)
    assert pipeline.refresh().alerts == []
    assert pipeline.refresh().alerts == []
    assert len(ai.summarize_calls) == 1


def test_campus_name_in_text_overrides_the_ai():
    feed = FakeFeed([raw("a", "Power outage on the Bothell campus.")])
    pin = make_pipeline(feed, FakeAI(scope="other_campus")).refresh().alerts[0]
    assert (pin.scope, pin.coordinates) == ("campus", [1.0, 2.0])


def test_ai_failure_without_campus_name_is_listed_without_a_pin():
    ai = FakeAI()
    ai.fail = True
    pin = make_pipeline(FakeFeed([raw("a", "Smoke advisory.")]), ai).refresh().alerts[0]
    assert (pin.scope, pin.coordinates, pin.severity) == ("university", None, "medium")
