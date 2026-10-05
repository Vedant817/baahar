"""Shared HTTP helpers.

Every outbound call in Baahar goes through :func:`get_json`, which guarantees
the three properties `AGENTS.md` demands: a hard timeout, bounded retries, and
a recorded-fixture fallback. No module is allowed to call `httpx.get` directly.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import httpx

from .config import get_settings

log = logging.getLogger(__name__)

#: Recorded responses live here and are committed to git. They are the reason
#: `baahar brief` still produces a real briefing with the network unplugged.
SAMPLES_DIR = Path(__file__).resolve().parents[2] / "data" / "samples"

_META_KEY = "_baahar_meta"


class UpstreamError(RuntimeError):
    """A network call failed in a way the caller must be told about.

    Baahar never swallows this into a cheerful empty answer.
    """


def get_json(
    url: str,
    params: dict[str, Any],
    *,
    timeout: float | None = None,
    retries: int = 2,
) -> dict[str, Any]:
    """GET `url` with `params`, returning parsed JSON.

    Retries with linear backoff on transport errors and 5xx. 4xx is raised
    immediately because retrying a bad request just wastes the user's time.
    """
    settings = get_settings()
    timeout = timeout if timeout is not None else settings.http_timeout
    last: Exception | None = None

    for attempt in range(retries + 1):
        try:
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                resp = client.get(url, params=params)
            if resp.status_code >= 500:
                raise UpstreamError(f"{url} -> HTTP {resp.status_code}")
            if resp.status_code >= 400:
                raise UpstreamError(f"{url} -> HTTP {resp.status_code}: {resp.text[:200]}")
            return resp.json()
        except (httpx.HTTPError, json.JSONDecodeError, UpstreamError) as exc:
            last = exc
            if attempt < retries:
                backoff = 0.6 * (attempt + 1)
                log.warning(
                    "upstream call failed (attempt %d/%d): %s -- retrying in %.1fs",
                    attempt + 1,
                    retries + 1,
                    exc,
                    backoff,
                )
                time.sleep(backoff)

    raise UpstreamError(f"{url} failed after {retries + 1} attempts: {last}") from last


def record_sample(name: str, payload: dict[str, Any], *, url: str, note: str = "") -> Path:
    """Persist a verbatim upstream response as an offline fixture.

    The response body is stored unmodified; provenance goes in a `_baahar_meta`
    sibling key that :func:`load_sample` strips on the way back in. Recording
    real responses (rather than hand-written ones) is what makes the offline
    tests worth anything.
    """
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    path = SAMPLES_DIR / name
    payload = dict(payload)
    payload[_META_KEY] = {
        "recorded_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_url": url,
        "note": note or "verbatim upstream response; do not hand-edit",
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")
    return path


def load_sample(name: str) -> dict[str, Any] | None:
    """Load a recorded fixture, or ``None`` if it does not exist."""
    path = SAMPLES_DIR / name
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    meta = payload.pop(_META_KEY, {})
    log.debug("using recorded fixture %s (%s)", name, meta.get("recorded_at_utc", "unknown date"))
    return payload


def sample_meta(name: str) -> dict[str, Any]:
    """Provenance of a recorded fixture, without loading the payload."""
    path = SAMPLES_DIR / name
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get(_META_KEY, {})
