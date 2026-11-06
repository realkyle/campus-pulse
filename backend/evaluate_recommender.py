"""Offline evaluation: does the hybrid ranking beat "just show what's popular"?

Leave-last-out: for each user with at least two known clicks, hide their most
recent click, rank every series they haven't clicked yet using everything else,
and check whether the hidden series lands in the top k. (Already-clicked series
are excluded for both methods: the question is whether we can predict something
new for them.) Compares hit rate@k against a popularity
baseline built from the same data.

Run with real data (reads backend/.env; read-only):
    ./venv/bin/python evaluate_recommender.py
"""
from collections import Counter, defaultdict
from datetime import datetime

from scoring import InteractionStats, Resolve, UserProfile, rank, series_and_category


def leave_last_out(rows: list[dict], resolve: Resolve, k: int = 5) -> dict:
    """Hit rate@k of the hybrid ranking vs. a popularity baseline."""
    mapped = []
    for row in rows:
        known = series_and_category(row, resolve)
        if known and row.get("timestamp"):
            mapped.append({**row, "series_key": known[0], "category": known[1]})

    # One pseudo-event per known series; alphabetical so "soonness" is neutral noise for both.
    category_of = {r["series_key"]: r["category"] for r in mapped}
    catalog = [{"id": s, "title": s, "category": c} for s, c in sorted(category_of.items())]

    by_user: dict[str, list[dict]] = defaultdict(list)
    for row in mapped:
        by_user[row["hashed_netid"]].append(row)

    model_hits = popular_hits = evaluated = 0
    for user_rows in by_user.values():
        if len({r["series_key"] for r in user_rows}) < 2:
            continue
        user_rows.sort(key=lambda r: r["timestamp"])
        held_out = user_rows[-1]
        history = user_rows[:-1]
        train = [r for r in mapped if r is not held_out]
        now = datetime.fromisoformat(held_out["timestamp"])
        stats = InteractionStats.build(train, now=now, resolve=resolve)
        profile = UserProfile.from_rows(history, resolve=resolve)

        if held_out["series_key"] in profile.series:
            continue  # a repeat click; nothing new to predict
        unseen = [e for e in catalog if e["id"] not in profile.series]
        top_model = [e["id"] for e in rank(unseen, profile, stats, major_categories=[], limit=k)]
        counts = Counter(r["series_key"] for r in train if r["series_key"] not in profile.series)
        top_popular = [s for s, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:k]]

        evaluated += 1
        model_hits += held_out["series_key"] in top_model
        popular_hits += held_out["series_key"] in top_popular

    return {
        "users_evaluated": evaluated,
        "k": k,
        "hybrid_hit_rate": model_hits / evaluated if evaluated else None,
        "popularity_hit_rate": popular_hits / evaluated if evaluated else None,
    }


def _main() -> None:
    from dotenv import load_dotenv

    load_dotenv()
    from candidates import series_key
    from database import fetch_all_interactions
    from events_fetcher import fetch_live_events

    rows = fetch_all_interactions()
    live, _ = fetch_live_events(limit=1000)
    by_id = {e["id"]: e for e in live}

    def resolve(event_id: str) -> tuple[str, str] | None:
        event = by_id.get(event_id)
        return (series_key(event["title"]), event["category"]) if event else None

    result = leave_last_out(rows, resolve)
    print(f"clicks: {len(rows)}  users evaluated: {result['users_evaluated']}  (k = {result['k']})")
    if result["users_evaluated"]:
        print(f"hybrid hit rate@{result['k']}:     {result['hybrid_hit_rate']:.2f}")
        print(f"popularity hit rate@{result['k']}: {result['popularity_hit_rate']:.2f}")
    else:
        print("Not enough users with 2+ known clicks to evaluate yet.")


if __name__ == "__main__":
    _main()
