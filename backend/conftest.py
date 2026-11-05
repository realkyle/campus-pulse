import pytest

import database


@pytest.fixture(autouse=True)
def block_real_database(monkeypatch):
    """Fail any test that reaches the real Supabase client.

    The query helpers in database.py catch every Exception and return an empty
    result, so an ordinary exception here would be swallowed and the test would
    still pass. pytest.fail raises a BaseException subclass, which those
    handlers don't catch, so the test fails loudly instead.
    """

    def _fail():
        pytest.fail(
            "Test reached the real Supabase client. "
            "Mock the database functions it calls instead."
        )

    monkeypatch.setattr(database, "_get_client", _fail)
