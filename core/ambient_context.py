"""Short, cached glance information for low-distraction companion displays."""

from __future__ import annotations

import json
import threading
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen


NTV_RSS_URL = "https://www.n-tv.de/rss"
OPEN_METEO_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


class AmbientContextService:
    """Combine public glance data with ephemeral device context.

    Device coordinates and calendar titles deliberately remain in memory. The
    server only caches public news/weather responses and never writes this
    context into Trinity's synchronized vault.
    """

    def __init__(self, fetch=None, clock=None):
        self._fetch = fetch or self._fetch_url
        self._clock = clock or time.time
        self._lock = threading.Lock()
        self._cache = {}
        self._device = {}

    def report_device(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("Geraetekontext muss ein Objekt sein.")
        now = self._clock()
        latitude = _coordinate(payload.get("latitude"), -90, 90)
        longitude = _coordinate(payload.get("longitude"), -180, 180)
        calendar_title = _clean(payload.get("calendar_title"), 40)
        try:
            calendar_start = float(payload.get("calendar_start") or 0)
        except (TypeError, ValueError):
            calendar_start = 0.0
        with self._lock:
            self._device = {
                "latitude": latitude,
                "longitude": longitude,
                "calendar_title": calendar_title,
                "calendar_start": calendar_start,
                "updated_at": now,
            }
        return {"ok": True, "updated_at": now}

    def snapshot(self, fallback_place="Filderstadt"):
        place = _clean(fallback_place, 80) or "Filderstadt"
        now = self._clock()
        with self._lock:
            device = dict(self._device)

        coordinate = None
        location_source = "fallback"
        if (
            device.get("latitude") is not None
            and device.get("longitude") is not None
            and now - float(device.get("updated_at") or 0) <= 2 * 60 * 60
        ):
            coordinate = (device["latitude"], device["longitude"])
            location_source = "device"

        with ThreadPoolExecutor(max_workers=2) as pool:
            news_future = pool.submit(self._cached, "ntv", 300, self._latest_ntv)
            if coordinate:
                weather_key = f"weather:{coordinate[0]:.3f}:{coordinate[1]:.3f}"
                weather_future = pool.submit(
                    self._cached,
                    weather_key,
                    600,
                    lambda: self._weather_at(*coordinate, place="Aktueller Standort"),
                )
            else:
                weather_future = pool.submit(
                    self._cached,
                    f"weather-place:{place.casefold()}",
                    600,
                    lambda: self._weather_for_place(place),
                )
            try:
                headline = news_future.result()
            except Exception:
                headline = {}
            try:
                weather = weather_future.result()
            except Exception:
                weather = {}

        calendar = {}
        start = float(device.get("calendar_start") or 0)
        title = str(device.get("calendar_title") or "")
        if title and now - 300 <= start <= now + 24 * 60 * 60:
            calendar = {"title": title, "start": start}

        return {
            "ok": True,
            "headline": headline,
            "weather": {**weather, "source": location_source} if weather else {},
            "calendar": calendar,
            "updated_at": now,
        }

    def _cached(self, key, ttl, loader):
        now = self._clock()
        with self._lock:
            cached = self._cache.get(key)
            if cached and cached[0] > now:
                return dict(cached[1])
        value = loader()
        with self._lock:
            self._cache[key] = (now + ttl, dict(value))
        return value

    def _latest_ntv(self):
        root = ET.fromstring(self._fetch(NTV_RSS_URL))
        candidates = []
        for item in root.findall("./channel/item"):
            title = _clean(item.findtext("title"), 220)
            if not title:
                continue
            published = item.findtext("pubDate") or ""
            try:
                timestamp = parsedate_to_datetime(published).timestamp()
            except (TypeError, ValueError, OverflowError):
                timestamp = 0.0
            candidates.append((timestamp, title))
        if not candidates:
            return {}
        published_at, title = max(candidates, key=lambda item: item[0])
        return {"source": "n-tv", "title": title, "published_at": published_at}

    def _weather_for_place(self, place):
        query = urlencode({"name": place, "count": 1, "language": "de", "format": "json"})
        payload = json.loads(self._fetch(f"{OPEN_METEO_GEOCODING_URL}?{query}"))
        results = payload.get("results") or []
        if not results:
            return {}
        result = results[0]
        return self._weather_at(
            float(result["latitude"]),
            float(result["longitude"]),
            place=_clean(result.get("name"), 40) or place,
        )

    def _weather_at(self, latitude, longitude, place):
        query = urlencode(
            {
                "latitude": latitude,
                "longitude": longitude,
                "hourly": "temperature_2m,weather_code",
                "forecast_hours": 2,
                "timezone": "auto",
            }
        )
        payload = json.loads(self._fetch(f"{OPEN_METEO_FORECAST_URL}?{query}"))
        hourly = payload.get("hourly") or {}
        temperatures = hourly.get("temperature_2m") or []
        codes = hourly.get("weather_code") or []
        if not temperatures:
            return {}
        index = 1 if len(temperatures) > 1 else 0
        code = int(codes[index] if index < len(codes) else 0)
        return {
            "place": place,
            "temperature": round(float(temperatures[index])),
            "code": code,
            "symbol": _weather_symbol(code),
        }

    @staticmethod
    def _fetch_url(url):
        request = Request(url, headers={"User-Agent": "Trinity-Assistant/0.17"})
        with urlopen(request, timeout=3.5) as response:
            return response.read()


def _coordinate(value, minimum, maximum):
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Ungueltige Standortkoordinate.") from exc
    if not minimum <= number <= maximum:
        raise ValueError("Standortkoordinate ausserhalb des gueltigen Bereichs.")
    return number


def _clean(value, limit):
    return " ".join(str(value or "").split())[:limit]


def _weather_symbol(code):
    if code == 0:
        return "SUN"
    if code in {1, 2}:
        return "PART"
    if code == 3:
        return "CLOUD"
    if code in {45, 48}:
        return "FOG"
    if code in {51, 53, 55, 56, 57}:
        return "DRIZ"
    if code in {61, 63, 65, 66, 67, 80, 81, 82}:
        return "RAIN"
    if code in {71, 73, 75, 77, 85, 86}:
        return "SNOW"
    if code in {95, 96, 99}:
        return "STORM"
    return "WX"
