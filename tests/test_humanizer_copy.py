"""Regression tests for the 2026-10-10 scenario-drill copy defects.

These are not field tests. They pin strings the app actually prints, so a
stranger cannot be told WAIT and GO on the same line, and a local journal
cannot impersonate docs/FIELD_TEST.md.
"""

from __future__ import annotations

from baahar.briefing_contract import deterministic_fallback
from baahar.journal import render_markdown


def test_briefing_prose_never_uses_forecast_window_as_a_sentence():
    text = deterministic_fallback(
        {
            "facts": {
                "decision": "WAIT",
                "park": "Cubbon Park",
                "naqi": 130,
                "band": "moderate",
                "apparent_c": 29,
                "precip_mm": 0,
                "precip_prob": 1,
                "air_available": True,
                "weather_available": True,
                "is_day": False,
                "time": "19:00",
                "weather_code": None,
                "walk_allowed": False,
                "scheduled_time": "06:00",
                "allowed_park_names": ["Cubbon Park"],
            }
        }
    )
    assert "Forecast window" not in text
    assert "The next hour to recheck is 06:00" in text
    assert not any(tok == "GO" for tok in text.split())


def test_journal_markdown_disclaims_the_field_test():
    assert "FIELD_TEST.md" in render_markdown([])
