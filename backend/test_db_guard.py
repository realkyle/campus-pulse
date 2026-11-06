import pytest

import database


def test_unmocked_database_call_fails_loudly():
    # database.py swallows ordinary exceptions; the conftest guard must still fail the test.
    with pytest.raises(pytest.fail.Exception):
        database.get_user_interactions("someone")
