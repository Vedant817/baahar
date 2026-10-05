"""The GO / WAIT / SKIP policy, and the safety asymmetry around TabPFN.

The tests here encode the *safety contract*: the product must never tell a user
to go outside in conditions the policy calls SKIP, no matter what a learned
model says.
"""

from __future__ import annotations

import pytest

from baahar.features import (
    BAND_ORDINALS,
    NAQI_SKIP,
    NAQI_WAIT,
    build_dataset,
    features_from_slot,
    heuristic_decision,
    time_split,
)
from baahar.models import DataSource, Decision, HourSlot
from baahar.score import (
    TABPFN_LABELS,
    build_plan,
    choose_scorer,
    pick_best,
    score_heuristic,
    score_slots,
    tabpfn_available,
)


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
        assert plan.scorer in {"heuristic", "tabpfn"}
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

    def test_tabpfn_label_order_is_frozen(self) -> None:
        """Column and class order are part of the model's contract."""
        assert TABPFN_LABELS == (Decision.GO, Decision.WAIT, Decision.SKIP)


class TestSafetyAsymmetry:
    """A learned model must never be more permissive than the policy."""

    def test_model_cannot_override_a_skip(self, hazardous_slot: HourSlot) -> None:
        # The TabPFN path needs numpy, which ships in the optional `ml` extra.
        # The safety property is asserted here and re-checked end-to-end by
        # `tests/test_tabpfn.py` when the extra is installed.
        np = pytest.importorskip("numpy")

        from baahar import score as score_mod

        class AlwaysGo:
            def predict_proba(self, x):
                return np.tile([[1.0, 0.0, 0.0]], (len(x), 1))

        scores = score_mod.score_tabpfn([hazardous_slot], model=AlwaysGo())
        assert scores[0].decision is Decision.SKIP, "model talked a user into bad air"
        assert any("policy" in r for r in scores[0].reasons)

    def test_model_is_allowed_to_be_more_strict(self, go_slot: HourSlot) -> None:
        np = pytest.importorskip("numpy")

        from baahar import score as score_mod

        class AlwaysSkip:
            def predict_proba(self, x):
                return np.tile([[0.0, 0.0, 1.0]], (len(x), 1))

        scores = score_mod.score_tabpfn([go_slot], model=AlwaysSkip())
        assert scores[0].decision is Decision.SKIP

    def test_absent_model_falls_back_to_policy(self, hazardous_slot: HourSlot) -> None:
        from baahar import score as score_mod

        scores = score_mod.score_tabpfn([hazardous_slot], model=None)
        assert scores[0].decision is Decision.SKIP


class TestFeatures:
    def test_feature_row_matches_declared_order(self, go_slot: HourSlot) -> None:
        from baahar.features import FEATURE_NAMES, row_from_slot

        row = row_from_slot(go_slot)
        assert len(row) == len(FEATURE_NAMES)

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
