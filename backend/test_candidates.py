"""Which events are eligible for the For You panel (recommender PR 1)."""
import pytest

from candidates import is_staff_only, series_key, student_candidates


def event(event_id: str, title: str, category: str = "social") -> dict:
    return {"id": event_id, "title": title, "category": category}


# Titles taken from the real campus feed (Nov 2026).
@pytest.mark.parametrize("title", [
    "Sponsored Research Virtual Pre-Award/Cost Transfer Office Hours",
    "Sponsored Research Post-Award Office Hours for Faculty",
    "Sponsored Research In-Person Open Office Hours",
    "Foundations of Community Engagement Workshop for Faculty",
    "Virtual Office Hours for Administrators",
    "General Faculty Organization - General Meeting",
    "Employee Recognition Event",
    "Autumn Academic Affairs All Staff Meeting",
])
def test_staff_only_titles(title):
    assert is_staff_only(title)


@pytest.mark.parametrize("title", [
    "ECE Compass – Faculty Mentorship for First- and Second-Year Students",  # mentions faculty, but for students
    "Campus Tour",
    "AI Community of Practice (CoP)",
    "Resume Workshop",
    "Meet the Staff of the Writing Center",  # "staff" without a staff-only audience phrase
])
def test_student_titles(title):
    assert not is_staff_only(title)


def test_series_key_ignores_case_spacing_and_punctuation():
    assert series_key("Campus  Tour") == series_key("campus tour!") == "campus tour"
    assert series_key("Information Session and Campus Tour") != series_key("Campus Tour")


def test_candidates_drop_staff_and_keep_next_date_of_each_series():
    events = [  # already soonest-first, as get_all_events() returns them
        event("e1", "Campus Tour"),
        event("e2", "Sponsored Research Virtual Office Hours for Faculty"),
        event("e3", "Resume Workshop", "business"),
        event("e4", "Campus Tour"),
        event("e5", "campus tour"),
    ]
    assert [e["id"] for e in student_candidates(events)] == ["e1", "e3"]


def test_candidates_of_empty_list():
    assert student_candidates([]) == []
