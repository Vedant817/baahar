"""The Gemini fallback must survive a transient failure, not just a dead model.

Measured 2026-10-07 against the live API: gemma-4-31b-it returned HTTP 500 on
roughly a third of byte-identical requests, and 503 (an explicit high-demand
message) on others. gemma-4-26b-a4b-it answered every time.

Two properties matter and neither was covered before:

* A transient 5xx/429 on the pinned model should be retried on that same model.
  Swapping models on the first blip discards a working model for no reason.
* A 4xx must NOT be retried. A revoked key or a retired model id fails
  identically forever, and retrying only delays the honest error.
"""

from __future__ import annotations

from datetime import datetime

import httpx
import pytest

from baahar import brief
from baahar.models import HourlyAir, HourlyWeather, HourSlot


class _Resp:
    def __init__(self, status_code: int, text: str = "") -> None:
        self.status_code = status_code
        self.text = text or f'{{"error":{{"code":{status_code}}}}}'

    def json(self) -> dict:
        return {
            "candidates": [
                {"content": {"parts": [{"text": "Six in the morning."}]}, "finishReason": "STOP"}
            ]
        }


def _plan():
    """A real plan built from a real slot.

    Deliberately not a hand-constructed OutdoorPlan: write_gemma reads a real
    briefing context out of this object, and a stub would only prove the retry
    loop runs, not that it runs on the payload we actually send.
    """
    from baahar.models import DataSource
    from baahar.score import build_plan

    slot = HourSlot(
        weather=HourlyWeather(
            time=datetime(2026, 10, 7, 6, 0),
            temp_c=24.0,
            apparent_c=25.0,
            precip_mm=0.0,
            precip_prob=10.0,
            humidity=70.0,
            wind_kmh=6.0,
            weather_code=1,
            is_day=1,
        ),
        air=HourlyAir(
            time=datetime(2026, 10, 7, 6, 0),
            pm25=18.0,
            pm10=32.0,
            naqi_effective=72.0,
            naqi_band="satisfactory",
        ),
    )
    return build_plan(
        [slot],
        weather_source=DataSource.FIXTURE,
        air_source=DataSource.FIXTURE,
        scorer="heuristic",
    )


@pytest.fixture
def scripted(monkeypatch):
    """Return a recorder that scripts a sequence of HTTP statuses per model."""
    calls: list[str] = []

    def build(
        pinned_statuses: list[int],
        *,
        fallback_statuses: list[int] | None = None,
        pinned: str = "gemma-pinned",
        fallback: str = "fb",
    ):
        """Script each model's own status sequence.

        Keying on the MODEL rather than on a flat call order is what lets a test
        say "the pinned model is dead but the fallback is healthy" - precisely the
        case the fallback exists for. A flat script cannot express it: once the
        pinned model's retries are exhausted the fallback inherits whatever status
        happened to be last, which makes the test assert the wrong thing.
        """

        fb_script = pinned_statuses if fallback_statuses is None else fallback_statuses

        def fake_post(model_name: str) -> _Resp:
            calls.append(model_name)
            script = fb_script if model_name == fallback else pinned_statuses
            index = calls.count(model_name) - 1
            status = script[min(index, len(script) - 1)]
            return _Resp(status)

        monkeypatch.setattr(brief, "GEMINI_HTTP_POST_HOOK", fake_post)
        monkeypatch.setattr(brief, "GEMINI_RETRY_S", 0, raising=False)
        monkeypatch.setattr(brief, "GEMINI_RETRIES", 2, raising=False)
        monkeypatch.setattr(brief, "GEMINI_TIMEOUT_S", 0.001, raising=False)
        monkeypatch.setattr(brief, "GEMINI_MAX_OUTPUT_TOKENS", 64, raising=False)
        monkeypatch.setattr(brief, "build_user_prompt", lambda _ctx: "prompt", raising=False)
        monkeypatch.setattr(brief, "build_context", lambda *_a, **_k: None, raising=False)

        class _Settings:
            gemini_api_key = "key"
            gemma_model = pinned
            gemma_model_fallback = fallback

        monkeypatch.setattr(brief, "get_settings", lambda: _Settings(), raising=False)
        return calls

    return build


@pytest.mark.parametrize("status", [429, 500, 502, 503])
def test_transient_status_is_retried_on_the_same_model(scripted, status):
    """A 5xx/429 means 'not now'; it must not cost us the pinned model."""
    calls = scripted([status, status, 200])
    brief.write_gemma(_plan())
    assert calls == ["gemma-pinned"] * 3, calls


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_client_error_is_not_retried(scripted, status):
    """A 4xx means 'never'. Retrying only delays the honest error."""
    calls = scripted([status])
    with pytest.raises(brief.UpstreamError):
        brief.write_gemma(_plan())
    assert calls == ["gemma-pinned", "fb"], calls


def test_exhausted_retries_still_fall_back(scripted):
    """A pinned model that is genuinely gone must still reach the fallback."""
    # Pinned always 500; fallback healthy. The fallback is what rescues us.
    calls = scripted([500], fallback_statuses=[200])
    brief.write_gemma(_plan())
    assert calls[:3] == ["gemma-pinned"] * 3, calls
    assert calls[-1] == "fb", calls


def test_both_models_failing_raises_honestly(scripted):
    """If everything fails, say so - never return a cheerful empty briefing."""
    calls = scripted([500])
    with pytest.raises(brief.UpstreamError):
        brief.write_gemma(_plan())
    assert calls == ["gemma-pinned"] * 3 + ["fb"] * 3, calls


def test_healthy_model_is_called_exactly_once(scripted):
    """The retry must not add latency to the common case."""
    calls = scripted([200])
    brief.write_gemma(_plan())
    assert calls == ["gemma-pinned"], calls


def test_transport_error_is_retried_then_falls_back(monkeypatch):
    """A timeout or reset is transient too, and must not lose the briefing."""
    calls: list[str] = []

    def fake_post(model_name: str):
        calls.append(model_name)
        if model_name == "gemma-pinned":
            raise httpx.ConnectError("connection reset")
        return _Resp(200)

    monkeypatch.setattr(brief, "GEMINI_HTTP_POST_HOOK", fake_post)
    monkeypatch.setattr(brief, "GEMINI_RETRY_S", 0, raising=False)
    monkeypatch.setattr(brief, "GEMINI_RETRIES", 2, raising=False)
    monkeypatch.setattr(brief, "GEMINI_TIMEOUT_S", 0.001, raising=False)
    monkeypatch.setattr(brief, "GEMINI_MAX_OUTPUT_TOKENS", 64, raising=False)
    monkeypatch.setattr(brief, "build_user_prompt", lambda _ctx: "prompt", raising=False)
    monkeypatch.setattr(brief, "build_context", lambda *_a, **_k: None, raising=False)

    class _Settings:
        gemini_api_key = "key"
        gemma_model = "gemma-pinned"
        gemma_model_fallback = "fb"

    monkeypatch.setattr(brief, "get_settings", lambda: _Settings(), raising=False)

    brief.write_gemma(_plan())
    assert calls == ["gemma-pinned"] * 3 + ["fb"], calls
