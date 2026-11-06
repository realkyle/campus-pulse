import json
import logging
import os
from typing import Literal

import openai
from openai import OpenAI
from pydantic import BaseModel, ValidationError

from building_coords import BUILDING_CODES, CAMPUS_NAME

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = f"""You are a campus safety alert parser for {CAMPUS_NAME}, one of several University of Washington campuses.
Given raw alert text, return ONLY a valid JSON object — no markdown, no extra text.

JSON schema:
{{
  "building_name": "<{"|".join(BUILDING_CODES)}|CAMPUS>",
  "incident_type": "<e.g. Police Activity|Medical Emergency|Fire|Suspicious Person|Weather|Utility Outage|All-Clear>",
  "severity": "<low|medium|high>",
  "recommended_action": "<concise student instruction, max 20 words>",
  "scope": "<campus|university_wide|other_campus>"
}}

Rules:
- severity=high: active threat, police, fire, evacuation
- severity=medium: medical, suspicious activity, utility outage
- severity=low: all-clear, informational, minor disruption
- scope=campus: the incident is at {CAMPUS_NAME}
- scope=university_wide: affects all UW campuses (e.g. system tests, drills, weather or smoke advisories)
- scope=other_campus: about a location at another UW campus (e.g. Seattle streets or buildings)
- If no {CAMPUS_NAME} building is mentioned, use CAMPUS."""

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
