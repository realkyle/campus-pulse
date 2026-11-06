"""Which events may appear in the For You panel.

The campus calendar mixes student events with staff-only sessions and repeats
some events many times (e.g. 55 "Campus Tour" dates). Recommendations start
from this cleaned list; /api/events still serves everything.
"""
import re

# Audience phrases, not single words: "Faculty Mentorship for First- and
# Second-Year Students" mentions faculty but is a student event.
_STAFF_ONLY = re.compile(
    r"\bsponsored research\b"
    r"|\bfor (?:faculty|staff|administrators|employees)\b"
    r"|\ball staff\b"
    r"|\bfaculty organization\b"
    r"|\bemployee recognition\b",
    re.IGNORECASE,
)
_FOR_STUDENTS = re.compile(r"\bstudents?\b", re.IGNORECASE)
_NON_WORD = re.compile(r"[^a-z0-9]+")


def is_staff_only(title: str) -> bool:
    """True for events aimed at faculty/staff rather than students."""
    return bool(_STAFF_ONLY.search(title)) and not _FOR_STUDENTS.search(title)


def series_key(title: str) -> str:
    """Identifies a repeating series: the title, lowercased, punctuation and extra spaces removed."""
    return _NON_WORD.sub(" ", title.lower()).strip()


def student_candidates(events: list[dict]) -> list[dict]:
    """Events eligible for recommendations, in the given (soonest-first) order.

    Drops staff-only events and keeps only the first, i.e. next, date of each series.
    """
    seen_series: set[str] = set()
    candidates = []
    for event in events:
        if is_staff_only(event["title"]):
            continue
        key = series_key(event["title"])
        if key in seen_series:
            continue
        seen_series.add(key)
        candidates.append(event)
    return candidates
