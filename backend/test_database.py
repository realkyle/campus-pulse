"""Supabase access in database.py, with a fake client (never the real database)."""
import database


class FakeQuery:
    """Records the builder calls and serves rows like Supabase's query builder."""

    def __init__(self, rows: list[dict], calls: list):
        self._rows = rows
        self._calls = calls
        self._range = None

    def __getattr__(self, name):
        def record(*args, **kwargs):
            self._calls.append((name, args, kwargs))
            if name == "range":
                self._range = args
            return self
        return record

    def execute(self):
        rows = self._rows
        if self._range:
            start, end = self._range
            rows = rows[start:end + 1]
        return type("Result", (), {"data": rows})()


class FakeClient:
    def __init__(self, rows: list[dict]):
        self.rows = rows
        self.calls: list = []

    def table(self, name):
        self.calls.append(("table", (name,), {}))
        return FakeQuery(self.rows, self.calls)


def use(monkeypatch, client):
    monkeypatch.setattr(database, "_get_client", lambda: client)


def test_fetch_all_reads_every_page(monkeypatch):
    rows = [{"id": i} for i in range(database.PAGE_SIZE * 2 + 5)]
    client = FakeClient(rows)
    use(monkeypatch, client)
    assert database.fetch_all_interactions() == rows
    assert [args for name, args, _ in client.calls if name == "range"] == [(0, 999), (1000, 1999), (2000, 2999)]


def test_fetch_all_exact_page_boundary(monkeypatch):
    rows = [{"id": i} for i in range(database.PAGE_SIZE)]
    use(monkeypatch, FakeClient(rows))
    assert len(database.fetch_all_interactions()) == database.PAGE_SIZE


def test_log_interaction_stores_category_and_series(monkeypatch):
    client = FakeClient([])
    use(monkeypatch, client)
    assert database.log_interaction("hash", "live-1", "technology", "hackathon")
    inserted = next(args[0] for name, args, _ in client.calls if name == "insert")
    assert {k: inserted[k] for k in ("hashed_netid", "event_id", "category", "series_key")} == {
        "hashed_netid": "hash", "event_id": "live-1", "category": "technology", "series_key": "hackathon"}


def test_user_interactions_are_filtered_by_user(monkeypatch):
    client = FakeClient([{"event_id": "live-1"}])
    use(monkeypatch, client)
    assert database.get_user_interactions("hash") == [{"event_id": "live-1"}]
    assert ("eq", ("hashed_netid", "hash"), {}) in client.calls


def test_user_interactions_empty_on_error(monkeypatch):
    def broken():
        raise RuntimeError("database down")
    monkeypatch.setattr(database, "_get_client", broken)
    assert database.get_user_interactions("hash") == []
