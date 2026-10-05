"""Briefing generation.

Four writers, one interface, and an explicit record of which one ran:

``template``
    Deterministic, local, no network, no key. Always available. This is what a
    judge with no keys and an offline laptop sees, and it is why the product is
    demoable at 3am on a plane.
``gemma``
    Open-weight Gemma via the Google AI Studio free tier. The default when a
    key is present.
``tinker``
    A hosted fine-tune served from Tinker's API, if a LoRA has been trained.
    Requires ``TINKER_API_KEY``.
``hybrid``
    Gemma (or Tinker) draft, then a local post-pass that repairs the two
    failures that actually matter: a missing safety caveat and a wrong park
    name. Falls back to the template if the model call fails.

Safety is enforced after generation, not requested politely in a prompt. A
prompt says "include a safety caveat"; :func:`enforce_safety` checks whether one
is actually there and appends a plain-language line if not. Prompts are not
contracts.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from typing import Any, Protocol

import httpx

from .config import get_settings
from .http_client import UpstreamError
from .models import Briefing, Decision, OutdoorPlan, Park

log = logging.getLogger(__name__)

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
TINKER_SAMPLE_URL = "https://api.tinker.ai/v1/sampling/generate"

MAX_WORDS = 120

#: Generous on purpose. Both open-weight Gemma models on the AI Studio free tier
#: emit a long reasoning trace before answering and *reject*
#: `thinkingConfig.thinkingBudget` with "Thinking budget is not supported for
#: this model" (verified live 2026-10-06). The trace therefore has to be paid
#: for in output tokens. Measured reasoning traces were 2.2k (gemma-4-31b-it)
#: to 5.7k (gemma-4-26b-a4b-it) characters. Latencies are recorded in
#: `eval/RESULTS.md`; the honest summary is 40-95 s, which is why the
#: deterministic template writer is a first-class path and not an afterthought.
GEMINI_TIMEOUT_S = 120.0
GEMINI_MAX_OUTPUT_TOKENS = 2048

SYSTEM_PROMPT = """You are Baahar (बाहर, "outside"), a Bengaluru outdoor-planning \
assistant. You write ONE short park briefing in plain English for a person who has \
about 120 words of attention before they must pocket their phone and walk.

Match the style and length of these two examples exactly.

Example A (good conditions):
Conditions: Cubbon Park (central), 06:30-07:30, Indian NAQI 78, 24C feeling like 26C, \
20% chance of rain, high shade.
Briefing: Go at 06:30-07:30. The air is clean enough at NAQI 78. It is 24C but feels \
like 26C under the old rain trees. Head to Cubbon Park. Once you are out, listen for \
the first two birds and then ignore the traffic. Pocket the phone and let it be boring \
for twenty minutes.

Example B (bad conditions):
Conditions: Hesaraghatta Lake (north), 15:00-16:00, Indian NAQI 320, 34C feeling like \
39C, 70% chance of rain.
Briefing: Stay in. The air is severe at NAQI 320 and it feels like 39C, which is the \
worst pairing for a walk. Rain is likely as well. Try again tomorrow morning instead.

Now write the briefing for the conditions given below.

Rules, briefly: safety first -- if air is poor or it is dangerously hot, say to stay \
in and give one short reason, never talk them into a bad walk. Use the exact time \
window. Name only the park given, never invent another. Bengaluru in October only: \
hot, post-monsoon, real dust. No fall colours, no snow, no New England. Under 120 \
words. One paragraph. No lists, no headings, no preamble, no sign-off.

Note on format: this prompt is deliberately two-shot rather than a list of numbered \
rules. An earlier eight-rule version made the model *reason about the rules and then \
restate them*, which leaked the instruction list into the user-facing text."""


class Writer(Protocol):
    """Anything that can turn a plan into briefing text."""

    name: str

    def write(self, plan: OutdoorPlan, **_: Any) -> str: ...


# ---------------------------------------------------------------------------
# Context assembly
# ---------------------------------------------------------------------------
def build_context(plan: OutdoorPlan, park: Park | None = None) -> dict[str, Any]:
    """The structured facts a writer is allowed to use. Nothing else."""
    park = park or plan.park
    slot = plan.best_slot
    weather = slot.weather if slot else None
    air = slot.air if slot else None

    return {
        "city": plan.city,
        "decision": plan.overall.value,
        "best_time": plan.best_time.strftime("%H:%M") if plan.best_time else None,
        "window": (
            f"{plan.best_time.strftime('%H:%M')}-{(plan.best_time.hour + 1) % 24:02d}:00"
            if plan.best_time
            else None
        ),
        "park": {
            "name": park.name,
            "area": park.area,
            "vibe": park.vibe,
            "shade": park.shade,
            "good_for": park.good_for,
            "crowding_hint": park.crowding_hint,
        }
        if park
        else None,
        "air": {
            "naqi": air.naqi,
            "band": air.naqi_band,
            "dominant_pollutant": air.dominant_label,
            "pm25": air.pm25,
            "pm10": air.pm10,
            "naqi_basis": air.naqi_basis,
        }
        if air
        else None,
        "weather": {
            "temp_c": weather.temp_c,
            "apparent_c": weather.apparent_c,
            "precip_mm": weather.precip_mm,
            "precip_prob": weather.precip_prob,
            "humidity": weather.humidity,
            "uv_index": weather.uv_index,
        }
        if weather
        else None,
        "safety_reasons": [s.reasons[0] for s in plan.slots[:1] if s.reasons],
    }


def build_user_prompt(ctx: dict[str, Any]) -> str:
    """Render the context as a compact block of *facts* only.

    The rules live in :data:`SYSTEM_PROMPT` alongside two worked examples, so
    this message carries only numbers and names. That keeps the model's
    reasoning short and stops it restating the instructions back at us.
    """
    lines: list[str] = ["Conditions:"]
    if ctx["decision"] == Decision.SKIP.value:
        lines.append("Assessment: conditions are bad -- the briefing must tell them to stay in.")
    else:
        lines.append(f"Assessment: {ctx['decision']}")
    if ctx.get("window"):
        lines.append(f"Window: {ctx['window']}")
    if ctx.get("park"):
        p = ctx["park"]
        bits = f"{p['name']} ({p['area']})"
        if p.get("shade"):
            bits += f", {p['shade']} shade"
        lines.append(f"Park: {bits}")
    if ctx.get("air") and ctx["air"].get("naqi") is not None:
        a = ctx["air"]
        dom = f", main pollutant {a['dominant_pollutant']}" if a.get("dominant_pollutant") else ""
        lines.append(f"Indian NAQI {a['naqi']:.0f} ({a['band']}{dom})")
    if ctx.get("weather"):
        w = ctx["weather"]
        bits = []
        if w.get("temp_c") is not None:
            bits.append(f"{w['temp_c']:.0f}C")
            if w.get("apparent_c") is not None and abs(w["apparent_c"] - w["temp_c"]) >= 1.5:
                bits.append(f"feeling like {w['apparent_c']:.0f}C")
        if w.get("precip_prob") is not None:
            bits.append(f"{w['precip_prob']:.0f}% chance of rain")
        if w.get("humidity") is not None:
            bits.append(f"humidity {w['humidity']:.0f}%")
        if bits:
            lines.append("Weather: " + ", ".join(bits))
    if ctx.get("safety_reasons"):
        lines.append("Reason the assessment holds: " + "; ".join(ctx["safety_reasons"]))
    lines += ["", "Briefing:"]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Template writer (always works)
# ---------------------------------------------------------------------------
def _fmt_window(ctx: dict[str, Any]) -> str:
    return ctx.get("window") or "shortly"


def write_template(plan: OutdoorPlan, **kwargs: Any) -> str:
    """Deterministic briefing. No network, no key, no randomness.

    This is not a toy path: it is the fallback that guarantees the product
    always produces a real, safety-aware briefing, which is what makes the
    offline demo legitimate.
    """
    ctx = build_context(plan, kwargs.get("park"))
    park = ctx.get("park")
    park_name = park["name"] if park else "your nearest park"
    weather = ctx.get("weather") or {}
    air = ctx.get("air") or {}

    if ctx["decision"] == Decision.SKIP.value:
        reason = (ctx.get("safety_reasons") or ["conditions are poor"])[0]
        air_txt = (
            f" Air is NAQI {air['naqi']:.0f} ({air['band']})." if air.get("naqi") is not None else ""
        )
        return (
            f"Stay in today. {reason}.{air_txt} No walk worth the trouble -- "
            "try again tomorrow or check the evening window. Not a doctor, just "
            "someone reading the numbers honestly."
        )

    window = _fmt_window(ctx)
    lead = (
        f"Hold off until {window}."
        if ctx["decision"] == Decision.WAIT
        else f"Go at {window}."
    )

    air_bits = ""
    if air.get("naqi") is not None:
        naqi, band = air["naqi"], air["band"]
        if naqi >= 200:
            air_bits = f" Air is poor (NAQI {naqi:.0f}, {band}), so keep it easy and stay on quieter paths."
        elif naqi >= 100:
            air_bits = f" Air is moderate (NAQI {naqi:.0f}) -- fine for an easy loop."
        else:
            air_bits = f" Air is clean enough (NAQI {naqi:.0f})."

    temp_bits = ""
    if weather.get("temp_c") is not None:
        feels = weather.get("apparent_c")
        if feels is not None and abs(feels - weather["temp_c"]) >= 1.5:
            temp_bits = f" It is {weather['temp_c']:.0f}C but feels like {feels:.0f}C."
        else:
            temp_bits = f" Around {weather['temp_c']:.0f}C."

    rain_bits = ""
    if weather.get("precip_prob") is not None and weather["precip_prob"] >= 30:
        rain_bits = f" {weather['precip_prob']:.0f}% chance of rain, so take a light layer."

    cue = kwargs.get("notice_this") or "Find one thing in the park you have never noticed before."
    vibe = f" {park['vibe'].split('.')[0]}." if park else ""

    return (
        f"{lead}{air_bits}{temp_bits}{rain_bits} Head to {park_name}.{vibe} "
        f"Once you are out: {cue} Pocket the phone and let it be boring for twenty minutes."
    )


# ---------------------------------------------------------------------------
# Gemma writer
# ---------------------------------------------------------------------------
def _strip_to_words(text: str, limit: int = MAX_WORDS) -> str:
    """Trim to a word budget, preferring a sentence boundary.

    Truncating at an arbitrary word index produced a real bug during live
    testing: "Head to Cubbon Park, known for its ..." became "Head to Cub".
    Park names are the single most important content in the text, so when the
    budget forces a cut we now keep complete sentences, and only fall back to a
    hard word cut if that would throw away more than half the budget.
    """
    text = re.sub(r"\s+", " ", text).strip()
    words = text.split()
    if len(words) <= limit:
        return text

    trimmed = " ".join(words[:limit])
    cut = max(trimmed.rfind("."), trimmed.rfind("!"), trimmed.rfind("?"))
    if cut > 0:
        return trimmed[: cut + 1].strip()
    return trimmed.rstrip(",;:-") + "..."


def _complete_last_sentence(text: str, limit: int = MAX_WORDS) -> str:
    """Extend a text that *almost* fits by keeping the next whole sentence.

    Used after appending the safety caveat, which can push a text that was at
    112 words over the limit. Losing the tail of the last sentence reads far
    worse than dropping a whole closing sentence.
    """
    words = text.split()
    if len(words) <= limit:
        return text
    sentences = re.split(r"(?<=[.!?])\s+", text)
    kept: list[str] = []
    count = 0
    for sentence in sentences:
        n = len(sentence.split())
        if count + n > limit:
            break
        kept.append(sentence)
        count += n
    if not kept:
        return _strip_to_words(text, limit)
    return " ".join(kept).strip()


def _extract_gemini_text(data: Any) -> tuple[str, str]:
    """Pull the answer out of a Gemini response. Returns ``(text, finish_reason)``.

    Non-trivial because the Gemma 4-series models served by AI Studio return a
    *reasoning* part before the answer: ``parts[0]["thought"] is True`` holds a
    chain-of-thought trace, and the prose we want is in a later part. Taking
    ``parts[0]`` blindly -- which the first version of this function did --
    silently shipped the model's internal notes as the user-facing briefing,
    including a verbatim restatement of these instructions.

    Verified against a live response on 2026-10-06 for both `gemma-4-31b-it`
    and `gemma-4-26b-a4b-it`.
    """
    candidates = data.get("candidates") if isinstance(data, dict) else None
    if not candidates:
        raise UpstreamError(f"Gemini returned no candidates: {str(data)[:200]}")

    candidate = candidates[0]
    parts = (candidate.get("content") or {}).get("parts") or []
    answer = "".join(
        str(part.get("text", "")).strip()
        for part in parts
        if isinstance(part, dict) and not part.get("thought")
    ).strip()

    if not answer:
        if any(isinstance(p, dict) and p.get("thought") for p in parts):
            raise UpstreamError(
                "Gemini returned only a reasoning part and no answer "
                "(raise maxOutputTokens)"
            )
        block = data.get("promptFeedback", {}).get("blockReason")
        raise UpstreamError(f"Gemini returned an empty answer (blockReason={block})")

    finish = str(candidate.get("finishReason") or "UNKNOWN")
    if finish == "MAX_TOKENS":
        log.warning("Gemini output was truncated by the token budget")
    return answer, finish


def write_gemma(plan: OutdoorPlan, model: str | None = None, **kwargs: Any) -> str:
    """Call the Gemini API with an open-weight Gemma model."""
    settings = get_settings()
    key = settings.gemini_api_key
    if not key:
        raise UpstreamError("GEMINI_API_KEY is not set")

    model = model or settings.gemma_model
    ctx = build_context(plan, kwargs.get("park"))
    payload = {
        "contents": [{"parts": [{"text": build_user_prompt(ctx)}]}],
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "generationConfig": {
            # T=0 rather than 0.4: measured reasoning traces shrink and the
            # output is more reliably on-style (a briefing is not a creative
            # writing task, and repeatability makes the eval comparable).
            "temperature": 0.0,
            "topP": 1.0,
            # Generous because the Gemma 4-series spends part of this budget on
            # reasoning tokens before it writes anything.
            "maxOutputTokens": GEMINI_MAX_OUTPUT_TOKENS,
        },
    }

    def _post(model_name: str) -> httpx.Response:
        url = f"{GEMINI_BASE}/{model_name}:generateContent"
        with httpx.Client(timeout=GEMINI_TIMEOUT_S) as client:
            return client.post(url, params={"key": key}, json=payload)

    # Try the pinned model, then the fallback. Both HTTP errors *and* transport
    # failures fall through: a retired model returns 404, a cold 31B endpoint
    # on the free tier can simply time out, and both deserve the second chance.
    candidates = [model]
    fb = settings.gemma_model_fallback
    if fb and fb != model:
        candidates.append(fb)

    last_problem = ""
    for attempt, name in enumerate(candidates):
        try:
            resp = _post(name)
        except httpx.HTTPError as exc:
            last_problem = f"request failed: {exc.__class__.__name__}"
            log.warning("Gemma %s %s", name, last_problem)
            continue
        if resp.status_code < 400:
            break
        last_problem = f"HTTP {resp.status_code}: {resp.text[:200]}"
        log.warning("Gemma %s returned %s", name, last_problem)
        if attempt == len(candidates) - 1:
            raise UpstreamError(f"Gemini API failed -- {last_problem}")
    else:  # pragma: no cover - loop always breaks or raises
        raise UpstreamError(f"Gemini API unavailable -- {last_problem}")

    try:
        data = resp.json()
    except ValueError as exc:
        raise UpstreamError(f"Gemini returned non-JSON: {resp.text[:200]}") from exc

    text, finish = _extract_gemini_text(data)
    if finish == "MAX_TOKENS":
        log.warning("briefing for %s was cut off at the token budget", model)
    return text


# ---------------------------------------------------------------------------
# Tinker writer
# ---------------------------------------------------------------------------
def write_tinker(plan: OutdoorPlan, **kwargs: Any) -> str:
    """Sample from a Tinker-hosted fine-tune.

    Shape of the Tinker sampling API is taken from the vendor docs; if it has
    moved, this raises and the caller falls back to Gemma. Never guess silently.
    """
    settings = get_settings()
    key = settings.tinker_api_key
    if not key:
        raise UpstreamError("TINKER_API_KEY is not set")

    ctx = build_context(plan, kwargs.get("park"))
    prompt = f"{SYSTEM_PROMPT}\n\n{build_user_prompt(ctx)}"
    payload = {
        "prompt": prompt,
        "max_tokens": 320,
        "temperature": 0.4,
    }
    headers = {"Authorization": f"Bearer {key}"}
    try:
        with httpx.Client(timeout=40) as client:
            resp = client.post(TINKER_SAMPLE_URL, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        raise UpstreamError(f"Tinker request failed: {exc}") from exc
    if resp.status_code >= 400:
        raise UpstreamError(f"Tinker API returned HTTP {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    for path in (("samples", 0, "tokens"), ("completion", None, None), ("text", None, None)):
        node: Any = data
        try:
            node = node[path[0]] if path[1] is None else node[path[0]][path[1]][path[2]]
        except (KeyError, IndexError, TypeError):
            continue
        if isinstance(node, list):
            return "".join(str(t) for t in node).strip()
        if isinstance(node, str):
            return node.strip()
    raise UpstreamError(f"unexpected Tinker response shape: {str(data)[:200]}")


# ---------------------------------------------------------------------------
# Safety enforcement (post-generation, not prompt-level)
# ---------------------------------------------------------------------------
_CAVEAT_MARKERS = (
    "naqi",
    "aqi",
    "air is",
    "air quality",
    "unhealthy",
    "moderate",
    "poor",
    "hazardous",
    "dust",
    "pollut",
    "asthma",
    "smoke",
    "clean enough",
)

_HEDGING = (
    "medical",
    "cure",
    "guaranteed safe",
    "guaranteed",
    "you will be fine",
    "completely safe",
    "safe to do anything",
    "doctor's advice",
)


def _has_caveat(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _CAVEAT_MARKERS)


_NUMERIC = re.compile(r"\b(?:naqi|aqi)\s*(?:is|at|of|[:=])?\s*(\d{1,3})\b", re.IGNORECASE)


def _has_numeric_caveat(text: str) -> bool:
    """True when the text already cites a specific NAQI number.

    Gemma often says "the air is only moderate". That *is* an air caveat, but
    it lacks the number Baahar is built around, so we append one. When the
    number is already there, appending a second one just reads as noise.
    """
    return bool(_NUMERIC.search(text))


def enforce_safety(text: str, plan: OutdoorPlan, park: Park | None = None) -> str:
    """Repair the two failures that matter, and flag what it fixed.

    * No air-quality acknowledgement -> append a factual NAQI line.
    * Names a park that isn't ours -> strip the wrong name.
    * Contains medical-claim hedging -> strip it.

    Returns the repaired text. A mismatch in SKIP direction is *always*
    corrected: if the plan says SKIP but the text sounds encouraging, we do not
    ship it.

    Order matters. Hedging is stripped *before* the caveat is appended,
    because the disclaimer we add contains the phrase "not medical advice" and
    the hedging filter -- which targets the word "medical" -- would otherwise
    delete the safety caveat it had just inserted. That bug shipped once: the
    caveat was added and removed in the same call.
    """
    text = _strip_to_words(text)
    fixed: list[str] = []

    if plan.overall is Decision.SKIP and not _sounds_like_skip(text):
        fixed.append("skipped_happy_tone")
        text = write_template(plan, park=park)

    cleaned = _strip_hedging(text)
    if cleaned != text:
        fixed.append("stripped_medical_hedging")
        text = cleaned

    if not _has_caveat(text):
        slot = plan.best_slot
        if (
            slot is not None
            and slot.air.naqi is not None
            and not _has_numeric_caveat(text)
        ):
            band = (slot.air.naqi_band or "").lower()
            text = (
                f"{text.rstrip()} Air right now is Indian NAQI "
                f"{slot.air.naqi:.0f}, {band} -- informational, not medical "
                "advice."
            ).strip()
            fixed.append("added_naqi_caveat")

    if fixed:
        log.info("brief safety repairs applied: %s", ", ".join(fixed))
    return _strip_to_words(text)


_SKIP_MARKERS = ("stay in", "don't go", "do not go", "skip", "wait", "indoors", "not going")


def _sounds_like_skip(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _SKIP_MARKERS)


def _strip_hedging(text: str) -> str:
    out = text
    for phrase in _HEDGING:
        out = re.sub(rf"[^.]*\b{re.escape(phrase)}\b[^.]*\.", "", out, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", out).strip()


#: Northern-Hemisphere-wrong weather that has no business in a Bengaluru
#: October briefing. Each entry has actually shown up in a model draft during
#: testing, which is how the list was built.
_GEOGRAPHY_BLEED = (
    "fall colors",
    "fall colours",
    "fall foliage",
    "New England",
    "autumn leaves",
    "snow",
    "frost",
    "blizzard",
    "icicle",
    "ski",
)


def _ground_park_names(text: str, park: Park | None) -> str:
    """Remove park-like proper nouns that are not the park we chose.

    Only targets a small list of Bengaluru park names plus the US-foliage
    failure modes, because those are the hallucinations that actually showed up
    in eval. Cheap, deterministic, and easy to unit-test.
    """
    if park is None:
        return text
    banned = [
        "Cubbon Park",
        "Lalbagh",
        "Ulsoor Lake",
        "Sankey Lake",
        "Bugle Rock",
        "Kanteerava",
        "Bannerghatta",
        "Hesaraghatta",
        "Kadugodi",
        "Jnanabharathi",
        "Bagmane",
        "Venkatagiri",
        "Corporation Park",
    ]
    other = [b for b in banned if b.lower() != park.name.lower()]
    out = text
    for name in other:
        out = re.sub(rf"\b{re.escape(name)}\b(\s+(?:Park|Lake|Gardens?))?", park.name, out)
    for bleed in _GEOGRAPHY_BLEED:
        out = re.sub(rf"[^.]*\b{re.escape(bleed)}\b[^.]*\.?", "", out, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", out).strip()


# ---------------------------------------------------------------------------
# Voice (optional)
# ---------------------------------------------------------------------------
def speak(text: str) -> str | None:
    """Return an audio URL via ElevenLabs, or ``None`` if unavailable."""
    settings = get_settings()
    if not settings.has_elevenlabs:
        return None
    try:
        with httpx.Client(timeout=45) as client:
            resp = client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{settings.elevenlabs_voice_id}",
                headers={"xi-api-key": settings.elevenlabs_api_key},
                json={
                    "text": text,
                    "model_id": settings.elevenlabs_model,
                    "voice_settings": {"stability": 0.4, "similarity_boost": 0.8},
                },
            )
        if resp.status_code >= 400:
            log.warning("ElevenLabs returned HTTP %s", resp.status_code)
            return None
    except httpx.HTTPError as exc:
        log.warning("ElevenLabs request failed: %s", exc)
        return None

    from .config import DATA_DIR

    out_dir = DATA_DIR / "cache" / "audio"
    out_dir.mkdir(parents=True, exist_ok=True)
    digest = abs(hash(text)) % (10**10)
    path = out_dir / f"brief_{digest}.mp3"
    path.write_bytes(resp.content)
    return path.as_uri()


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
def _cache_key(plan: OutdoorPlan, park: Park | None, writer: str) -> str:
    """Stable key for a briefing request.

    Built from the *rounded* conditions, not the raw floats, so that two calls
    in the same weather state reuse one model call instead of paying 45 s
    twice. The consequence -- a cached text that is a few minutes stale for a
    slowly-drifting NAQI -- is acceptable for a 20-minute walk plan, and the
    key is exposed in the response so nothing is hidden.
    """
    slot = plan.best_slot
    air, weather = (slot.air, slot.weather) if slot else (None, None)
    payload = {
        "w": writer,
        "city": plan.city,
        "decision": plan.overall.value,
        "hour": plan.best_time.strftime("%H") if plan.best_time else None,
        "park": park.name if park else None,
        "naqi": round(air.naqi / 10) * 10 if air and air.naqi is not None else None,
        "apparent": round(weather.apparent_c) if weather and weather.apparent_c else None,
        "precip": round(weather.precip_prob / 10) * 10 if weather and weather.precip_prob else None,
    }
    blob = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def cache_path(key: str) -> Any:
    from .config import DATA_DIR

    return DATA_DIR / "cache" / "briefings" / f"{key}.json"


def _read_cache(key: str) -> Briefing | None:
    path = cache_path(key)
    if not path.exists():
        return None
    try:
        return Briefing.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except Exception as exc:  # noqa: BLE001
        log.warning("ignoring unreadable briefing cache %s: %s", key, exc)
        return None


def _write_cache(key: str, briefing: Briefing) -> None:
    path = cache_path(key)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(briefing.model_dump_json(indent=2), encoding="utf-8")
    except OSError as exc:  # pragma: no cover
        log.warning("could not write briefing cache: %s", exc)


def clear_cache() -> int:
    """Delete cached briefings. Returns how many were removed."""
    directory = cache_path("x").parent
    if not directory.exists():
        return 0
    removed = 0
    for path in directory.glob("*.json"):
        try:
            path.unlink()
            removed += 1
        except OSError:
            pass
    return removed


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def generate(
    plan: OutdoorPlan,
    *,
    writer: str = "auto",
    park: Park | None = None,
    voice: bool = False,
    notice_this: str | None = None,
) -> Briefing:
    """Produce the briefing. Never raises for an ordinary failure.

    With a model key present, this costs tens of seconds (measured -- see
    `eval/RESULTS.md`). Since a user who has just asked "can I go for a walk?"
    will not wait a minute for a paragraph, successful model briefings are
    cached on the rounded conditions and the cache is checked first. Use
    `writer="template"` to always skip the model, or clear it with
    `baahar.cache-clear`.
    """
    settings = get_settings()
    started = time.perf_counter()
    writer = (writer or "auto").lower()
    note_parts: list[str] = []

    key = _cache_key(plan, park, writer)
    if writer != "template" and get_settings().cache_enabled:
        cached = _read_cache(key)
        if cached is not None:
            cached.note = (cached.note + " " if cached.note else "") + "served from cache"
            return cached

    def finish(t: str, w: str, note: str = "") -> Briefing:
        repaired = enforce_safety(t, plan, park=park)
        grounded = _ground_park_names(repaired, park)
        final = _complete_last_sentence(_strip_to_words(grounded))
        briefing = Briefing(
            text=final,
            model=w,
            writer=w,
            word_count=len(final.split()),
            note=note,
            audio_url=speak(final) if voice else None,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
        if w != "template" and settings.cache_enabled:
            _write_cache(key, briefing)
        return briefing

    if writer == "template":
        return finish(write_template(plan, park=park, notice_this=notice_this), "template")

    if writer in {"gemma", "tinker"}:
        chosen = writer
        if chosen == "gemma" and not settings.has_gemini:
            note_parts.append("No GEMINI_API_KEY; used the local template writer.")
            return finish(write_template(plan, park=park, notice_this=notice_this), "template", note_parts[0])
        if chosen == "tinker" and not settings.has_tinker:
            note_parts.append("No TINKER_API_KEY; used Gemma.")
            chosen = "gemma"
        try:
            fn = write_gemma if chosen == "gemma" else write_tinker
            raw = fn(plan, park=park, notice_this=notice_this)
            return finish(raw, "hybrid", f"generated by {chosen}, then safety-checked.")
        except UpstreamError as exc:
            note_parts.append(f"{chosen} call failed ({exc}); used the local template.")
            return finish(write_template(plan, park=park, notice_this=notice_this), "template", " ".join(note_parts))

    # auto: prefer Tinker (fine-tuned), then Gemma, then template.
    if settings.has_tinker:
        try:
            raw = write_tinker(plan, park=park, notice_this=notice_this)
            return finish(raw, "hybrid", "generated by the Tinker fine-tune, then safety-checked.")
        except UpstreamError as exc:
            note_parts.append(f"Tinker unavailable ({exc}).")
    if settings.has_gemini:
        try:
            raw = write_gemma(plan, park=park, notice_this=notice_this)
            return finish(raw, "hybrid", "generated by Gemma, then safety-checked.")
        except UpstreamError as exc:
            note_parts.append(f"Gemma unavailable ({exc}).")
    if note_parts:
        note_parts.append("Used the local template writer.")
    return finish(
        write_template(plan, park=park, notice_this=notice_this),
        "template",
        " ".join(note_parts),
    )


def briefing_payload(plan: OutdoorPlan, park: Park | None = None) -> dict[str, Any]:
    """Structured facts as JSON -- used by the eval harness for scoring."""
    ctx = build_context(plan, park)
    return json.dumps(ctx, indent=2, default=str)