# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Status

The implementation does not yet exist. `login_identity_api_spec.md` is the source of truth for what to build. The spec lays out file layout, dependencies, endpoint contracts, env vars, and the Dockerfile verbatim — implement to that spec rather than re-deriving choices.

## Architecture

A FastAPI read-only lookup service over a PostgreSQL `identity_links` table. The table is populated daily by a separate identity pipeline job (out of scope for this repo); this API only reads.

The core query relies on PostgreSQL array containment:

```sql
SELECT emails FROM identity_links WHERE emails @> ARRAY[%s]
```

A row stores a group of linked emails as a `text[]`; the GIN index on `emails` makes `@>` fast. If no row matches, the endpoint returns the input email alone in `linked_identities` rather than 404 — this is by design.

Intended layout (everything lives flat under `api/`):

```
api/
├── Dockerfile
├── requirements.txt
└── main.py
```

## Constraints worth knowing before editing

- **Email path param regex is `^[a-zA-Z0-9._+-]+@[123]$`** — the domain is a single literal digit `1`, `2`, or `3`, not a real domain. This is intentional (matches the upstream pipeline's data shape). Don't "fix" it to a normal email regex. Validation failure must return 422.
- **Auth is a static API key** via `X-API-Key` header, compared against env var `API_KEY`. Missing or wrong key → 403 (not 401, per spec).
- **Use psycopg2 with `%s` placeholders** — never f-string user input into SQL. The spec calls this out explicitly.
- **Always close the DB connection in a `finally` block.** The spec opens connections per-request rather than pooling; follow that pattern unless changing it deliberately.
- `slowapi` is listed in requirements — rate limiting is expected, even though the spec doesn't detail the policy.

## Env vars

`POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `API_KEY`. All required at runtime.

## Build & run

```bash
docker build -t login-identity-api ./api
docker run --rm -p 8000:8000 \
  -e POSTGRES_HOST=... -e POSTGRES_PORT=5432 \
  -e POSTGRES_DB=identity_db -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=secret -e API_KEY=my-secret-key \
  login-identity-api
```

Swagger UI lives at `http://localhost:8000/docs` automatically (FastAPI default — no setup needed).

No test suite, lint config, or CI is defined yet. If adding one, update this file.