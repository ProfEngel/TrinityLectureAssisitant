"""Token-protected WebSocket proxy for the upstream realtime endpoint."""

from __future__ import annotations

import asyncio
import hmac
import json
import threading
from collections.abc import Iterable
from pathlib import Path
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

    def __init__(
        self,
        host: str,
        port: int,
        upstream_port: int,
        tokens: str | Iterable[str],
        speaker_config_path: str | Path | None = None,
    ):
        self.host = host
        self.port = int(port)
        self.upstream_port = int(upstream_port)
        raw_tokens = [tokens] if isinstance(tokens, str) else list(tokens)
        self.tokens = tuple(dict.fromkeys(token for token in raw_tokens if token))
        self.speaker_config_path = Path(speaker_config_path) if speaker_config_path else None
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._server = None
        self._ready = threading.Event()
        self._error: BaseException | None = None

    def _speaker_target(self) -> dict | None:
        if not self.speaker_config_path:
            return None
        try:
            config = json.loads(self.speaker_config_path.read_text(encoding="utf-8"))
            target = config.get("system", {}).get("speech_output")
            return target if isinstance(target, dict) else None
        except (OSError, ValueError, TypeError):
            # Never tear down a live call for a transient config write.
            return None

    @staticmethod
    def _selected_for_client(target: dict | None, device_id: str, client_ip: str) -> bool:
        if target is None:
            return True
        if target.get("kind") == "none":
            return False
        selected_id = str(target.get("device_id") or "")
        selected_ip = str(target.get("client_ip") or "")
        if device_id:
            return hmac.compare_digest(device_id, selected_id)
        # Older Companion builds send no device ID yet. The Bridge records the
        # Tailscale peer that explicitly claimed "Antwortet hier".
        return bool(selected_ip and client_ip == selected_ip)

    async def _watch_speaker(self, client, device_id: str, client_ip: str) -> None:
        while True:
            await asyncio.sleep(0.25)
            if not self._selected_for_client(self._speaker_target(), device_id, client_ip):
                await client.close(code=4409, reason="Voice moved to another device")
                return

    async def _handler(self, client) -> None:
        request = getattr(client, "request", None)
        path = getattr(request, "path", "/")
        headers = getattr(request, "headers", {})
        supplied_token = _token_from_request(path, headers)
        if self.tokens and not any(hmac.compare_digest(supplied_token, token) for token in self.tokens):
            await client.close(code=4401, reason="Unauthorized")
            return

        query = parse_qs(urlsplit(path).query)
        device_id = str((query.get("device_id") or [""])[0])[:160]
        client_ip = str(client.remote_address[0]) if client.remote_address else ""
        if not self._selected_for_client(self._speaker_target(), device_id, client_ip):
            await client.close(code=4403, reason="Select this device for voice first")
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
            watcher = asyncio.create_task(self._watch_speaker(client, device_id, client_ip))
            done, pending = await asyncio.wait(
                {first, second, watcher}, return_when=asyncio.FIRST_COMPLETED
            )
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
