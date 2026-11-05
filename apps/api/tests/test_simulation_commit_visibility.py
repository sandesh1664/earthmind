"""Session finalization must precede response delivery; no native execution is mocked as proof."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

from earthmind_api.dependencies import get_session
from earthmind_api.main import create_app
from earthmind_api.settings import Settings
from earthmind_contracts.simulation import DemandConfig, ScenarioResponse, ScenarioValidation
from starlette.types import Message, Scope


async def test_scenario_commit_finishes_before_201_response_headers(monkeypatch) -> None:
    token = "test-only-not-a-working-development-secret"
    app = create_app(Settings(dev_write_token=token))
    committed: list[bool] = []

    async def session_dependency():
        yield object()
        committed.append(True)

    app.dependency_overrides[get_session] = session_dependency
    identifier, network_id = uuid4(), uuid4()
    result = ScenarioResponse(
        id=identifier,
        network_version_id=network_id,
        network_version_label="request-order-contract-fixture",
        name="Commit visibility contract fixture",
        demand=DemandConfig(),
        configuration_checksum="a" * 64,
        created_at=datetime.now(UTC),
        validation=ScenarioValidation(valid=True),
    )
    monkeypatch.setattr(
        "earthmind_api.simulation_routes.create_scenario", AsyncMock(return_value=result)
    )
    payload = json.dumps({"name": result.name, "network_version_id": str(network_id)}).encode()
    delivered = False
    messages: list[Message] = []

    async def receive() -> Message:
        nonlocal delivered
        if not delivered:
            delivered = True
            return {"type": "http.request", "body": payload, "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message: Message) -> None:
        if message["type"] == "http.response.start":
            assert committed == [True], "201 must not be sent before transaction finalization"
            assert message["status"] == 201
        messages.append(message)

    scope: Scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/v1/scenarios",
        "raw_path": b"/api/v1/scenarios",
        "root_path": "",
        "query_string": b"",
        "headers": [
            (b"host", b"test"),
            (b"content-type", b"application/json"),
            (b"content-length", str(len(payload)).encode()),
            (b"x-earthmind-dev-token", token.encode()),
        ],
        "client": ("127.0.0.1", 12345),
        "server": ("test", 80),
    }
    await app(scope, receive, send)
    body = b"".join(
        item.get("body", b"") for item in messages if item["type"] == "http.response.body"
    )
    assert json.loads(body)["id"] == str(identifier)
    assert committed == [True]
