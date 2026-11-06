# Health API

## `GET /api/health`

Liveness check, also used by CI to confirm which commit is deployed.

**200**
```json
{"status": "ok", "version": "<git commit SHA>"}
```

| Field | Meaning |
|---|---|
| `status` | Always `"ok"` when the server can answer |
| `version` | The full commit SHA the server was built from, read from Render's `RENDER_GIT_COMMIT` environment variable; `"unknown"` when it isn't set (e.g. local runs) |

No authentication. The commit SHA is already public (the repository is public), so exposing it leaks nothing.

## Test plan (`backend/test_api.py`)

1. With `RENDER_GIT_COMMIT` set → `version` equals it.
2. Without it → `version` is `"unknown"`.
