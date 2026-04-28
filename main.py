import os

import psycopg2
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Path, Request, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse

load_dotenv()

EMAIL_PATTERN = r"^[a-zA-Z0-9._+-]+@[123]$"

# Hardcoded mapping — keys are the only domain digits the regex allows,
# values are trusted column names. Never derive a column name from raw input.
COLUMN_BY_DOMAIN = {
    "1": "system_1_email",
    "2": "system_2_email",
    "3": "system_3_email",
}

API_KEY = os.environ["API_KEY"]
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(key: str = Security(api_key_header)) -> None:
    if key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")


def get_connection():
    return psycopg2.connect(
        host=os.environ["POSTGRES_HOST"],
        port=os.environ["POSTGRES_PORT"],
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )


class IdentityResponse(BaseModel):
    input: str
    linked_identities: list[str]


limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Login Identity API")
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get(
    "/identities/{email}",
    response_model=IdentityResponse,
    dependencies=[Depends(require_api_key)],
)
@limiter.limit("60/minute")
def get_identities(
    request: Request,
    email: str = Path(..., pattern=EMAIL_PATTERN),
) -> IdentityResponse:
    column = COLUMN_BY_DOMAIN[email.rsplit("@", 1)[1]]
    sql = (
        "SELECT system_1_email, system_2_email, system_3_email "
        f"FROM identity_links WHERE {column} = %s"
    )
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(sql, (email,))
            row = cur.fetchone()
        if row is None:
            return IdentityResponse(input=email, linked_identities=[email])
        return IdentityResponse(
            input=email,
            linked_identities=[e for e in row if e is not None],
        )
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
