#!/usr/bin/env python3
"""Generate one presentation image through Kie.ai or fal.ai without logging keys."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path


KIE_CREATE_URL = "https://api.kie.ai/api/v1/jobs/createTask"
KIE_STATUS_URL = "https://api.kie.ai/api/v1/jobs/recordInfo"
FAL_BASE_URL = "https://fal.run"


class PresentationImageError(RuntimeError):
    """A provider request failed or returned an unusable result."""


def _request_json(url, *, method="GET", headers=None, payload=None, timeout=120):
    data = None
    request_headers = dict(headers or {})
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(
        url, data=data, headers=request_headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except Exception as exc:  # pylint: disable=broad-except
        raise PresentationImageError(f"Provider-Anfrage fehlgeschlagen: {exc}") from exc
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PresentationImageError("Provider lieferte kein gültiges JSON.") from exc


def _find_http_urls(value):
    urls = []
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith(("http://", "https://")):
            urls.append(stripped)
        elif stripped.startswith(("{", "[")):
            try:
                urls.extend(_find_http_urls(json.loads(stripped)))
            except json.JSONDecodeError:
                pass
    elif isinstance(value, list):
        for item in value:
            urls.extend(_find_http_urls(item))
    elif isinstance(value, dict):
        preferred = (
            "resultUrls",
            "result_urls",
            "images",
            "image",
            "url",
            "resultJson",
            "result_json",
            "result",
        )
        for key in preferred:
            if key in value:
                urls.extend(_find_http_urls(value[key]))
        for key, item in value.items():
            if key not in preferred:
                urls.extend(_find_http_urls(item))
    return list(dict.fromkeys(urls))


def _kie_image_url(
    *, api_key, model, prompt, aspect_ratio, resolution, timeout_seconds
):
    created = _request_json(
        KIE_CREATE_URL,
        method="POST",
        headers={"Authorization": f"Bearer {api_key}"},
        payload={
            "model": model,
            "input": {
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "resolution": resolution,
                "output_format": "png",
                "image_input": [],
            },
        },
    )
    task_id = str((created.get("data") or {}).get("taskId") or "").strip()
    if not task_id:
        raise PresentationImageError(
            "Kie.ai hat keine Task-ID geliefert: "
            + str(created.get("msg") or created.get("message") or "unbekannter Fehler")
        )
    deadline = time.monotonic() + timeout_seconds
    delay = 2.0
    while time.monotonic() < deadline:
        status = _request_json(
            KIE_STATUS_URL + "?" + urllib.parse.urlencode({"taskId": task_id}),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60,
        )
        data = status.get("data") or {}
        state = str(
            data.get("state")
            or data.get("status")
            or status.get("state")
            or status.get("status")
            or ""
        ).strip().casefold()
        if state in {"success", "succeeded", "completed", "complete"}:
            urls = _find_http_urls(data)
            if not urls:
                raise PresentationImageError(
                    "Kie.ai meldet Erfolg, aber keine Bildadresse."
                )
            return urls[0]
        if state in {"fail", "failed", "error", "cancelled", "canceled"}:
            raise PresentationImageError(
                "Kie.ai-Auftrag fehlgeschlagen: "
                + str(data.get("failMsg") or data.get("error") or status.get("msg") or state)
            )
        time.sleep(delay)
        delay = min(delay * 1.4, 10.0)
    raise PresentationImageError("Kie.ai-Auftrag hat das Zeitlimit überschritten.")


def _fal_image_url(*, api_key, model, prompt, aspect_ratio, resolution):
    result = _request_json(
        f"{FAL_BASE_URL}/{model.lstrip('/')}",
        method="POST",
        headers={"Authorization": f"Key {api_key}"},
        payload={
            "prompt": prompt,
            "num_images": 1,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
            "output_format": "png",
            "sync_mode": False,
        },
        timeout=300,
    )
    urls = _find_http_urls(result.get("images") or result)
    if not urls:
        raise PresentationImageError("fal.ai hat keine Bildadresse geliefert.")
    return urls[0]


def _download(url, output_path):
    request = urllib.request.Request(url, headers={"User-Agent": "Trinity/Presentation"})
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            data = response.read()
    except Exception as exc:  # pylint: disable=broad-except
        raise PresentationImageError(f"Bilddownload fehlgeschlagen: {exc}") from exc
    if not data:
        raise PresentationImageError("Der Bilddownload war leer.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".part")
    temporary.write_bytes(data)
    temporary.replace(output_path)
    return len(data)


def generate(args):
    prompt_path = Path(args.prompt_file).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    try:
        prompt = prompt_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise PresentationImageError(f"Promptdatei konnte nicht gelesen werden: {exc}") from exc
    if not prompt:
        raise PresentationImageError("Die Promptdatei ist leer.")
    if len(prompt.encode("utf-8")) > 100_000:
        raise PresentationImageError("Der Bildprompt ist ungewöhnlich groß.")

    provider = str(args.provider).strip().casefold()
    if provider == "kie":
        api_key = os.environ.get("KIE_API_KEY", "").strip()
        if not api_key:
            raise PresentationImageError("KIE_API_KEY ist nicht eingerichtet.")
        image_url = _kie_image_url(
            api_key=api_key,
            model=args.model,
            prompt=prompt,
            aspect_ratio=args.aspect_ratio,
            resolution=args.resolution,
            timeout_seconds=args.timeout,
        )
    elif provider == "fal":
        api_key = os.environ.get("FAL_KEY", "").strip()
        if not api_key:
            raise PresentationImageError("FAL_KEY ist nicht eingerichtet.")
        image_url = _fal_image_url(
            api_key=api_key,
            model=args.model,
            prompt=prompt,
            aspect_ratio=args.aspect_ratio,
            resolution=args.resolution,
        )
    else:
        raise PresentationImageError("Provider muss kie oder fal sein.")

    byte_count = _download(image_url, output_path)
    return {
        "ok": True,
        "provider": provider,
        "model": args.model,
        "output": str(output_path),
        "bytes": byte_count,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Sichere Bildbrücke für Trinitys HTML-Präsentationswerkstatt."
    )
    parser.add_argument("--provider", choices=("kie", "fal"), required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--prompt-file", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--aspect-ratio", default="16:9")
    parser.add_argument("--resolution", choices=("1K", "2K", "4K"), default="2K")
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    try:
        print(json.dumps(generate(args), ensure_ascii=False))
        return 0
    except PresentationImageError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
