"""Hybrid event ranking for the For You panel (contract: api/recommendations.md, Ranking).

Pure functions on plain data, so every rule is unit-tested without a database:
- UserProfile: what one user clicked (categories, series).
- InteractionStats: what everyone clicked (recent popularity, item-item co-clicks),
  rebuilt hourly in the background.
- rank(): scores candidates with weighted, explainable terms and attaches a reason.

Replaces the earlier SVD model, which can't learn from clicks-only data: with every
"rating" equal to 1, predicting 1 for everything is a perfect fit.
"""
import math
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from candidates import series_key

WEIGHTS = {"category": 3.0, "series": 2.0, "co_click": 1.5, "popularity": 1.0, "soonness": 1.0}
CO_CLICK_MIN_CLICKS = 50          # below this, co-click similarity is noise and is ignored
POPULARITY_WINDOW = timedelta(days=7)

# event_id → (series_key, category) for rows stored before those columns existed.
Resolve = Callable[[str], tuple[str, str] | None]


def series_and_category(row: dict, resolve: Resolve) -> tuple[str, str] | None:
    """A click's (series_key, category): stored on the row, else looked up by event ID."""
    if row.get("series_key") and row.get("category"):
        return row["series_key"], row["category"]
    return resolve(row["event_id"])


@dataclass(frozen=True)
class UserProfile:
    clicks: int                        # distinct events clicked (known ones)
    category_share: dict[str, float]   # category → share of those clicks
    series: frozenset[str]
    event_ids: frozenset[str] = frozenset()

    @classmethod
    def from_rows(cls, rows: list[dict], resolve: Resolve) -> "UserProfile":
        """Build from this user's interaction rows. Repeat clicks on one event count once."""
        known: dict[str, tuple[str, str]] = {}
        for row in rows:
            mapped = series_and_category(row, resolve)
            if mapped:  # one-off events that already left the calendar can't be mapped
                known[row["event_id"]] = mapped
        categories = Counter(category for _, category in known.values())
        total = len(known)
        return cls(
            clicks=total,
            category_share={c: n / total for c, n in categories.items()},
            series=frozenset(series for series, _ in known.values()),
            event_ids=frozenset(known),
        )


@dataclass(frozen=True)
class InteractionStats:
    total_clicks: int
    popularity: dict[str, float]               # series → recent clicks / most-clicked series
    similar: dict[str, dict[str, float]]       # series → {other series: cosine similarity}

    @classmethod
    def build(cls, rows: list[dict], now: datetime, resolve: Resolve) -> "InteractionStats":
        """Aggregate all users' clicks: 7-day popularity and item-item co-click similarity.

        Similarity is cosine over users: |users who clicked both| / sqrt(|A| · |B|).
        It suits implicit, positive-only data (a click, never a rating).
        """
        recent: Counter[str] = Counter()
        series_by_user: dict[str, set[str]] = defaultdict(set)
        for row in rows:
            mapped = series_and_category(row, resolve)
            if not mapped:
                continue
            series = mapped[0]
            series_by_user[row["hashed_netid"]].add(series)
            timestamp = row.get("timestamp")
            if timestamp and now - datetime.fromisoformat(timestamp) <= POPULARITY_WINDOW:
                recent[series] += 1

        top = max(recent.values(), default=0)
        popularity = {s: n / top for s, n in recent.items()} if top else {}

        users_per_series: Counter[str] = Counter()
        both: Counter[tuple[str, str]] = Counter()
        for clicked in series_by_user.values():
            users_per_series.update(clicked)
            for a in clicked:
                for b in clicked:
                    if a != b:
                        both[(a, b)] += 1
        similar: dict[str, dict[str, float]] = defaultdict(dict)
        for (a, b), n in both.items():
            similar[a][b] = n / math.sqrt(users_per_series[a] * users_per_series[b])

        return cls(total_clicks=len(rows), popularity=popularity, similar=dict(similar))


def _reason(terms: dict[str, float], has_clicks: bool, category: str) -> str:
    # The most specific factor present explains the rank best.
    if terms["series"] > 0:
        return "Another date of an event you opened"
    if terms["co_click"] > 0:
        return "Popular with students who like what you like"
    if terms["category"] > 0:
        return f"Because you liked {category.title()} events" if has_clicks else "Matches your major"
    if terms["popularity"] > 0:
        return "Popular on campus this week"
    return "Coming up soon"


def rank(
    candidates: list[dict],
    profile: UserProfile,
    stats: InteractionStats,
    major_categories: list[str],
    limit: int,
) -> list[dict]:
    """Top `limit` candidates by score, as copies with a "reason" field.

    `candidates` must be soonest-first; ties keep that order.
    """
    use_co_clicks = stats.total_clicks >= CO_CLICK_MIN_CLICKS
    n = len(candidates)
    scored = []
    for position, event in enumerate(candidates):
        series = series_key(event["title"])
        category = event["category"]
        if profile.clicks:
            category_affinity = profile.category_share.get(category, 0.0)
        else:
            category_affinity = 1.0 if category in major_categories else 0.0
        co_click = 0.0
        if use_co_clicks:
            co_click = max((stats.similar.get(s, {}).get(series, 0.0) for s in profile.series if s != series), default=0.0)
        terms = {
            "category": category_affinity,
            # Other dates of a series the user opened; not the very event they opened.
            "series": 1.0 if series in profile.series and event["id"] not in profile.event_ids else 0.0,
            "co_click": co_click,
            "popularity": stats.popularity.get(series, 0.0),
            "soonness": 1.0 - position / n,
        }
        score = sum(WEIGHTS[name] * value for name, value in terms.items())
        scored.append((-score, position, {**event, "reason": _reason(terms, profile.clicks > 0, category)}))

    scored.sort(key=lambda item: (item[0], item[1]))
    return [event for _, _, event in scored[:limit]]
