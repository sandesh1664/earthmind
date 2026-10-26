"""Explicit local-development write authorization; not a user login system."""

from secrets import compare_digest
from typing import Annotated, cast

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from earthmind_api.settings import Settings

write_key = APIKeyHeader(
    name="X-Earthmind-Dev-Token",
    scheme_name="DevelopmentWriteToken",
    description=(
        "Local developer write authorization. "
        "Not user authentication or public deployment security."
    ),
    auto_error=False,
)


async def require_dev_write(
    request: Request, supplied: Annotated[str | None, Security(write_key)]
) -> None:
    settings = cast(Settings, request.app.state.settings)
    token = settings.dev_write_token
    if token is None:
        raise HTTPException(status_code=503, detail="Development writes are disabled")
    if supplied is None or not compare_digest(supplied.encode(), token.get_secret_value().encode()):
        raise HTTPException(status_code=403, detail="Developer write authorization required")
