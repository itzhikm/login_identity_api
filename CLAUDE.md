# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Status

Implemented. `main.py` is the live service; `login_identity_api_spec.md` is the original spec but the code has diverged from it in two places — see "Spec divergences" below.

## Architecture

A FastAPI read-only lookup service over a PostgreSQL `identity_links` table. The table is populated daily by a separate identity pipeline job (out of scope for this repo); this API only reads.

The table has three per-system columns: `system_1_email`, `system_2_email`, `system_3_email`. A row groups one identity across the three systems (any column may be NULL). The endpoint picks which column to filter on based on the digit after `@` in the input email, then returns the non-NULL columns from the matching row.

```sql
-- For email "a@1", column resolves to system_1_email:
SELECT system_1_email, system_2_email, system_3_email
FROM identity_links WHERE system_1_email = %s
```

If no row matches, the endpoint returns the input email alone in `linked_identities` rather than 404 — this is by design.

## Layout

Files live flat at the repo root, not under `api/`:

```
.
├── Dockerfile
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
├── main.py
├── tests/
│   ├── conftest.py
│   └── test_main.py
└── scripts/
    └── run_docker.cmd
```

Note: `pytest.ini` sets `pythonpath = api` and `requirements-dev.txt` references `-r api/requirements.txt` — both are stale leftovers from the spec's `api/` layout. Tests still run because `main.py` is at the root and importable directly; fix these if they cause friction.

## Constraints worth knowing before editing

- **Email path param regex is `^[a-zA-Z0-9._+-]+@[123]$`** — the domain is a single literal digit `1`, `2`, or `3`, not a real domain. This is intentional (matches the upstream pipeline's data shape). Don't "fix" it to a normal email regex. Validation failure must return 422.
- **Auth is a static API key** via `X-API-Key` header, compared against env var `API_KEY`. Missing or wrong key → 403 (not 401, per spec). `APIKeyHeader(auto_error=False)` is required so the dependency controls the status code.
- **Use psycopg2 with `%s` placeholders** — never f-string user input into SQL. The column name *is* f-stringed in, but only after being looked up in a hardcoded `COLUMN_BY_DOMAIN` dict keyed on the regex-validated digit; raw input never reaches the SQL string.
- **Always close the DB connection in a `finally` block.** Connections are opened per-request, not pooled — follow that pattern unless changing it deliberately.
- **Rate limit: 60 req/min per client IP** via slowapi, keyed by `get_remote_address`. The `RateLimitExceeded` handler returns JSON 429 instead of slowapi's default plain-text response. Keep `request: Request` in any handler decorated with `@limiter.limit(...)` — slowapi extracts the key from it.
- **`API_KEY` is read at import time** (`os.environ["API_KEY"]`) — the process fails to start if it's missing, rather than 500-ing on first request. Tests in `tests/conftest.py` set it before importing `main`.

## Spec divergences

If you read `login_identity_api_spec.md`, note these two intentional differences from the current code:

1. The spec's older draft mentioned `emails text[]` with `@>` array containment. The actual schema and code use three separate columns with equality on the column matching the email's domain digit.
2. The spec puts everything under `api/`. The repo has files at the root.

## Env vars

`POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `API_KEY`. All required at runtime. Loaded via `python-dotenv` from `.env` in dev.

## Build & run

```bash
docker build -t login-identity-api .
docker run --rm -p 8000:8000 \
  -e POSTGRES_HOST=... -e POSTGRES_PORT=5432 \
  -e POSTGRES_DB=identity_db -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=secret -e API_KEY=my-secret-key \
  login-identity-api
```

Or for local dev: `python main.py` (uses `uvicorn` with `reload=True`).

Swagger UI lives at `http://localhost:8000/docs` automatically (FastAPI default — no setup needed).

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

`tests/conftest.py` sets `API_KEY` before importing `main` and provides a `mock_db` fixture that monkeypatches `get_connection` — tests don't touch a real Postgres. When adding tests for new SQL, assert the exact SQL string and params via `cursor.execute.assert_called_once_with(...)` to keep injection-safety regressions visible (see `test_identities_uses_column_matching_email_domain`).

No lint config or CI is defined yet. If adding one, update this file.