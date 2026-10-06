"""Briefing safety enforcement.

The prompt *asks* the model to include a safety caveat. These tests assert that
Baahar does not depend on that request: :func:`enforce_safety` repairs the text
afterwards, and these cases pin the repairs.

Every case here corresponds to a failure observed during real runs, not a
theoretical one.
"""

from __future__ import annotations

import pytest

from baahar.brief import (
    MAX_WORDS,
    _complete_last_sentence,
    _extract_gemini_text,
    _ground_park_names,
    _has_numeric_caveat,
    _strip_hedging,
    _strip_to_words,
    enforce_safety,
    generate,
)
from baahar.models import DataSource
from baahar.score import build_plan


@pytest.fixture
def go_plan(go_slot):
    from baahar.parks import park_by_id

    park = park_by_id("cubbon")
    return build_plan(
        [go_slot],
        park=park,
        weather_source=DataSource.LIVE,
        air_source=DataSource.LIVE,
    )


@pytest.fixture
def skip_plan(hazardous_slot):
    from baahar.parks import park_by_id

    park = park_by_id("hesaraghatta")
    return build_plan(
        [hazardous_slot],
        park=park,
        weather_source=DataSource.LIVE,
        air_source=DataSource.LIVE,
    )


class TestSkipDirection:
    def test_an_encouraging_text_is_replaced_when_the_plan_says_skip(self, skip_plan) -> None:
        """The single most important test in this file.

        A cheerful "perfect day for a walk" must never survive a SKIP plan.
        """
        cheerful = (
            "It's a beautiful morning for a walk! Head to the park and enjoy the "
            "clear skies and gentle breeze. You will have a wonderful time."
        )
        out = enforce_safety(cheerful, skip_plan, park=skip_plan.park)
        assert "beautiful morning for a walk" not in out.lower()
        assert any(m in out.lower() for m in ("stay in", "skip", "wait", "indoors"))

    def test_a_correct_skip_text_is_left_alone(self, skip_plan) -> None:
        honest = "Stay in. The air is severe at NAQI 409 and it feels like 41C."
        out = enforce_safety(honest, skip_plan, park=skip_plan.park)
        assert out == honest


class TestCaveats:
    def test_a_missing_naqi_caveat_is_appended(self, go_plan) -> None:
        text = "Go at 06:00. The trees are lovely and the paths are quiet this early."
        out = enforce_safety(text, go_plan, park=go_plan.park)
        assert _has_numeric_caveat(out)
        assert "NAQI" in out

    def test_an_existing_naqi_number_is_not_duplicated(self, go_plan) -> None:
        text = "Go at 06:00. The air is satisfactory at NAQI 18. Head to Cubbon Park."
        out = enforce_safety(text, go_plan, park=go_plan.park)
        assert out.lower().count("naqi") == 1, out

    def test_numeric_caveat_detection(self) -> None:
        assert _has_numeric_caveat("NAQI 74 is fine")
        assert _has_numeric_caveat("the air is at NAQI: 120")
        assert not _has_numeric_caveat("the air is moderate")
        assert not _has_numeric_caveat("NAQI is not great")


class TestMedicalClaims:
    @pytest.mark.parametrize(
        "text",
        [
            "This walk is guaranteed safe for everyone.",
            "It is the medical cure for a bad week.",
            "You will be fine, do not worry about your asthma.",
        ],
    )
    def test_medical_hedging_is_stripped(self, go_plan, text: str) -> None:
        out = enforce_safety(text, go_plan, park=go_plan.park)
        lowered = out.lower()
        assert "guaranteed safe" not in lowered
        assert "medical cure" not in lowered
        assert "you will be fine" not in lowered

    def test_strip_hedging_removes_the_sentence_not_the_paragraph(self) -> None:
        out = _strip_hedging("Go outside. This is guaranteed safe. Listen to the birds.")
        assert "guaranteed" not in out.lower()
        assert "listen to the birds" in out.lower()


class TestHallucination:
    def test_a_different_park_is_replaced(self, go_plan) -> None:
        text = "Go at 06:00. Head to Lalbagh for the morning. NAQI 18."
        out = _ground_park_names(text, go_plan.park)
        assert "Lalbagh" not in out
        assert "Cubbon Park" in out

    def test_us_foliage_bleed_is_removed(self, go_plan) -> None:
        text = "Go at 06:00. Enjoy the fall colors in New England. NAQI 18."
        out = _ground_park_names(text, go_plan.park)
        lowered = out.lower()
        assert "fall colors" not in lowered
        assert "new england" not in lowered

    def test_the_chosen_park_is_never_rewritten(self, go_plan) -> None:
        text = "Go at 06:00. Head to Cubbon Park. NAQI 18."
        assert _ground_park_names(text, go_plan.park) == text

    def test_a_shared_prefix_does_not_duplicate_the_name(self, go_plan) -> None:
        """Regression: "Lalbagh Botanical Garden" became "... Garden Garden".

        The grounding list holds the short token "Lalbagh". When the chosen park
        is *Lalbagh Botanical Garden*, replacing that token spliced the full name
        in front of the suffix that was already there.
        """
        from baahar.parks import park_by_id

        lalbagh = park_by_id("lalbagh")
        text = "Go at 06:00. Head to Lalbagh Botanical Garden. NAQI 18."
        out = _ground_park_names(text, lalbagh)
        assert out == text
        assert "Garden Botanical" not in out
        assert out.count("Botanical Garden") == 1

    def test_a_genuinely_different_park_is_still_replaced(self, go_plan) -> None:
        """The fix above must not disable hallucination grounding."""
        from baahar.parks import park_by_id

        lalbagh = park_by_id("lalbagh")
        out = _ground_park_names("Go at 06:00. Head to Cubbon Park. NAQI 18.", lalbagh)
        assert "Cubbon" not in out
        assert "Lalbagh Botanical Garden" in out

    def test_snow_is_stripped_from_an_october_plan(self, go_plan) -> None:
        out = _ground_park_names(
            "Go at 06:00. Watch the snow fall on the trees. NAQI 18.", go_plan.park
        )
        assert "snow" not in out.lower()


class TestTruncation:
    def test_short_text_is_untouched(self) -> None:
        assert _strip_to_words("Go at six. It is fine.") == "Go at six. It is fine."

    def test_long_text_is_cut_on_a_sentence_boundary(self) -> None:
        words = [f"word{i}" for i in range(400)]
        text = " ".join(words[:60]) + ". " + " ".join(words[60:120]) + ". " + " ".join(words[120:])
        out = _strip_to_words(text, MAX_WORDS)
        assert len(out.split()) <= MAX_WORDS
        assert out.endswith(".")

    def test_a_park_name_is_never_cut_in_half(self) -> None:
        """Regression: an earlier version produced the literal text "Head to Cub".

        `_strip_to_words` ran before the safety pass, so a 124-word answer was
        truncated mid-token and shipped a half park name to the user.
        """
        padding = " ".join(["filler"] * 200)
        text = f"Go at 06:00. Head to Cubbon Park, {padding}"
        out = _strip_to_words(text, MAX_WORDS)
        assert "Head to Cub" not in out
        assert "Cub\n" not in out

    def test_complete_last_sentence_drops_whole_sentences(self) -> None:
        text = " ".join(["word"] * 118) + ". Extra sentence here."
        out = _complete_last_sentence(text, MAX_WORDS)
        assert len(out.split()) <= MAX_WORDS
        assert not out.endswith("word") or out.endswith(".")

    def test_output_is_always_within_budget(self, go_plan) -> None:
        for text in ("Go at 06:00. " * 60, "Stay in.", "x " * 400):
            out = enforce_safety(text, go_plan, park=go_plan.park)
            assert len(out.split()) <= MAX_WORDS, out[:120]


class TestTemplateWriter:
    def test_template_always_produces_text(self, go_plan) -> None:
        briefing = generate(go_plan, writer="template", park=go_plan.park)
        assert briefing.text
        assert briefing.writer == "template"
        assert briefing.word_count <= MAX_WORDS

    def test_template_respects_skip(self, skip_plan) -> None:
        briefing = generate(skip_plan, writer="template", park=skip_plan.park)
        assert briefing.text.lower().startswith("stay in")

    def test_template_is_deterministic(self, go_plan) -> None:
        a = generate(go_plan, writer="template", park=go_plan.park)
        b = generate(go_plan, writer="template", park=go_plan.park)
        assert a.text == b.text

    def test_missing_key_falls_back_without_raising(self, go_plan, monkeypatch) -> None:
        """No GEMINI_API_KEY must degrade, not crash."""
        monkeypatch.setenv("GEMINI_API_KEY", "")
        from baahar import config

        config.get_settings.cache_clear()
        briefing = generate(go_plan, writer="gemma", park=go_plan.park)
        config.get_settings.cache_clear()
        assert briefing.writer == "template"
        assert briefing.text
        assert "GEMINI_API_KEY" in briefing.note

    def test_requesting_tinker_says_so_when_it_falls_back(self, go_plan, monkeypatch) -> None:
        """Asking for Tinker must never quietly hand back a Gemma briefing.

        Regression: the note used to say only "generated by gemma", which was
        technically true and completely misleading about what was requested.
        """
        monkeypatch.setenv("TINKER_API_KEY", "")
        monkeypatch.setenv("TINKER_SAMPLE_URL", "")
        from baahar import config

        config.get_settings.cache_clear()
        briefing = generate(go_plan, writer="tinker", park=go_plan.park)
        config.get_settings.cache_clear()
        if briefing.writer == "hybrid":  # a Gemma key is present in CI
            assert "Tinker" in briefing.note
            assert "No fine-tuned model served this briefing" in briefing.note

    def test_tinker_without_a_configured_endpoint_refuses(self, go_plan, monkeypatch) -> None:
        """The Tinker writer must not guess an endpoint.

        An earlier version hard-coded a plausible-looking URL that had never been
        called. Refusing loudly is the correct behaviour when the API shape is
        unverified.
        """
        from baahar.brief import TINKER_SAMPLE_URL, write_tinker
        from baahar.http_client import UpstreamError

        if TINKER_SAMPLE_URL:
            pytest.skip("TINKER_SAMPLE_URL is configured in this environment")
        # A key is set so the writer gets past the first gate and reaches the
        # endpoint check, which is the behaviour under test.
        monkeypatch.setenv("TINKER_API_KEY", "test-key-not-a-real-credential")
        from baahar import config

        config.get_settings.cache_clear()
        with pytest.raises(UpstreamError, match="TINKER_SAMPLE_URL"):
            write_tinker(go_plan, park=go_plan.park)
        config.get_settings.cache_clear()

    def test_tinker_without_a_key_says_the_key_is_missing(self, go_plan, monkeypatch) -> None:
        # `get_settings` is memoised, so clearing the environment variable alone is
        # not enough -- a cached Settings built earlier still carries the key.
        # This test only passed while no Tinker key existed anywhere; it started
        # failing the moment one was configured, which is a test bug, not a
        # product bug.
        from baahar import config
        from baahar.brief import write_tinker
        from baahar.http_client import UpstreamError

        monkeypatch.setenv("TINKER_API_KEY", "")
        config.get_settings.cache_clear()
        try:
            assert config.get_settings().tinker_api_key is None
            with pytest.raises(UpstreamError, match="TINKER_API_KEY"):
                write_tinker(go_plan, park=go_plan.park)
        finally:
            config.get_settings.cache_clear()


class TestGeminiResponseParsing:
    """The reasoning-part bug found live on 2026-10-06."""

    def test_reasoning_parts_are_skipped(self) -> None:
        payload = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "internal chain of thought", "thought": True},
                            {"text": "Go at six. It is clean."},
                        ]
                    },
                    "finishReason": "STOP",
                }
            ]
        }
        text, finish = _extract_gemini_text(payload)
        assert text == "Go at six. It is clean."
        assert "chain of thought" not in text
        assert finish == "STOP"

    def test_only_a_reasoning_part_is_an_error(self) -> None:
        """Previously this silently shipped the model's notes as the briefing."""
        payload = {
            "candidates": [
                {
                    "content": {"parts": [{"text": "thinking...", "thought": True}]},
                    "finishReason": "MAX_TOKENS",
                }
            ]
        }
        with pytest.raises(Exception, match="reasoning part"):
            _extract_gemini_text(payload)

    def test_no_candidates_is_an_error(self) -> None:
        with pytest.raises(Exception, match="no candidates"):
            _extract_gemini_text({"error": {"message": "boom"}})

    def test_truncation_is_reported(self) -> None:
        payload = {
            "candidates": [
                {"content": {"parts": [{"text": "partial"}]}, "finishReason": "MAX_TOKENS"}
            ]
        }
        _, finish = _extract_gemini_text(payload)
        assert finish == "MAX_TOKENS"
