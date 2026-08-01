"""Token-protected WebSocket proxy for the upstream realtime endpoint."""

from __future__ import annotations

import asyncio
import hmac
import threading
from collections.abc import Iterable
from urllib.parse import parse_qs, urlsplit


def _token_from_request(path: str, headers) -> str:
    query = parse_qs(urlsplit(path).query)
    query_token = str((query.get("access_token") or [""])[0])
    if query_token:
        return query_token
    authorization = str(headers.get("Authorization", ""))
    if authorization.startswith("Bearer "):
        return authorization[7:]
    return ""


class AuthenticatedWebSocketProxy:
    """Expose a public socket while keeping speech-to-speech loopback-only."""

    def __init__(self, host: str, port: int, upstream_port: int, tokens: str | Iterable[str]):
        self.host = host
        self.port = int(port)
        self.upstream_port = int(upstream_port)
        raw_tokens = [tokens] if isinstance(tokens, str) else list(tokens)
        self.tokens = tuple(dict.fromkeys(token for token in raw_tokens if token))
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._server = None
        self._ready = threading.Event()
        self._error: BaseException | None = None

    async def _handler(self, client) -> None:
        request = getattr(client, "request", None)
        path = getattr(request, "path", "/")
        headers = getattr(request, "headers", {})
        supplied_token = _token_from_request(path, headers)
        if self.tokens and not any(hmac.compare_digest(supplied_token, token) for token in self.tokens):
            await client.close(code=4401, reason="Unauthorized")
            return

        import websockets

        clean_path = urlsplit(path).path or "/v1/realtime"
        upstream_url = f"ws://127.0.0.1:{self.upstream_port}{clean_path}"
        async with websockets.connect(upstream_url, max_size=None) as upstream:
            async def relay(source, destination):
                async for message in source:
                    await destination.send(message)

            first = asyncio.create_task(relay(client, upstream))
            second = asyncio.create_task(relay(upstream, client))
            done, pending = await asyncio.wait({first, second}, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            await asyncio.gather(*done, *pending, return_exceptions=True)

    def _run(self) -> None:
        try:
            import websockets

            async def serve_forever():
                self._server = await websockets.serve(
                    self._handler,
                    self.host,
                    self.port,
                    max_size=None,
                )
                self._ready.set()
                await self._server.wait_closed()

            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(serve_forever())
        except BaseException as exc:  # surfaced synchronously by start()
            self._error = exc
            self._ready.set()
        finally:
            if self._loop:
                self._loop.close()

    def start(self, timeout: float = 5.0) -> None:
        self._thread = threading.Thread(target=self._run, name="trinity-voice-proxy", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout):
            raise TimeoutError("Voice-WebSocket-Proxy wurde nicht rechtzeitig bereit.")
        if self._error:
            raise RuntimeError(f"Voice-WebSocket-Proxy konnte nicht starten: {self._error}")

    def stop(self) -> None:
        if self._loop and self._server:
            self._loop.call_soon_threadsafe(self._server.close)
        if self._thread:
            self._thread.join(timeout=5)
        self._thread = None
        self._server = None
