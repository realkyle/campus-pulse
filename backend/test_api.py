from fastapi.testclient import TestClient

import main

# Not used as a context manager, so the startup event (the RSS/OpenAI polling loops) never runs.
client = TestClient(main.app)


def test_removed_netid_login_endpoint_returns_404():
    # The old typed-NetID login had no password; it must stay gone.
    response = client.post("/api/login", json={"netid": "someone"})
    assert response.status_code == 404
