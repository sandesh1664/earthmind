"""Bound M02 JSON buffering before request parsing or geometry processing."""

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class GeoBodyLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        bounded = (
            path == "/api/v1/regions"
            or path.startswith("/api/v1/geo/")
            or path.startswith(("/api/v1/scenarios", "/api/v1/simulations", "/api/v1/comparisons"))
        )
        if scope["type"] != "http" or scope.get("method") != "POST" or not bounded:
            await self.app(scope, receive, send)
            return
        maximum = (
            min(self.max_bytes, 65536)
            if path.startswith(("/api/v1/scenarios", "/api/v1/simulations", "/api/v1/comparisons"))
            else self.max_bytes
        )
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > maximum:
                response = JSONResponse(
                    {
                        "error": {
                            "code": "payload_too_large",
                            "message": (
                                "Simulation request exceeds its byte limit"
                                if path.startswith(
                                    (
                                        "/api/v1/scenarios",
                                        "/api/v1/simulations",
                                        "/api/v1/comparisons",
                                    )
                                )
                                else "Geospatial request exceeds its byte limit"
                            ),
                        }
                    },
                    status_code=413,
                )
                await response(scope, receive, send)
                return
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
