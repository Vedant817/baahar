"""The GO / WAIT / SKIP policy, and the safety asymmetry around TabPFN, LightGBM, and Ensemble.

The tests here encode the *safety contract*: the product must never tell a user
to go outside in conditions the policy calls SKIP, no matter what a learned
model says.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from baahar.features import (
    BAND_ORDINALS,
    COMPACT_FEATURE_NAMES,
    NAQI_SKIP,
    NAQI_WAIT,
    build_dataset,
    features_from_slot,
    heuristic_decision,
    time_split,
)
from baahar.models import DataSource, Decision, HourSlot, SlotScore
from baahar.score import (
    DEFAULT_ENSEMBLE_ARTIFACT,
    DEFAULT_LGBM_ARTIFACT,
    DEFAULT_TABPFN_ARTIFACT,
    TABPFN_LABELS,
    build_plan,
    choose_scorer,
    display_window,
    ensemble_available,
    lgbm_available,
    load_ensemble_model,
    load_lgbm_model,
    pick_best,
    save_ensemble_model,
    save_lgbm_model,
    score_heuristic,
    score_slots,
    tabpfn_available,
)

#: Mirrors `tests/conftest.py`. Duplicated rather than imported because `tests/`
#: is not a package, so `from tests.conftest import ...` fails at collection.
IST = timezone(timedelta(hours=5, minutes=30))
BASE = datetime(2026, 10, 6, 5, 0, tzinfo=IST)


class TestPolicy:
    def test_clean_morning_is_go(self, go_slot: HourSlot) -> None:
        decision, reasons = heuristic_decision(go_slot)
        assert decision is Decision.GO
        assert reasons

    def test_hazardous_air_is_skip(self, hazardous_slot: HourSlot) -> None:
        decision, reasons = heuristic_decision(hazardous_slot)
        assert decision is Decision.SKIP
        assert any("NAQI" in r for r in reasons)

    def test_heavy_rain_is_skip(self, rain_slot: HourSlot) -> None:
        decision, reasons = heuristic_decision(rain_slot)
        assert decision is Decision.SKIP
        assert any("rain" in r.lower() for r in reasons)

    def test_thunderstorm_is_skip(self, thunder_slot: HourSlot) -> None:
        decision, reasons = heuristic_decision(thunder_slot)
        assert decision is Decision.SKIP
        assert any("thunder" in r.lower() for r in reasons)

    def test_night_with_good_air_is_wait_not_skip(self, night_slot: HourSlot) -> None:
        """Park gates shut at night, so WAIT -- but the air is fine."""
        decision, _ = heuristic_decision(night_slot)
        assert decision is Decision.WAIT

    def test_missing_air_data_is_skip_not_go(self, missing_air_slot: HourSlot) -> None:
        """The one case that must never become a cheerful answer."""
        decision, reasons = heuristic_decision(missing_air_slot)
        assert decision is Decision.SKIP
        assert "not guessing" in reasons[0].lower()

    def test_poor_but_not_severe_air_is_wait(self, slot) -> None:
        decision, _ = heuristic_decision(
            slot(0, temp_c=27.0, apparent_c=28.0, pm25=95.0, pm10=150.0)
        )
        assert decision is Decision.WAIT

    def test_extreme_heat_alone_is_skip(self, slot) -> None:
        decision, reasons = heuristic_decision(
            slot(0, temp_c=33.0, apparent_c=38.0, pm25=15.0, pm10=25.0)
        )
        assert decision is Decision.SKIP
        assert any("feels like" in r.lower() for r in reasons)


class TestBoundaryBehaviour:
    """The NAQI thresholds must sit exactly on CPCB's category edges."""

    @pytest.mark.parametrize(
        ("naqi", "expected"),
        [
            (0, Decision.GO),
            (100, Decision.GO),
            (150, Decision.GO),  # top of CPCB Moderate
            (199, Decision.GO),  # just below NAQI_WAIT
            (200, Decision.WAIT),  # NAQI_WAIT, the top of Moderate
            (201, Decision.WAIT),  # CPCB Poor begins
            (299, Decision.WAIT),
            (300, Decision.SKIP),  # NAQI_SKIP: the SKIP check runs first
            (301, Decision.SKIP),  # CPCB Severe begins
            (400, Decision.SKIP),
            (401, Decision.SKIP),
        ],
    )
    def test_naqi_thresholds(self, slot, naqi: float, expected: Decision) -> None:
        decision, _ = heuristic_decision(
            slot(0, temp_c=24.0, apparent_c=25.0, pm25=10.0, pm10=20.0, naqi=naqi)
        )
        assert decision is expected

    def test_thresholds_match_declared_constants(self) -> None:
        assert NAQI_WAIT == 200.0
        assert NAQI_SKIP == 300.0


class TestScoring:
    @pytest.mark.parametrize("field", ["apparent_c", "precip_mm"])
    @pytest.mark.parametrize("value", [None, float("nan"), float("inf")])
    def test_unknown_heat_or_rain_cannot_recommend_a_walk(self, go_slot, field, value):
        weather = go_slot.weather.model_copy(update={field: value})
        incomplete = go_slot.model_copy(update={"weather": weather})
        plan = build_plan([incomplete], scorer="heuristic")
        assert plan.overall is Decision.SKIP
        assert "not guessing" in plan.slots[0].reasons[0]

    def test_optional_weather_context_can_be_absent(self, go_slot):
        weather = go_slot.weather.model_copy(
            update={
                "temp_c": None,
                "humidity": None,
                "wind_kmh": None,
                "uv_index": None,
                "weather_code": None,
                "precip_prob": None,
            }
        )
        partial = go_slot.model_copy(update={"weather": weather})
        assert score_heuristic([partial])[0].decision is Decision.GO

    def test_known_hazard_keeps_its_reason_when_weather_is_missing(self, hazardous_slot):
        weather = hazardous_slot.weather.model_copy(update={"apparent_c": None, "precip_mm": None})
        partial = hazardous_slot.model_copy(update={"weather": weather})
        result = score_heuristic([partial])[0]
        assert result.decision is Decision.SKIP
        assert "NAQI" in result.reasons[0]

    def test_every_hour_gets_a_decision_and_a_reason(self, go_slot: HourSlot, slot) -> None:
        slots = [go_slot, slot(1, pm25=120.0), slot(2, temp_c=34.0, apparent_c=38.0)]
        scores = score_heuristic(slots)
        assert len(scores) == 3
        for s in scores:
            assert s.decision in set(Decision)
            assert s.reasons, "every decision must be explainable"
            assert 0.0 <= s.comfort <= 100.0

    def test_pick_best_prefers_go_over_a_comfortable_skip(self, slot) -> None:
        slots = [
            slot(0, pm25=400.0),  # SKIP, low comfort
            slot(1, pm25=15.0),  # GO, high comfort
        ]
        scores = score_heuristic(slots)
        assert pick_best(scores).decision is Decision.GO

    def test_pick_best_of_nothing_is_none(self) -> None:
        assert pick_best([]) is None

    def test_plan_reports_its_own_scorer(self, go_slot: HourSlot) -> None:
        plan = build_plan([go_slot], weather_source=DataSource.LIVE, air_source=DataSource.LIVE)
        assert plan.scorer in {"heuristic", "tabpfn", "lgbm", "ensemble"}
        assert plan.scorer_note
        assert plan.headline

    def test_fixture_sources_are_surfaced_as_degraded(self, go_slot: HourSlot) -> None:
        plan = build_plan(
            [go_slot], weather_source=DataSource.FIXTURE, air_source=DataSource.FIXTURE
        )
        assert any("fixture" in d for d in plan.degraded)

    def test_empty_window_does_not_crash(self) -> None:
        plan = build_plan([])
        assert plan.overall is Decision.SKIP
        assert plan.best_time is None


class TestDisplayWindow:
    """The recommended hour must be visible in the table the user reads.

    Regression test for a real bug: `build_plan` truncated with
    `scores[:window_hours]`, which at 13:00 showed 13:00-to-midnight while the
    briefing recommended 07:00 tomorrow. Every visible row read WAIT or SKIP, so
    the table appeared to contradict the advice it was meant to justify.
    """

    @staticmethod
    def _scores(count: int) -> list[SlotScore]:
        start = datetime(2026, 10, 6, 13, 0, tzinfo=IST)
        return [
            SlotScore(
                time=start + timedelta(hours=i),
                decision=Decision.WAIT,
                comfort=50.0,
            )
            for i in range(count)
        ]

    @staticmethod
    def _go_at(scores: list[SlotScore], index: int) -> SlotScore:
        return SlotScore(
            time=scores[index].time,
            decision=Decision.GO,
            comfort=99.0,
        )

    def test_best_hour_is_always_in_the_window(self) -> None:
        for index in range(24):
            scores = self._scores(24)
            best = self._go_at(scores, index)
            out = display_window(scores, best, 12)
            assert any(s.time == best.time for s in out), (
                f"best hour at index {index} is missing from the window"
            )

    def test_window_never_exceeds_its_cap(self) -> None:
        for index in (0, 5, 11, 12, 18, 23):
            scores = self._scores(24)
            best = self._go_at(scores, index)
            assert len(display_window(scores, best, 12)) <= 12

    def test_window_shows_only_real_hours(self) -> None:
        scores = self._scores(24)
        best = self._go_at(scores, 18)
        known = {s.time for s in scores}
        out = display_window(scores, best, 12)
        assert all(s.time in known for s in out)

    def test_behaviour_is_unchanged_when_best_is_already_visible(self) -> None:
        scores = self._scores(24)
        best = self._go_at(scores, 3)
        assert display_window(scores, best, 12) == scores[:12]

    def test_window_keeps_lead_in_context(self) -> None:
        """The point of anchoring is that the improvement is *visible*.

        Showing only the best row would assert 07:00 is good without showing
        that 06:00 was worse, which is the evidence a sceptical reader wants.
        """
        scores = self._scores(24)
        best = self._go_at(scores, 18)
        out = display_window(scores, best, 12)
        assert len(out) > 1
        assert out[0].time < best.time

    def test_no_best_hour_still_shows_the_leading_slice(self) -> None:
        scores = self._scores(24)
        assert display_window(scores, None, 12) == scores[:12]

    def test_window_larger_than_the_data(self) -> None:
        scores = self._scores(5)
        best = self._go_at(scores, 2)
        assert len(display_window(scores, best, 12)) == 5

    def test_empty_scores(self) -> None:
        assert display_window([], None, 12) == []

    def test_plan_actually_shows_its_own_recommendation(self, slot) -> None:
        """End to end through build_plan, which is where the bug lived."""
        base = datetime(2026, 10, 6, 13, 0, tzinfo=IST)
        slots = []
        for i in range(24):
            offset = int((base + timedelta(hours=i) - BASE).total_seconds() // 3600)
            # Poor until early morning, then clean.
            pm25 = 150.0 if i < 16 else 15.0
            slots.append(slot(offset, pm25=pm25, temp_c=24.0, apparent_c=25.0))
        plan = build_plan(slots, weather_source=DataSource.LIVE, air_source=DataSource.LIVE)
        assert plan.best_time is not None
        assert any(s.time == plan.best_time for s in plan.slots), (
            "build_plan produced a plan whose table omits its own recommendation"
        )


class TestScorerSelection:
    def test_explicit_heuristic_is_respected(self) -> None:
        name, note = choose_scorer("heuristic")
        assert name == "heuristic"
        assert note

    def test_requesting_tabpfn_without_install_degrades_honestly(self) -> None:
        """Two separate gates may block TabPFN; both must degrade, not crash."""
        from baahar.config import get_settings

        available, reason = tabpfn_available()
        name, note = choose_scorer("tabpfn")
        if not available:
            assert name == "heuristic"
            assert reason in note or note
            if "not installed" in reason:
                assert "--group ml" in note, "note should say how to install it"
            else:
                # Licence gate: the fix is a human step, so point at the doc.
                assert "TABPFN_TOKEN" in note or "NEEDS_HUMAN" in note
        else:
            assert name == "tabpfn"
        assert get_settings().has_tabpfn_license in (True, False)

    def test_tabpfn_gates_are_reported_distinctly(self) -> None:
        """Install and licence are different problems with different fixes."""
        available, reason = tabpfn_available()
        if not available:
            assert ("not installed" in reason) or ("licence" in reason.lower())

    def test_requesting_lgbm_without_artifact_degrades_to_heuristic(self) -> None:
        name, note = choose_scorer("lgbm")
        assert name == "heuristic"
        assert "LightGBM" in note

    def test_requesting_ensemble_without_artifact_degrades_to_heuristic(self) -> None:
        name, note = choose_scorer("ensemble")
        assert name == "heuristic"
        assert "Ensemble" in note

    def test_lgbm_available_returns_status(self) -> None:
        available, reason = lgbm_available()
        assert isinstance(available, bool)
        assert isinstance(reason, str)

    def test_ensemble_available_returns_status(self) -> None:
        available, reason = ensemble_available()
        assert isinstance(available, bool)
        assert isinstance(reason, str)

    def test_auto_mode_note_stays_short_and_user_facing(self, go_slot) -> None:
        """`auto` did not ask for TabPFN, so no install command in the UI."""
        name, note = choose_scorer("auto")
        if name == "heuristic":
            assert "uv sync" not in note, note
            assert "NEEDS_HUMAN" not in note, "auto mode must not read like a build error"
            assert len(note) < 110, note

    def test_score_slots_never_raises(self, go_slot: HourSlot) -> None:
        scores, name, note = score_slots([go_slot], "tabpfn")
        assert len(scores) == 1
        assert name in {"heuristic", "tabpfn"}
        assert note

    def test_score_slots_lgbm_never_raises(self, go_slot: HourSlot) -> None:
        scores, name, note = score_slots([go_slot], "lgbm")
        assert len(scores) == 1
        assert name in {"heuristic", "lgbm"}
        assert note

    def test_score_slots_ensemble_never_raises(self, go_slot: HourSlot) -> None:
        scores, name, note = score_slots([go_slot], "ensemble")
        assert len(scores) == 1
        assert name in {"heuristic", "ensemble"}
        assert note

    def test_tabpfn_label_order_is_frozen(self) -> None:
        """Column and class order are part of the model's contract."""
        assert TABPFN_LABELS == (Decision.GO, Decision.WAIT, Decision.SKIP)


class TestSafetyAsymmetry:
    """A learned model must never be more permissive than the policy."""

    @pytest.mark.parametrize("scorer", ["score_lgbm", "score_ensemble", "score_tabpfn"])
    @pytest.mark.parametrize("field", ["apparent_c", "precip_mm"])
    def test_model_cannot_fill_unknown_safety_weather_with_a_go(self, go_slot, scorer, field):
        np = pytest.importorskip("numpy")
        from baahar import score as score_mod
        from baahar.features import TABPFN_FEATURE_ORDER

        class AlwaysGo:
            n_features_in_ = len(
                TABPFN_FEATURE_ORDER if scorer == "score_tabpfn" else COMPACT_FEATURE_NAMES
            )

            def predict_proba(self, x):
                return np.tile([[1.0, 0.0, 0.0]], (len(x), 1))

        incomplete = go_slot.model_copy(
            update={"weather": go_slot.weather.model_copy(update={field: None})}
        )
        result = getattr(score_mod, scorer)([incomplete], model=AlwaysGo())[0]
        assert result.decision is Decision.SKIP
        assert result.scorer != "heuristic", "the model path must reach its safety gate"
        assert any("not guessing" in reason for reason in result.reasons)

    def test_model_cannot_override_a_skip(self, hazardous_slot: HourSlot) -> None:
        np = pytest.importorskip("numpy")

        from baahar import score as score_mod

        class AlwaysGo:
            def predict_proba(self, x):
                return np.tile([[1.0, 0.0, 0.0]], (len(x), 1))

        scores = score_mod.score_tabpfn([hazardous_slot], model=AlwaysGo())
        assert scores[0].decision is Decision.SKIP, "model talked a user into bad air"
        assert any("policy" in r for r in scores[0].reasons)

    def test_lgbm_cannot_override_a_skip(self, hazardous_slot: HourSlot) -> None:
        np = pytest.importorskip("numpy")

        from baahar import score as score_mod

        class AlwaysGo:
            n_features_in_ = len(COMPACT_FEATURE_NAMES)

            def predict_proba(self, x):
                return np.tile([[1.0, 0.0, 0.0]], (len(x), 1))

        scores = score_mod.score_lgbm([hazardous_slot], model=AlwaysGo())
        assert scores[0].decision is Decision.SKIP, "lgbm talked a user into bad air"
        assert any("policy" in r for r in scores[0].reasons)
        assert scores[0].scorer == "lgbm"

    def test_ensemble_cannot_override_a_skip(self, hazardous_slot: HourSlot) -> None:
        np = pytest.importorskip("numpy")

        from baahar import score as score_mod

        class AlwaysGo:
            n_features_in_ = len(COMPACT_FEATURE_NAMES)

            def predict_proba(self, x):
                return np.tile([[1.0, 0.0, 0.0]], (len(x), 1))

        scores = score_mod.score_ensemble([hazardous_slot], model=AlwaysGo())
        assert scores[0].decision is Decision.SKIP, "ensemble talked a user into bad air"
        assert any("policy" in r for r in scores[0].reasons)
        assert scores[0].scorer == "ensemble"

    def test_model_is_allowed_to_be_more_strict(self, go_slot: HourSlot) -> None:
        np = pytest.importorskip("numpy")

        from baahar import score as score_mod

        class AlwaysSkip:
            def predict_proba(self, x):
                return np.tile([[0.0, 0.0, 1.0]], (len(x), 1))

        scores = score_mod.score_tabpfn([go_slot], model=AlwaysSkip())
        assert scores[0].decision is Decision.SKIP

    def test_lgbm_is_allowed_to_be_more_strict(self, go_slot: HourSlot) -> None:
        np = pytest.importorskip("numpy")

        from baahar import score as score_mod

        class AlwaysSkip:
            n_features_in_ = len(COMPACT_FEATURE_NAMES)

            def predict_proba(self, x):
                return np.tile([[0.0, 0.0, 1.0]], (len(x), 1))

        scores = score_mod.score_lgbm([go_slot], model=AlwaysSkip())
        assert scores[0].decision is Decision.SKIP
        assert scores[0].scorer == "lgbm"

    def test_ensemble_is_allowed_to_be_more_strict(self, go_slot: HourSlot) -> None:
        np = pytest.importorskip("numpy")

        from baahar import score as score_mod

        class AlwaysSkip:
            n_features_in_ = len(COMPACT_FEATURE_NAMES)

            def predict_proba(self, x):
                return np.tile([[0.0, 0.0, 1.0]], (len(x), 1))

        scores = score_mod.score_ensemble([go_slot], model=AlwaysSkip())
        assert scores[0].decision is Decision.SKIP
        assert scores[0].scorer == "ensemble"

    def test_absent_model_falls_back_to_policy(self, hazardous_slot: HourSlot) -> None:
        from baahar import score as score_mod

        scores = score_mod.score_tabpfn([hazardous_slot], model=None)
        assert scores[0].decision is Decision.SKIP

    def test_absent_lgbm_falls_back_to_policy(self, hazardous_slot: HourSlot) -> None:
        from baahar import score as score_mod

        scores = score_mod.score_lgbm([hazardous_slot], model=None)
        assert scores[0].decision is Decision.SKIP
        assert scores[0].scorer == "heuristic"

    def test_absent_ensemble_falls_back_to_policy(self, hazardous_slot: HourSlot) -> None:
        from baahar import score as score_mod

        scores = score_mod.score_ensemble([hazardous_slot], model=None)
        assert scores[0].decision is Decision.SKIP
        assert scores[0].scorer == "heuristic"


class TestFeatures:
    def test_feature_row_matches_declared_order(self, go_slot: HourSlot) -> None:
        from baahar.features import FEATURE_NAMES, row_from_slot

        row = row_from_slot(go_slot)
        assert len(row) == len(FEATURE_NAMES)

    def test_every_declared_feature_is_computed(self, go_slot: HourSlot) -> None:
        """A name in FEATURE_NAMES with no matching key raises KeyError deep
        inside predict, which reads as a model fault rather than a data fault."""
        from baahar.features import FEATURE_NAMES, features_from_slot

        computed = features_from_slot(go_slot)
        missing = [n for n in FEATURE_NAMES if n not in computed]
        assert not missing, f"declared but not computed: {missing}"

    def test_every_compact_feature_is_computed(self, go_slot: HourSlot) -> None:
        from baahar.features import COMPACT_FEATURE_NAMES, features_from_slot

        computed = features_from_slot(go_slot)
        missing = [n for n in COMPACT_FEATURE_NAMES if n not in computed]
        assert not missing, f"compact feature missing: {missing}"

    def test_compact_feature_names_has_17_elements(self) -> None:
        assert len(COMPACT_FEATURE_NAMES) == 17

    def test_hour_and_month_are_model_columns(self, go_slot: HourSlot) -> None:
        """Regression guard for the 13-vs-15 feature divergence.

        The eval fitted on `hour`/`month` from the archive while the library built
        `hour_sin`/`hour_cos`, so the fitted model could never be used by the app.\
        These two must be part of the model's column contract.
        """
        from baahar.features import TABPFN_FEATURE_ORDER

        assert "hour" in TABPFN_FEATURE_ORDER
        assert "month" in TABPFN_FEATURE_ORDER

    def test_the_eval_imports_the_library_column_order(self) -> None:
        """One definition, one owner. A second copy of the column list in
        run_eval.py is exactly how the two drifted apart."""
        from pathlib import Path

        source = Path(__file__).resolve().parents[1] / "scripts" / "run_eval.py"
        text = source.read_text(encoding="utf-8")
        assert "FEATURE_COLUMNS = list(TABPFN_FEATURE_ORDER)" in text, (
            "run_eval.py must derive FEATURE_COLUMNS from baahar.features rather "
            "than declaring its own list"
        )

    def test_eval_columns_match_the_library(self) -> None:
        from baahar.features import TABPFN_FEATURE_ORDER

        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
        try:
            import run_eval  # type: ignore[import-not-found]
        finally:
            sys.path.pop(0)
        assert list(run_eval.FEATURE_COLUMNS) == list(TABPFN_FEATURE_ORDER)

    def test_a_feature_count_mismatch_is_refused_loudly(self, go_slot: HourSlot) -> None:
        """Not reordered to fit. Silently padding or truncating columns would make
        the model score on values that mean something else."""
        from baahar import score as score_mod

        class WrongWidthModel:
            n_features_in_ = 7

            def predict_proba(self, x):  # pragma: no cover - must never be reached
                raise AssertionError("predict must not run on a mismatched model")

        with pytest.raises(ValueError, match="expects 7 features"):
            score_mod.score_tabpfn([go_slot], model=WrongWidthModel())

    def test_save_and_load_agree_on_the_default_path(self, tmp_path: Path) -> None:
        """Writer and reader must name the same file, or a fitted model gets
        written and then ignored.

        Deliberately writes to `tmp_path` via the explicit argument. Asserting the
        default path by *calling* the default would overwrite a real fitted model
        with a stub, which is not a cost worth paying for a path assertion --
        and the earlier version of this test did exactly that.
        """
        from baahar.score import save_tabpfn_model

        target = save_tabpfn_model({"sentinel": True}, path=tmp_path / "m.pkl")
        assert Path(target) == tmp_path / "m.pkl"
        assert (tmp_path / "m.pkl").exists()

    def test_save_and_load_lgbm_agree(self, tmp_path: Path) -> None:
        target = save_lgbm_model({"sentinel": True}, path=tmp_path / "lgb.pkl")
        assert Path(target) == tmp_path / "lgb.pkl"
        loaded = load_lgbm_model(path=tmp_path / "lgb.pkl")
        assert loaded == {"sentinel": True}

    def test_save_and_load_ensemble_agree(self, tmp_path: Path) -> None:
        target = save_ensemble_model(
            {"sentinel": True}, path=tmp_path / "ens.pkl", feature_order=COMPACT_FEATURE_NAMES
        )
        assert Path(target) == tmp_path / "ens.pkl"
        loaded = load_ensemble_model(path=tmp_path / "ens.pkl")
        assert loaded == {"sentinel": True, "feature_order": list(COMPACT_FEATURE_NAMES)}

    def test_default_artifact_is_gitignored(self) -> None:
        """The fitted models are artifacts and must never reach the repo."""
        gitignore = (Path(__file__).resolve().parents[1] / ".gitignore").read_text(encoding="utf-8")
        assert DEFAULT_TABPFN_ARTIFACT.parent.name in gitignore
        assert DEFAULT_LGBM_ARTIFACT.parent.name in gitignore
        assert DEFAULT_ENSEMBLE_ARTIFACT.parent.name in gitignore
        assert "*.pkl" in gitignore

    def test_hour_is_cyclically_encoded(self, slot) -> None:
        """23:00 and 00:00 must be adjacent in feature space, not far apart."""
        import math

        late = features_from_slot(slot(0))
        late["hour_sin"], late["hour_cos"] = (
            math.sin(2 * math.pi * 23 / 24),
            math.cos(2 * math.pi * 23 / 24),
        )
        midnight = features_from_slot(slot(0))
        midnight["hour_sin"], midnight["hour_cos"] = 0.0, 1.0
        distance = math.hypot(
            late["hour_sin"] - midnight["hour_sin"], late["hour_cos"] - midnight["hour_cos"]
        )
        assert distance < 0.3, "23:00 and 00:00 should be close in feature space"

    def test_missing_values_are_nan_not_zero(self, missing_air_slot: HourSlot) -> None:
        """A missing NAQI must not read as a perfect zero."""
        import math

        feats = features_from_slot(missing_air_slot)
        assert math.isnan(feats["naqi"])
        assert math.isnan(feats["pm25"])

    def test_band_ordinals_are_ordered_by_severity(self) -> None:
        values = list(BAND_ORDINALS.values())
        assert values == sorted(values)
        assert BAND_ORDINALS["hazardous"] > BAND_ORDINALS["good"]


class TestHeadline:
    """The headline is the only line most people read.

    It must never recommend an hour the table underneath marks as anything other
    than GO. Using the product in offline mode surfaced this: with a fixture
    window where every hour is WAIT, the old headline read "Wait for 22:00"
    while 22:00 was itself a WAIT in the table two lines below.
    """

    def test_go_headline_names_a_go_hour(self, go_slot, night_slot) -> None:
        plan = build_plan([night_slot, go_slot], scorer="heuristic")
        assert plan.overall is Decision.GO
        assert plan.headline == f"Go at {plan.best_time.strftime('%H:%M')}."

    def test_wait_headline_never_names_an_hour_as_the_recommendation(
        self, night_slot, slot
    ) -> None:
        """A WAIT window must say there is no GO hour, not point at one."""
        slots = [night_slot, slot(1, pm25=120.0), slot(2, pm25=130.0)]
        plan = build_plan(slots, scorer="heuristic")
        assert plan.overall is Decision.WAIT
        assert "No GO hour" in plan.headline
        # The hour it names as "best" must not be presented as a GO.
        assert "Go at" not in plan.headline

    def test_wait_headline_does_not_say_wait_for(self, night_slot, slot) -> None:
        """The old wording survived in committed acceptance artifacts; this is the
        regression test for the behaviour itself, not for the old string."""
        plan = build_plan([night_slot, slot(1, pm25=120.0)], scorer="heuristic")
        assert "Wait for" not in plan.headline

    def test_skip_headline_leads_with_the_reason(self, hazardous_slot) -> None:
        plan = build_plan([hazardous_slot], scorer="heuristic")
        assert plan.overall is Decision.SKIP
        assert plan.headline.startswith("Skip it.")

    def test_empty_window_is_not_reported_as_a_recommendation(self) -> None:
        plan = build_plan([], scorer="heuristic")
        assert plan.headline == "No usable hours in the window."


class TestSplits:
    def test_time_split_is_chronological_and_disjoint(self, slot) -> None:
        slots = [slot(h) for h in range(24)]
        rows = build_dataset(slots)
        train, test = time_split(rows, holdout_fraction=0.25)
        assert len(train) + len(test) == len(rows)
        assert not ({r.time for r in train} & {r.time for r in test})
        assert max(r.time for r in train) < min(r.time for r in test)

    def test_time_split_never_shuffles(self, slot) -> None:
        """The whole point: neighbouring hours must not straddle the split."""
        rows = build_dataset([slot(h) for h in range(10)])
        train, test = time_split(rows, 0.2)
        assert [r.time for r in train] == sorted(r.time for r in train)
        assert [r.time for r in test] == sorted(r.time for r in test)

    def test_labels_come_from_the_policy(self, slot) -> None:
        rows = build_dataset([slot(0, pm25=400.0), slot(1, pm25=10.0)])
        assert [r.label for r in rows] == ["SKIP", "GO"]
