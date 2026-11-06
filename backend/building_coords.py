import re

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

# Streets at or next to this campus; any other named street or building is elsewhere.
CAMPUS_STREETS = ("Campus Way NE", "Beardslee Blvd", "108th Ave NE", "110th Ave NE")

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
