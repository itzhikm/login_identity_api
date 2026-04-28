# Login Identity API Spec for Claude Code

## Overview
A FastAPI service that exposes a single endpoint to retrieve all linked identities
for a given email address. The API queries the `identity_links` table in PostgreSQL,
which is populated daily by the identity pipeline job.

---

## Project Structure
```
api/
├── Dockerfile
├── requirements.txt
└── main.py
```

---

## Environment Variables
```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=identity_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=secret
```

---

## main.py

### Endpoints

**GET /identities/{email}**
```
Description:
  Returns all identities linked to the given email address.
  If the email is not found in any group, returns only the input email.

Path parameter:
  email: str  – e.g. a@1

Response model: IdentityResponse
  {
    "input":             str,        # the requested email
    "linked_identities": list[str]   # all emails in the same group including input
  }

Query:
  -- Pick column by the digit after '@' (1/2/3 → system_<n>_email)
  SELECT system_1_email, system_2_email, system_3_email
  FROM identity_links
  WHERE system_<n>_email = %s

Behavior:
  - If row found     → return non-NULL values from the three columns
  - If row not found → return { "input": email, "linked_identities": [email] }
  - Always close DB connection in finally block
```

**GET /health**
```
Description:
  Health check endpoint for Docker and load balancer probes.

Response:
  { "status": "ok" }
```

---

## Response Examples

**Email found in a group:**
```
GET /identities/a@1

{
  "input": "a@1",
  "linked_identities": ["a@1", "b@2", "ddd@3"]
}
```

**Email not found in any group:**
```
GET /identities/x@1

{
  "input": "x@1",
  "linked_identities": ["x@1"]
}
```

---

## Security

**API Key authentication:**
```
- Read API key from environment variable: API_KEY
- Expect header: X-API-Key
- Return HTTP 403 if key is missing or invalid
```

**Input validation:**
```
- email path parameter must match pattern: ^[a-zA-Z0-9._+-]+@[123]$
- Return HTTP 422 if pattern does not match
```

---

## Swagger UI
Available automatically at:
```
http://localhost:8000/docs
```

---

## Dockerfile
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
ENTRYPOINT ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## requirements.txt
```
fastapi==0.110.0
uvicorn==0.29.0
psycopg2-binary==2.9.9
slowapi==0.1.9
```

---

## Local Debug Run
```bash
docker build -t login-identity-api .

docker run --rm -p 8000:8000 login-identity-api \
  -e POSTGRES_HOST=localhost \
  -e POSTGRES_PORT=5432 \
  -e POSTGRES_DB=identity_db \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=secret \
  -e API_KEY=my-secret-key
```

---

## Implementation Notes
- Use psycopg2 for DB connection
- Use %s placeholders for all queries, never f-strings with user input
- The column name (system_1_email / system_2_email / system_3_email) is selected
  via a hardcoded dict keyed on the regex-validated domain digit — never built
  from raw input
- Always close DB connection in finally block
- Swagger UI is available out of the box via FastAPI — no extra configuration needed
