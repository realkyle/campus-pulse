from datetime import datetime, timezone
from typing import Callable, Optional

from pydantic import BaseModel

from nlp_summarizer import AlertSummary, AlertTriage


class AlertPin(BaseModel):
    id: str
    raw_text: str
    building_name: str
    incident_type: str
    severity: str                    # low | medium | high
    recommended_action: str
    coordinates: list[float]         # [lat, lng]
    published: str
    headline: str | None = None      # smart triage — high severity only
    safety_brief: str | None = None  # smart triage — high severity only


class AlertsResponse(BaseModel):
    alerts: list[AlertPin]
    last_updated: str
    ai_available: bool
    feed_available: bool


FetchAlerts = Callable[[], tuple[list[dict], bool]]
Summarize = Callable[[str], tuple[Optional[AlertSummary], bool]]
Triage = Callable[[str, AlertSummary], Optional[AlertTriage]]
ResolveCoordinates = Callable[[str], tuple[float, float]]


class AlertPipeline:
    """Turns the raw alert feed into map pins, calling the AI only for new alerts.

    Each alert's ID is a hash of its text, so a pin built from a successful AI
    summary is reused for as long as that alert stays in the feed. Fallback pins
    (AI failed) are not stored, so the next refresh tries the AI again. Alerts
    that leave the feed are forgotten, which keeps memory bounded.

    The fetch, AI and geocoding steps are injected so tests can use fakes.
    refresh() blocks on network calls; call it from a worker thread, and never
    from two threads at once (the poll loop calls it one run at a time).
    """

    def __init__(
        self,
        fetch: FetchAlerts,
        summarize: Summarize,
        triage: Triage,
        resolve_coordinates: ResolveCoordinates,
        fallback_coordinates: tuple[float, float],
    ) -> None:
        self._fetch = fetch
        self._summarize = summarize
        self._triage = triage
        self._resolve_coordinates = resolve_coordinates
        self._fallback_coordinates = fallback_coordinates
        self._pins_by_id: dict[str, AlertPin] = {}

    def refresh(self) -> AlertsResponse:
        """Fetch the feed and return the current pins plus feed/AI health flags."""
        raw_alerts, feed_ok = self._fetch()
        ai_ok = True
        pins: list[AlertPin] = []
        kept: dict[str, AlertPin] = {}

        for raw in raw_alerts:
            pin = kept.get(raw["id"]) or self._pins_by_id.get(raw["id"])
            if pin is None:
                summary, ai_available = self._summarize(raw["raw_text"])
                ai_ok = ai_ok and ai_available
                if summary is None:
                    pins.append(self._fallback_pin(raw))
                    continue
                pin = self._summarized_pin(raw, summary)
            kept[raw["id"]] = pin
            pins.append(pin)

        self._pins_by_id = kept
        return AlertsResponse(
            alerts=pins,
            last_updated=datetime.now(timezone.utc).isoformat(),
            ai_available=ai_ok,
            feed_available=feed_ok,
        )

    def _summarized_pin(self, raw: dict, summary: AlertSummary) -> AlertPin:
        headline = None
        safety_brief = None
        if summary.severity == "high":
            result = self._triage(raw["raw_text"], summary)
            if result:
                headline = result.headline
                safety_brief = result.safety_brief
        return AlertPin(
            id=raw["id"],
            raw_text=raw["raw_text"],
            building_name=summary.building_name,
            incident_type=summary.incident_type,
            severity=summary.severity,
            recommended_action=summary.recommended_action,
            coordinates=list(self._resolve_coordinates(summary.building_name)),
            published=raw["published"],
            headline=headline,
            safety_brief=safety_brief,
        )

    def _fallback_pin(self, raw: dict) -> AlertPin:
        # Without the AI we can't place or grade the alert, so show its raw text
        # at the campus center rather than hide it.
        return AlertPin(
            id=raw["id"],
            raw_text=raw["raw_text"],
            building_name="CAMPUS",
            incident_type="Alert",
            severity="medium",
            recommended_action="See raw alert text for details.",
            coordinates=list(self._fallback_coordinates),
            published=raw["published"],
        )
