"""FastAPI app: JSON API + the Pocket Mode web UI.

Design rules for this file:

* **One endpoint for the product.** ``GET /api/brief`` returns a single
  ``BriefResponse`` -- plan, briefing, and pocket payload together -- because the
  UI has two screens and the client should not have to stitch three requests
  into one coherent answer.
* **The UI is static files.** No CDN, no bundler, no build step. ``static/`` is
  committed as-is so a judge can read the whole front end in one sitting.
* **Nothing here hides a failure.** ``degraded``, ``scorer_note``,
  ``weather_source`` and ``air_source`` all reach the client, and the UI shows
  them. If Baahar is replaying a fixture, the user sees that.

Note on latency: with ``model=auto`` and a Gemma key present, ``/api/brief``
takes tens of seconds (measured; see ``eval/RESULTS.md``). The UI shows a live
elapsed counter and offers a one-tap switch to the local template writer, so a
slow open model degrades into a usable product instead of a spinner.
"""

from __future__ import annotations

import ipaddress
import logging
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import brief as brief_mod
from . import forecast as forecast_mod
from . import parks as parks_mod
from . import pocket as pocket_mod
from . import score as score_mod
from .config import STATIC_DIR, get_settings
from .http_client import UpstreamError
from .models import BriefResponse
from .naqi import band_table, pollutant_table

log = logging.getLogger(__name__)

app = FastAPI(
    title="Baahar",
    description="Find Bengaluru's next safe outdoor hour, then put the phone away.",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)


@app.get("/api/health")
def health() -> dict[str, object]:
    """Liveness plus a presence-only view of configuration."""
    settings = get_settings()
    return {
        "status": "ok",
        "version": app.version,
        "city": settings.city,
        "keys_present": settings.which_keys(),
        "offline": settings.offline,
    }


@app.get("/api/brief", response_model=BriefResponse)
def api_brief(
    lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    lon: Annotated[float | None, Query(ge=-180, le=180)] = None,
    city: str | None = None,
    hours: Annotated[int | None, Query(ge=1, le=48)] = None,
    model: Annotated[str, Query(pattern="^(auto|gemma|tinker|template)$")] = "auto",
    scorer: Annotated[str, Query(pattern="^(auto|heuristic|tabpfn|lgbm|ensemble)$")] = "auto",
    walk_minutes: Annotated[int | None, Query(ge=5, le=180)] = None,
    park: str | None = None,
    voice: bool = False,
    offline: bool = False,
) -> BriefResponse:
    """The whole product in one payload."""
    settings = get_settings()
    target_lat = lat if lat is not None else settings.lat
    target_lon = lon if lon is not None else settings.lon

    try:
        slots, wsrc, asrc = forecast_mod.fetch_joined(
            lat=target_lat, lon=target_lon, hours=hours, offline=offline or None
        )
    except UpstreamError as exc:
        # A real error, surfaced as one. Never an empty 200 that reads as "fine".
        log.warning("/api/brief could not load a forecast: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=(f"Could not reach Open-Meteo and no recorded fixture is available. ({exc})"),
        ) from exc

    chosen = parks_mod.park_by_id(park) if park else None
    if park and chosen is None:
        raise HTTPException(status_code=404, detail=f"unknown park id {park!r}")
    if chosen is None:
        chosen = parks_mod.pick_park(lat=target_lat, lon=target_lon)

    plan = score_mod.build_plan(
        slots,
        city=city or settings.city,
        scorer=scorer,
        park=chosen,
        weather_source=wsrc,
        air_source=asrc,
        generated_at=datetime.now().astimezone(),
    )
    pocket = pocket_mod.build_pocket(
        plan, walk_minutes=pocket_mod.ensure_walk_minutes(walk_minutes)
    )
    briefing = brief_mod.generate(
        plan,
        writer=model,
        park=chosen,
        voice=voice,
        notice_this=pocket_mod.briefing_cue(plan),
    )

    return BriefResponse(
        plan=plan,
        briefing=briefing,
        pocket=pocket,
        meta={
            "elapsed_ms": briefing.latency_ms,
            "scorer": plan.scorer,
            "writer": briefing.writer,
            "cues_remaining": pocket_mod.alternate_cues(plan),
            "cue_tags": [c.tag for c in pocket_mod.cue_pool(plan)],
            # Per-cue provenance. The record count differs per species, so this is
            # a mapping rather than one shared sentence.
            "cue_evidence": pocket_mod.cue_evidence(plan),
            "walk_timer_seconds": pocket_mod.walk_timer_seconds(pocket.walk_minutes),
        },
    )


@app.get("/api/score")
def api_score(
    lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    lon: Annotated[float | None, Query(ge=-180, le=180)] = None,
    hours: Annotated[int | None, Query(ge=1, le=48)] = None,
    scorer: Annotated[str, Query(pattern="^(auto|heuristic|tabpfn|lgbm|ensemble)$")] = "auto",
) -> dict[str, object]:
    """Scores only, no briefing. Used by the CLI-equivalent path and by tests."""
    settings = get_settings()
    slots, wsrc, asrc = forecast_mod.fetch_joined(
        lat=lat if lat is not None else settings.lat,
        lon=lon if lon is not None else settings.lon,
        hours=hours,
        offline=None,
    )
    plan = score_mod.build_plan(slots, scorer=scorer, weather_source=wsrc, air_source=asrc)
    return plan.model_dump(mode="json")


@app.get("/api/parks")
def api_parks(
    lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    lon: Annotated[float | None, Query(ge=-180, le=180)] = None,
) -> dict[str, object]:
    settings = get_settings()
    target_lat = lat if lat is not None else settings.lat
    target_lon = lon if lon is not None else settings.lon
    return {
        "city": settings.city,
        "parks": [
            {
                **p.model_dump(mode="json"),
                "distance_km": round(parks_mod.distance_to(target_lat, target_lon, p), 2),
            }
            for p in parks_mod.nearest_parks(
                target_lat, target_lon, limit=len(parks_mod.load_parks())
            )
        ],
    }


@app.get("/api/naqi-scale")
def api_naqi_scale() -> dict[str, object]:
    """The NAQI bands and breakpoints, as data.

    Exposed so the UI legend and this documentation cannot drift apart, and so a
    curious user can audit exactly how Baahar turns a PM2.5 number into an index.
    """
    return {"bands": band_table(), "pollutants": pollutant_table()}


def _is_loopback(host: str | None) -> bool:
    """Whether a peer address is this machine.

    Used to keep ``/api/cache/clear`` a local dev tool. ``X-Forwarded-For`` is
    deliberately ignored: a header the caller sets is not evidence of anything,
    and honouring it would make the check trivially bypassable by anyone who
    read this file. Behind a proxy the peer address is the proxy's, so the
    endpoint simply stays refused in a deploy -- which is the correct answer.
    """
    if not host:
        return False
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@app.post("/api/cache/clear")
def api_cache_clear(request: Request) -> JSONResponse:
    """Wipe cached briefings. Local dev tool, loopback callers only.

    An earlier version was open to anyone. Combined with ``/api/brief?model=gemma
    &voice=1`` that is a quota-burn loop: every request misses the cache, spends a
    ~45 s Gemini call and an ElevenLabs call on the maintainer's keys, and
    renders nothing for a caller who cannot read the JSON anyway. No rate limit
    or auth middleware exists anywhere in this app, so the cheap correct fix is
    to refuse the one endpoint that is destructive and non-essential.
    """
    if not _is_loopback(request.client.host if request.client else None):
        log.warning("refused /api/cache/clear from non-loopback host")
        raise HTTPException(
            status_code=403,
            detail=(
                "cache clear is a local dev tool and is only served to loopback "
                "callers. Run `uv run baahar serve` and use http://127.0.0.1:8000."
            ),
        )
    removed = brief_mod.clear_cache()
    return JSONResponse({"removed": removed})


def _audio_file(name: str) -> Path | None:
    """Resolve a requested clip name to a real file inside the audio cache.

    Returns ``None`` for anything that escapes the cache or is not a file. The
    containment check is the whole point: resolving first and comparing against
    the resolved root closes ``..`` traversal, absolute paths, and symlinks
    pointing outside the directory in one comparison.

    Starlette will not route an unescaped ``/`` into a single ``{name}``
    segment, so the router happens to block the obvious attempts on Linux. That
    is not a control -- a percent-encoded separator arrives decoded, and on
    Windows a backslash is a separator everywhere -- so the check lives here and
    does not depend on how the request was spelled.
    """
    root = brief_mod.audio_dir().resolve()
    target = (root / name).resolve()
    if not target.is_relative_to(root):
        log.warning("refused audio path outside the cache: %r", name)
        return None
    return target if target.is_file() else None


@app.get(brief_mod.AUDIO_ROUTE + "/{name}")
def api_audio(name: str) -> FileResponse:
    """Serve one cached briefing clip.

    Replaces handing out a ``file://`` URI, which published the build layout and
    the maintainer's Windows username in the public JSON.
    """
    target = _audio_file(name)
    if target is None:
        raise HTTPException(status_code=404, detail="no such audio clip")
    return FileResponse(target, media_type="audio/mpeg")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
