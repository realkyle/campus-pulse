from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel

from nlp_summarizer import AlertSummary, AlertTriage


class AlertPin(BaseModel):
    id: str
    raw_text: str
    building_name: str
    incident_type: str
    severity: str                    # low | medium | high
    recommended_action: str
    scope: Literal["campus", "university"] = "campus"
    coordinates: list[float] | None  # [lat, lng]; None = university-wide, listed but not pinned
    published: str
    headline: str | None = None      # smart triage — high severity only
    safety_brief: str | None = None  # smart triage — high severity only


class AlertsResponse(BaseModel):
    alerts: list[AlertPin]
    last_updated: str
    ai_available: bool
    feed_available: bool


FetchAlerts = Callable[[], tuple[list[dict], bool]]
Summarize = Callable[[str], tuple[AlertSummary | None, bool]]
Triage = Callable[[str, AlertSummary], AlertTriage | None]
ResolveCoordinates = Callable[[str], tuple[float, float]]
# (alert text, AI scope or None if the AI failed) → "campus" | "university_wide" | "other_campus"
ScopeFor = Callable[[str, str | None], str]


class AlertPipeline:
    """Turns the raw alert feed into map pins, calling the AI only for new alerts.

    Each alert's ID is a hash of its text, so a result built from a successful
    AI summary is reused for as long as that alert stays in the feed, including
    the decision to leave out an alert about another campus. Fallback pins (AI
    failed) are not stored, so the next refresh tries the AI again. Alerts that
    leave the feed are forgotten, which keeps memory bounded.

    Scope comes from `scope_for` (building_coords.effective_scope): campus →
    pinned; university-wide → listed without coordinates; other campus → left
    out. A pin needs evidence of this campus in the text itself, not just the
    AI's word.

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
        scope_for: ScopeFor,
    ) -> None:
        self._fetch = fetch
        self._summarize = summarize
        self._triage = triage
        self._resolve_coordinates = resolve_coordinates
        self._fallback_coordinates = fallback_coordinates
        self._scope_for = scope_for
        # alert ID → its pin, or None for "left out" (other campus)
        self._results_by_id: dict[str, AlertPin | None] = {}

    def refresh(self) -> AlertsResponse:
        """Fetch the feed and return the current pins plus feed/AI health flags."""
        raw_alerts, feed_ok = self._fetch()
        ai_ok = True
        pins: list[AlertPin] = []
        kept: dict[str, AlertPin | None] = {}

        for raw in raw_alerts:
            alert_id = raw["id"]
            if alert_id in kept or alert_id in self._results_by_id:
                pin = kept[alert_id] if alert_id in kept else self._results_by_id[alert_id]
            else:
                summary, ai_available = self._summarize(raw["raw_text"])
                ai_ok = ai_ok and ai_available
                if summary is None:
                    pins.append(self._fallback_pin(raw))
                    continue
                pin = self._summarized_pin(raw, summary)
            kept[alert_id] = pin
            if pin is not None:
                pins.append(pin)

        self._results_by_id = kept
        return AlertsResponse(
            alerts=pins,
            last_updated=datetime.now(UTC).isoformat(),
            ai_available=ai_ok,
            feed_available=feed_ok,
        )

    def _summarized_pin(self, raw: dict, summary: AlertSummary) -> AlertPin | None:
        """The pin for a summarized alert, or None if it's about another campus."""
        scope = self._scope_for(raw["raw_text"], summary.scope)
        if scope == "other_campus":
            return None
        scope = "campus" if scope == "campus" else "university"
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
            scope=scope,
            coordinates=list(self._resolve_coordinates(summary.building_name)) if scope == "campus" else None,
            published=raw["published"],
            headline=headline,
            safety_brief=safety_brief,
        )

    def _fallback_pin(self, raw: dict) -> AlertPin:
        # Without the AI we can't place or grade the alert, so show its raw text
        # rather than hide it: at the campus center if the text shows it's this
        # campus, otherwise in the list only.
        on_campus = self._scope_for(raw["raw_text"], None) == "campus"
        return AlertPin(
            id=raw["id"],
            raw_text=raw["raw_text"],
            building_name="CAMPUS",
            incident_type="Alert",
            severity="medium",
            recommended_action="See raw alert text for details.",
            scope="campus" if on_campus else "university",
            coordinates=list(self._fallback_coordinates) if on_campus else None,
            published=raw["published"],
        )
