"""Tests for AlertPipeline: GPT is called once per alert text, failures retry."""
from alert_pipeline import AlertPipeline
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

    def __init__(self, severity: str = "medium") -> None:
        self.severity = severity
        self.fail = False
        self.summarize_calls: list[str] = []
        self.triage_calls: list[str] = []

    def summarize(self, raw_text: str):
        self.summarize_calls.append(raw_text)
        if self.fail:
            return None, False
        return AlertSummary(
            building_name="UW1", incident_type="Police Activity",
            severity=self.severity, recommended_action="Avoid the area.",
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
    feed, ai = FakeFeed([raw("a")]), FakeAI()
    ai.fail = True
    pipeline = make_pipeline(feed, ai)

    failed = pipeline.refresh()
    pin = failed.alerts[0]
    assert failed.ai_available is False
    assert (pin.building_name, pin.severity, pin.coordinates) == ("CAMPUS", "medium", list(CENTER))
    assert pin.raw_text == "Police activity near UW1."

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
