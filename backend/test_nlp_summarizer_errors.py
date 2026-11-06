"""How summarize() reports failures (contract: api/alerts.md, ai_available)."""
from types import SimpleNamespace

import httpx
import openai
import pytest

import nlp_summarizer


def fake_client(content: str = "", error: Exception | None = None):
    def create(**kwargs):
        if error:
            raise error
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


def use(monkeypatch, client):
    monkeypatch.setattr(nlp_summarizer, "_get_client", lambda: client)


VALID = '{"building_name": "UW1", "incident_type": "Fire", "severity": "HIGH", "recommended_action": "Leave.", "scope": "campus"}'


def test_valid_answer(monkeypatch):
    use(monkeypatch, fake_client(VALID))
    summary, ai_available = nlp_summarizer.summarize("Fire in UW1")
    assert ai_available
    assert (summary.building_name, summary.severity, summary.scope) == ("UW1", "high", "campus")


def test_scope_defaults_to_university_wide(monkeypatch):
    use(monkeypatch, fake_client(VALID.replace(', "scope": "campus"', "")))
    summary, _ = nlp_summarizer.summarize("Fire")
    assert summary.scope == "university_wide"


def test_connection_error_means_ai_unavailable(monkeypatch):
    error = openai.APIConnectionError(request=httpx.Request("POST", "https://api.openai.com"))
    use(monkeypatch, fake_client(error=error))
    assert nlp_summarizer.summarize("Fire") == (None, False)


def test_missing_api_key_means_ai_unavailable(monkeypatch):
    monkeypatch.setattr(nlp_summarizer, "_client", None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert nlp_summarizer.summarize("Fire") == (None, False)


@pytest.mark.parametrize("content", ["not json", '{"building_name": "UW1"}', '{"severity": "high"'])
def test_bad_answer_is_not_an_outage(monkeypatch, content):
    use(monkeypatch, fake_client(content))
    assert nlp_summarizer.summarize("Fire") == (None, True)
