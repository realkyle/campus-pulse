import json
import logging
import os
from typing import Literal

import openai
from openai import OpenAI
from pydantic import BaseModel, ValidationError

from building_coords import BUILDING_CODES, BUILDING_NAMES, CAMPUS_NAME, CAMPUS_STREETS

logger = logging.getLogger(__name__)

_BUILDING_LIST = "\n".join(f"  {code} = {BUILDING_NAMES[code]}" for code in BUILDING_CODES)

# v2 (2026-11-06): rules added from the baseline evaluation's failures
# (evals/results/*-baseline.json). Rules are general; never copy eval cases in.
SYSTEM_PROMPT = f"""You are a campus safety alert parser for {CAMPUS_NAME}, one of several University of Washington campuses.
Given raw alert text, return ONLY a valid JSON object — no markdown, no extra text.

JSON schema:
{{
  "building_name": "<{"|".join(BUILDING_CODES)}|CAMPUS>",
  "incident_type": "<e.g. Police Activity|Medical Emergency|Fire|Suspicious Person|Weather|Health Advisory|Utility Outage|All-Clear>",
  "severity": "<low|medium|high>",
  "recommended_action": "<concise student instruction, max 20 words>",
  "scope": "<campus|university_wide|other_campus>"
}}

{CAMPUS_NAME} buildings (code = name):
{_BUILDING_LIST}
{CAMPUS_NAME} streets: {", ".join(CAMPUS_STREETS)}.

Scope rules:
- scope=campus: the alert names {CAMPUS_NAME}, one of its buildings or streets, or a place right next to it.
- scope=other_campus: the alert names any other place (another UW campus, or a building, street or
  neighborhood that is not listed above), even if no city is named.
- scope=university_wide: the alert names no specific place and applies to all UW campuses or the region
  (system tests, drills, closures, weather or smoke advisories).

Severity rules, applied in this order:
1. low: the incident is over or was never real: all-clear, "response completed", area reopened,
   false alarm, harmless, test, drill or training. This applies even if the text mentions police or fire.
2. high: an ongoing threat to people: active threat, armed person, police activity with avoid/shelter
   instructions, fire, explosion or bomb threat, gas leak, hazardous materials, any evacuation or
   shelter-in-place instruction.
3. medium: medical emergency, suspicious person or package, utility or network outage, road or area
   closure, campus closure, health advisory (smoke, heat, disease, dangerous animals), or an emergency
   response that only closes an area without evacuate/shelter instructions.
4. low: anything else informational (reminders, schedule changes, minor disruptions).

Building: use the code of the named {CAMPUS_NAME} building; use CAMPUS if none is named or scope isn't campus."""

MODEL = "gpt-4o-mini"

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _client


TRIAGE_PROMPT = f"""You are a campus safety communications officer for {CAMPUS_NAME}.
A high-severity emergency alert has just been issued. Write two things:

1. "headline": A single urgent sentence (max 12 words) for a push notification.
2. "safety_brief": Exactly 3 sentences of calm, actionable safety guidance for students.

Return ONLY valid JSON with keys "headline" and "safety_brief"."""


class AlertSummary(BaseModel):
    building_name: str
    incident_type: str
    severity: str
    recommended_action: str
    # If the model omits it, list the alert without a pin rather than hide or misplace it.
    scope: Literal["campus", "university_wide", "other_campus"] = "university_wide"


class AlertTriage(BaseModel):
    headline: str
    safety_brief: str


def triage(raw_text: str, summary: AlertSummary) -> AlertTriage | None:
    """
    Second GPT call — only fires for severity=high.
    Generates a push-notification headline and 3-sentence safety brief.
    """
    try:
        context = (
            f"Incident: {summary.incident_type} at {summary.building_name}.\n"
            f"Raw alert: {raw_text}"
        )
        response = _get_client().chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": TRIAGE_PROMPT},
                {"role": "user", "content": context},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=200,
        )
        data = json.loads(response.choices[0].message.content.strip())
        return AlertTriage(**data)
    except Exception as e:
        logger.error("Triage failed: %s", e)
        return None


def summarize(raw_text: str) -> tuple[AlertSummary | None, bool]:
    """Ask the AI to structure one alert. Returns (summary, ai_available).

    The two failure kinds are reported differently on purpose:
    - OpenAI unreachable (network, auth, outage, missing key) → (None, False):
      the frontend warns that AI summaries are down.
    - A malformed answer (bad JSON, missing field) → (None, True): logged, and
      the alert falls back to raw text, but it isn't an outage.
    """
    try:
        response = _get_client().chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Alert text: {raw_text}"},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=200,
        )
    except (openai.OpenAIError, KeyError) as e:  # KeyError: OPENAI_API_KEY not set
        logger.error("OpenAI unavailable: %r", e)
        return None, False

    try:
        summary = AlertSummary(**json.loads(response.choices[0].message.content.strip()))
    except (json.JSONDecodeError, ValidationError, TypeError) as e:
        logger.warning("Unusable AI answer for alert: %s", e)
        return None, True

    summary.severity = summary.severity.lower()
    if summary.severity not in ("low", "medium", "high"):
        summary.severity = "medium"
    return summary, True
