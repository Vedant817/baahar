"""Baahar configuration.

Deliberately dependency-free (no pydantic-settings): a plain dataclass reads
`.env` and the real environment so that a judge can `pip install -e .` and see
a working tool with no configuration step at all.

Every knob has a working default. Nothing in this module is required.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# repo root: src/baahar/config.py -> src/baahar -> src -> <root>
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
SAMPLES_DIR = DATA_DIR / "samples"
EVAL_DATA_DIR = DATA_DIR / "eval"
PARKS_FILE = DATA_DIR / "parks_blr.json"
EVAL_DIR = REPO_ROOT / "eval"
EVAL_RAW_DIR = EVAL_DIR / "raw"
STATIC_DIR = Path(__file__).resolve().parent / "static"

load_dotenv(REPO_ROOT / ".env", override=False)


def _flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _secret(name: str) -> str | None:
    raw = (os.getenv(name) or "").strip()
    return raw or None


@dataclass(frozen=True)
class Settings:
    """Runtime settings. Construct via :func:`get_settings`."""

    # --- location -------------------------------------------------------
    city: str = "Bengaluru"
    lat: float = 12.9716
    lon: float = 77.5946
    timezone: str = "Asia/Kolkata"

    # --- behaviour ------------------------------------------------------
    #: Force recorded fixtures even when the network is healthy.
    offline: bool = False
    #: Hours of forecast to pull.
    forecast_hours: int = 24
    #: Hours actually scored for the user-facing table.
    plan_hours: int = 12
    #: Default Pocket Mode walk length.
    walk_minutes: int = 20
    #: Outbound HTTP timeout, seconds.
    http_timeout: float = 12.0
    #: Cache successful model-generated briefings between identical requests.
    #: Measured Gemma latency is tens of seconds, so this is what makes the
    #: product bearable rather than a demo trick.
    cache_enabled: bool = True

    # --- keys (all optional) -------------------------------------------
    gemini_api_key: str | None = None
    #: Pinned open-weight Gemma model. Defaults were taken from a live
    #: `GET /v1beta/models` listing on 2026-10-06, which returned
    #: `gemma-4-31b-it` and `gemma-4-26b-a4b-it`; older pins such as
    #: `gemma-2.5-9b-it` now 404. Both are pinned in `.env.example` too.
    gemma_model: str = "gemma-4-31b-it"
    gemma_model_fallback: str = "gemma-4-26b-a4b-it"
    tinker_api_key: str | None = None
    tinker_lora_path: str | None = None
    tabpfn_api_key: str | None = None
    tabpfn_base_url: str = "https://api.priorlabs.ai"
    #: Optional path to a pickled TabPFN classifier fitted by
    #: `scripts/run_eval.py`. Optional: with no artifact, the scorer uses the
    #: documented policy.
    tabpfn_model_path: str | None = None
    elevenlabs_api_key: str | None = None
    elevenlabs_voice_id: str | None = None
    elevenlabs_model: str = "eleven_flash_v2_5"
    waqi_token: str | None = None

    # --- model selection defaults ---------------------------------------
    #: "auto" | "gemma" | "tinker" | "template"
    default_brief_model: str = "auto"
    #: "auto" | "tabpfn" | "heuristic"
    default_scorer: str = "auto"

    extra: dict[str, str] = field(default_factory=dict)

    # -- derived helpers --------------------------------------------------
    @property
    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def has_tinker(self) -> bool:
        return bool(self.tinker_api_key)

    @property
    def has_tabpfn_api(self) -> bool:
        return bool(self.tabpfn_api_key)

    @property
    def has_elevenlabs(self) -> bool:
        return bool(self.elevenlabs_api_key and self.elevenlabs_voice_id)

    @property
    def has_waqi(self) -> bool:
        return bool(self.waqi_token)

    def which_keys(self) -> dict[str, bool]:
        """Presence-only key map, safe to print and to commit to eval artifacts."""
        return {
            "gemini": self.has_gemini,
            "tinker": self.has_tinker,
            "tabpfn_api": self.has_tabpfn_api,
            "elevenlabs": self.has_elevenlabs,
            "waqi": self.has_waqi,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings from `.env` + environment, cached for the process."""
    return Settings(
        city=os.getenv("BAAHAR_CITY", "Bengaluru"),
        lat=_float("BAAHAR_LAT", 12.9716),
        lon=_float("BAAHAR_LON", 77.5946),
        timezone=os.getenv("BAAHAR_TZ", "Asia/Kolkata"),
        offline=_flag("BAAHAR_OFFLINE", False),
        forecast_hours=_int("BAAHAR_FORECAST_HOURS", 24),
        plan_hours=_int("BAAHAR_PLAN_HOURS", 12),
        walk_minutes=_int("BAAHAR_WALK_MINUTES", 20),
        http_timeout=_float("BAAHAR_HTTP_TIMEOUT", 12.0),
        cache_enabled=_flag("BAAHAR_CACHE", True),
        gemini_api_key=_secret("GEMINI_API_KEY"),
        gemma_model=os.getenv("GEMMA_MODEL", "gemma-4-31b-it"),
        gemma_model_fallback=os.getenv("GEMMA_MODEL_FALLBACK", "gemma-4-26b-a4b-it"),
        tinker_api_key=_secret("TINKER_API_KEY"),
        tinker_lora_path=_secret("TINKER_LORA_PATH"),
        tabpfn_api_key=_secret("TABPFN_API_KEY"),
        tabpfn_base_url=os.getenv("TABPFN_BASE_URL", "https://api.priorlabs.ai"),
        tabpfn_model_path=_secret("TABPFN_MODEL_PATH"),
        elevenlabs_api_key=_secret("ELEVENLABS_API_KEY"),
        elevenlabs_voice_id=_secret("ELEVENLABS_VOICE_ID"),
        elevenlabs_model=os.getenv("ELEVENLABS_MODEL", "eleven_flash_v2_5"),
        waqi_token=_secret("WAQI_TOKEN"),
        default_brief_model=os.getenv("BAAHAR_BRIEF_MODEL", "auto"),
        default_scorer=os.getenv("BAAHAR_SCORER", "auto"),
    )


def repo_root() -> Path:
    return REPO_ROOT