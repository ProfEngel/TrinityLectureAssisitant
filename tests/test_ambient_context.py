import json
import threading
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from urllib.parse import quote
from urllib.request import Request, urlopen

from ambient_context import AmbientContextService
from trinity_bridge import TrinityBridge, make_handler


def test_ambient_context_uses_latest_rss_item_and_fallback_weather():
    rss = b"""<rss><channel>
      <item><title>Alt</title><pubDate>Fri, 31 Jul 2026 10:00:00 +0000</pubDate></item>
      <item><title>Neueste Meldung</title><pubDate>Fri, 31 Jul 2026 12:00:00 +0000</pubDate></item>
    </channel></rss>"""

    def fetch(url):
        if "n-tv.de" in url:
            return rss
        if "geocoding" in url:
            return json.dumps({"results": [{"latitude": 48.68, "longitude": 9.22, "name": "Filderstadt"}]}).encode()
        return json.dumps({"hourly": {"temperature_2m": [20.1, 21.6], "weather_code": [1, 3]}}).encode()

    now = datetime(2026, 7, 31, 13, tzinfo=timezone.utc).timestamp()
    result = AmbientContextService(fetch=fetch, clock=lambda: now).snapshot("Filderstadt")

    assert result["headline"]["title"] == "Neueste Meldung"
    assert result["weather"] == {
        "place": "Filderstadt", "temperature": 22, "code": 3, "symbol": "CLOUD", "source": "fallback"
    }


def test_ambient_context_prefers_fresh_device_location_and_calendar_without_persisting_it():
    calls = []

    def fetch(url):
        calls.append(url)
        if "n-tv.de" in url:
            return b"<rss><channel><item><title>Headline</title></item></channel></rss>"
        return json.dumps({"hourly": {"temperature_2m": [17, 18], "weather_code": [0, 1]}}).encode()

    now = 1_800_000_000.0
    service = AmbientContextService(fetch=fetch, clock=lambda: now)
    service.report_device(
        {
            "latitude": 52.52,
            "longitude": 13.405,
            "calendar_title": "Vorlesung Wirtschaftsinformatik",
            "calendar_start": now + 3600,
        }
    )
    result = service.snapshot("Filderstadt")

    assert result["weather"]["source"] == "device"
    assert result["weather"]["temperature"] == 18
    assert result["calendar"]["title"] == "Vorlesung Wirtschaftsinformatik"
    assert not any("geocoding" in url for url in calls)


def test_ambient_context_returns_partial_data_when_public_services_fail():
    def fetch(_url):
        raise OSError("offline")

    result = AmbientContextService(fetch=fetch).snapshot("Filderstadt")

    assert result["ok"] is True
    assert result["headline"] == {}
    assert result["weather"] == {}


def test_ambient_http_endpoints_accept_authenticated_device_context(tmp_path):
    (tmp_path / "core").mkdir()
    (tmp_path / "memory").mkdir()
    bridge = TrinityBridge(tmp_path, token="secret")

    class FakeAmbient:
        def __init__(self):
            self.device = None

        def report_device(self, payload):
            self.device = payload
            return {"ok": True}

        def snapshot(self, fallback_place):
            return {"ok": True, "place": fallback_place, "device": self.device}

    bridge.ambient = FakeAmbient()
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(bridge))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = f"http://127.0.0.1:{server.server_port}"
        report = Request(
            f"{base_url}/ambient/device",
            data=json.dumps({"latitude": 48.68, "longitude": 9.22}).encode("utf-8"),
            headers={"Authorization": "Bearer secret", "Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(report, timeout=3) as response:
            assert json.load(response)["ok"] is True

        snapshot = Request(
            f"{base_url}/ambient?place={quote('Filderstadt Plattenhardt')}",
            headers={"Authorization": "Bearer secret"},
        )
        with urlopen(snapshot, timeout=3) as response:
            payload = json.load(response)
        assert payload["place"] == "Filderstadt Plattenhardt"
        assert payload["device"] == {"latitude": 48.68, "longitude": 9.22}
    finally:
        server.shutdown()
        server.server_close()
