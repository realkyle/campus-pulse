import pytest

from building_coords import CAMPUS_CENTER, resolve_coordinates


def test_exact_abbreviations():
    assert resolve_coordinates("UW1") == (47.75884, -122.19067)
    assert resolve_coordinates("UW2") == (47.75872, -122.19133)
    assert resolve_coordinates("DISC") == (47.75902, -122.19201)
    assert resolve_coordinates("LIB") == (47.75979, -122.19136)
    assert resolve_coordinates("HH") == (47.76170, -122.19456)
    assert resolve_coordinates("NCH") == (47.76042, -122.19050)


def test_full_name_aliases():
    assert resolve_coordinates("DISCOVERY HALL") == resolve_coordinates("DISC")
    assert resolve_coordinates("LIBRARY") == resolve_coordinates("LIB")
    assert resolve_coordinates("HUSKY HALL") == resolve_coordinates("HH")
    assert resolve_coordinates("NORTH CREEK HALL") == resolve_coordinates("NCH")


def test_campus_fallback():
    assert resolve_coordinates("CAMPUS") == CAMPUS_CENTER
    assert resolve_coordinates("CAMPUS CENTER") == CAMPUS_CENTER


def test_unknown_building_returns_campus_center():
    assert resolve_coordinates("UNKNOWN BUILDING") == CAMPUS_CENTER
    assert resolve_coordinates("PARKING LOT Z") == CAMPUS_CENTER


def test_case_insensitive():
    assert resolve_coordinates("uw1") == resolve_coordinates("UW1")
    assert resolve_coordinates("disc") == resolve_coordinates("DISC")
    assert resolve_coordinates("library") == resolve_coordinates("LIB")


def test_whitespace_trimmed():
    assert resolve_coordinates("  UW1  ") == resolve_coordinates("UW1")


def test_partial_match():
    # "UW1" is contained in a key — should resolve to UW1 coords, not fallback
    result = resolve_coordinates("UW1 BUILDING")
    assert result != CAMPUS_CENTER


def test_partial_match_needs_whole_words():
    # "UW" is not UW1, and an unrelated word containing a code doesn't match it.
    assert resolve_coordinates("UW") == CAMPUS_CENTER
    assert resolve_coordinates("BLIBRARY ANNEX") == CAMPUS_CENTER
    assert resolve_coordinates("NEAR THE LIBRARY") == resolve_coordinates("LIB")


def test_every_prompt_code_has_coordinates():
    from building_coords import BUILDING_CODES, BUILDING_COORDS
    assert all(code in BUILDING_COORDS for code in BUILDING_CODES)


def test_mentions_campus_whole_word():
    from building_coords import mentions_campus
    assert mentions_campus("Police near UW1 on the Bothell campus")
    assert not mentions_campus("Alert at all campuses")


def test_every_building_code_has_a_name_in_the_prompt():
    from building_coords import BUILDING_CODES, BUILDING_NAMES
    from nlp_summarizer import SYSTEM_PROMPT
    assert set(BUILDING_NAMES) == set(BUILDING_CODES)
    for code in BUILDING_CODES:
        assert f"{code} = {BUILDING_NAMES[code]}" in SYSTEM_PROMPT


def test_prompt_shows_a_plain_json_schema():
    from nlp_summarizer import SYSTEM_PROMPT
    assert "JSON schema:\n{\n" in SYSTEM_PROMPT
    assert "{{" not in SYSTEM_PROMPT and "}}" not in SYSTEM_PROMPT


# ── Scope evidence guard (no pin without evidence in the text) ───────────────


from building_coords import effective_scope, has_campus_evidence  # noqa: E402


@pytest.mark.parametrize("text", [
    "Fire on the Bothell campus",
    "Police activity near Founders Hall",
    "Power outage in UW2",
    "Road closed on Campus Way NE",
    "Police at the Beardslee Blvd park-and-ride",
    "Gas leak near North Creek Hall",
])
def test_campus_evidence(text):
    assert has_campus_evidence(text)


@pytest.mark.parametrize("text", [
    "Traffic blocked near 15th Ave NE",            # a street elsewhere, despite "Ave NE"
    "A rabid bat was found on University Way NE",  # "Way NE", not Campus Way NE
    "Emergency response at the Husky Union Building",  # not Husky Hall
    "Fire alarm in Suzzallo Library",              # "Library" alone is too generic
    "Earthquake reported in the region",
])
def test_no_campus_evidence(text):
    assert not has_campus_evidence(text)


def test_effective_scope():
    # Naming the campus always pins it.
    assert effective_scope("Fire on the Bothell campus", "other_campus") == "campus"
    # The AI says campus but the text shows no evidence: listed for all UW, no pin, never hidden.
    assert effective_scope("Rabid bat on University Way NE", "campus") == "university_wide"
    # Evidence other than the name (a building) keeps the AI's campus label.
    assert effective_scope("Gas leak near North Creek Hall", "campus") == "campus"
    # Otherwise the AI's label stands.
    assert effective_scope("Fire in Lander Hall, Seattle", "other_campus") == "other_campus"
    assert effective_scope("Campuses close at noon", "university_wide") == "university_wide"


def test_effective_scope_when_the_ai_failed():
    assert effective_scope("Gas leak near North Creek Hall", None) == "campus"
    assert effective_scope("Smoke advisory for the region", None) == "university_wide"
