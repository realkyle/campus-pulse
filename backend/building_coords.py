import re
from typing import Optional

# Campus identity: used in the AI prompt and to recognize alerts about this campus.
CAMPUS_NAME = "UW Bothell"
CAMPUS_KEYWORDS = ("bothell",)

# Campus center: fallback pin location
CAMPUS_CENTER = (47.75927, -122.19120)

# Building codes the AI may answer with (the prompt is built from this list, so
# the two can't drift apart). Each must be a key of BUILDING_COORDS.
BUILDING_CODES = ("UW1", "UW2", "DISC", "LIB", "ARC", "HH", "NCH", "CC")

# Names the AI is told for each code, so "near the Campus Center" maps to CC.
BUILDING_NAMES = {
    "UW1": "Founders Hall (UW1)",
    "UW2": "Commons Hall (UW2)",
    "DISC": "Discovery Hall",
    "LIB": "Library (LB1, LBA annex)",
    "ARC": "Activities and Recreation Center",
    "HH": "Husky Hall",
    "NCH": "North Creek Hall",
    "CC": "Campus Center",
}

# Streets at or next to this campus, told to the AI. (v3: "108th/110th Ave NE" were
# removed; v2 listed them and Seattle "... Ave NE" alerts started getting pinned here.)
CAMPUS_STREETS = ("Campus Way NE", "Beardslee Blvd")

# Text that proves an alert is about this campus. Only distinctive terms: "Library"
# alone also matches Seattle's libraries, and numbered avenues exist in other cities.
CAMPUS_EVIDENCE = (
    *CAMPUS_KEYWORDS,
    "UW1", "UW2", "DISC", "NCH",
    "Founders Hall", "Commons Hall", "Discovery Hall", "Husky Hall", "North Creek Hall",
    "Activities and Recreation Center",
    *CAMPUS_STREETS,
)

# Keyed by codes and full names. Coordinates are (lat, lng).
BUILDING_COORDS: dict[str, tuple[float, float]] = {
    "UW1": (47.75884, -122.19067),
    "UW2": (47.75872, -122.19133),
    "DISC": (47.75902, -122.19201),
    "DISCOVERY HALL": (47.75902, -122.19201),
    "LIB": (47.75979, -122.19136),
    "LIBRARY": (47.75979, -122.19136),
    "ARC": (47.76005, -122.19033),
    "ACTIVITIES AND RECREATION CENTER": (47.76005, -122.19033),
    "HH": (47.76170, -122.19456),
    "HUSKY HALL": (47.76170, -122.19456),
    "NCH": (47.76042, -122.19050),
    "NORTH CREEK HALL": (47.76042, -122.19050),
    "CC": (47.75927, -122.19120),
    "CAMPUS CENTER": (47.75927, -122.19120),
    "CAMPUS": (47.75927, -122.19120),
}


def resolve_coordinates(building_name: str) -> tuple[float, float]:
    """Map a building code or name to (lat, lng); unknown names → campus center."""
    key = building_name.strip().upper()
    if key in BUILDING_COORDS:
        return BUILDING_COORDS[key]
    # A known name appearing as whole words, e.g. "NEAR THE LIBRARY". Whole words
    # so that "UW" doesn't resolve to UW1.
    for name, coords in BUILDING_COORDS.items():
        if re.search(rf"\b{re.escape(name)}\b", key):
            return coords
    return CAMPUS_CENTER


def mentions_campus(text: str) -> bool:
    """True if the text names this campus (whole word, case-insensitive)."""
    return any(re.search(rf"\b{re.escape(k)}\b", text, re.IGNORECASE) for k in CAMPUS_KEYWORDS)


def has_campus_evidence(text: str) -> bool:
    """True if the text itself shows the alert is about this campus (CAMPUS_EVIDENCE, whole words)."""
    return any(re.search(rf"\b{re.escape(term)}\b", text, re.IGNORECASE) for term in CAMPUS_EVIDENCE)


def effective_scope(text: str, ai_scope: Optional[str]) -> str:
    """The scope the map uses: the AI's label, checked against the text.

    - Naming the campus always makes it a campus alert.
    - The AI may only put a pin here if the text has evidence of this campus;
      otherwise the alert is listed for all UW campuses: shown, never hidden,
      but without a misleading pin (the evaluation found Seattle alerts pinned here).
    """
    if mentions_campus(text):
        return "campus"
    if ai_scope is None:  # the AI failed: pin only with evidence, otherwise list it
        return "campus" if has_campus_evidence(text) else "university_wide"
    if ai_scope == "campus" and not has_campus_evidence(text):
        return "university_wide"
    return ai_scope
