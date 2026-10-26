from collections.abc import AsyncIterator

import httpx
import pytest
from earthmind_api.request_limits import GeoBodyLimitMiddleware
from earthmind_api.security import require_dev_write
from earthmind_api.settings import Settings
from fastapi import Depends, FastAPI, Request
from pydantic import ValidationError


def secured_app(token: str | None = "test-only-development-token-not-a-working-secret") -> FastAPI:
    app = FastAPI()
    app.state.settings = Settings(dev_write_token=token)
    app.add_middleware(GeoBodyLimitMiddleware, max_bytes=1024)

    @app.post("/api/v1/regions", dependencies=[Depends(require_dev_write)])
    async def create(request: Request) -> dict[str, object]:
        return {"accepted": await request.json()}

    return app


@pytest.mark.parametrize("key", [None, "wrong", ""])
async def test_development_writes_require_private_token(key: str | None) -> None:
    headers = {} if key is None else {"X-Earthmind-Dev-Token": key}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=secured_app()), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/regions", json={}, headers=headers)
    assert response.status_code == 403


async def test_token_authorizes_only_configured_development_gate() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=secured_app()), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/regions",
            json={"probe": True},
            headers={"X-Earthmind-Dev-Token": "test-only-development-token-not-a-working-secret"},
        )
        schema = (await client.get("/openapi.json")).json()
    assert response.status_code == 200
    assert response.json() == {"accepted": {"probe": True}}
    assert schema["components"]["securitySchemes"]["DevelopmentWriteToken"]["type"] == "apiKey"


async def test_unconfigured_write_gate_is_disabled() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=secured_app(None)), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/regions", json={})
    assert response.status_code == 503


async def test_streaming_body_limit_cannot_be_bypassed_without_content_length() -> None:
    async def content() -> AsyncIterator[bytes]:
        yield b'{"payload":"'
        yield b"a" * 700
        yield b"b" * 700
        yield b'"}'

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=secured_app()), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/regions", content=content(), headers={"Content-Type": "application/json"}
        )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


def test_short_tokens_and_unbounded_limits_are_rejected_without_exposing_values() -> None:
    with pytest.raises(ValidationError) as error:
        Settings(dev_write_token="private-short-value", geo_max_request_bytes=999999999)
    assert "private-short-value" not in str(error.value)
    assert Settings(dev_write_token="").dev_write_token is None
