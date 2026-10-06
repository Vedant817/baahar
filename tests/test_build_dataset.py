"""The eval dataset must be fitted on the same air-quality number the app serves.

`scripts/run_eval.py` fits TabPFN on the `naqi` column of
`data/eval/gono_rows.jsonl`, and `src/baahar/score.py` scores with
`baahar.features.features_from_slot`, which emits the **effective**
(conservative) NAQI under that same key. This builder used to write the
*instantaneous* reading into that column, so the published accuracy described a
model fitted on optimistic air while the product acted on the conservative one:
the same class of bug as eval/RESULTS.md C.14, one layer up, and invisible from
the eval's own side.

These tests drive `build_dataset` with a synthetic archive -- `fetch_series` is
stubbed, so there is no network, no cache and no committed fixture -- and check
what comes out the other end.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import build_dataset  # noqa: E402

from baahar.features import features_from_slot  # noqa: E402
from baahar.models import HourlyAir, HourlyWeather, HourSlot  # noqa: E402
from baahar.naqi import (  # noqa: E402
    band_for_index,
    compute_naqi,
    compute_naqi_trailing,
    conservative_naqi,
)

START = datetime(2026, 10, 1, 0, 0)


def diurnal_pm25(hours: int, peak: float = 120.0, trough: float = 35.0) -> list[float]:
    """Overnight peak, afternoon trough. The shape that makes this matter."""
    out = []
    for i in range(hours):
        if i <= 14:
            out.append(round(peak + (trough - peak) * (i / 14.0), 3))
        else:
            out.append(round(trough + (peak - trough) * ((i - 14) / 10.0), 3))
    return out


def curve(hours: int) -> list[dict[str, float]]:
    """The Baahar-keyed readings `air.parse_air` would build from the archive.

    The quiet pollutants are constant and never dominate, so the assertion below
    is about the PM curve and nothing else.
    """
    pm = diurnal_pm25(hours)
    return [
        {
            "pm25": v,
            "pm10": round(v * 2.2, 3),
            "no2": 20.0,
            "o3": 40.0,
            "so2": 5.0,
            "co": 300.0,
        }
        for v in pm
    ]


def _aq_payload(hours: int) -> dict:
    pm = diurnal_pm25(hours)
    return {
        "hourly": {
            "time": [(START + timedelta(hours=i)).isoformat() for i in range(hours)],
            "pm2_5": pm,
            "pm10": [round(v * 2.2, 3) for v in pm],
            "nitrogen_dioxide": [20.0] * hours,
            "ozone": [40.0] * hours,
            "sulphur_dioxide": [5.0] * hours,
            "carbon_monoxide": [300.0] * hours,
        }
    }


def _wx_payload(hours: int) -> dict:
    return {
        "hourly": {
            "time": [(START + timedelta(hours=i)).isoformat() for i in range(hours)],
            "temperature_2m": [24.0] * hours,
            "apparent_temperature": [25.0] * hours,
            "precipitation": [0.0] * hours,
            "precipitation_probability": [10.0] * hours,
            "relative_humidity_2m": [60.0] * hours,
            "wind_speed_10m": [8.0] * hours,
            "uv_index": [3.0] * hours,
            "weather_code": [0] * hours,
        }
    }


@pytest.fixture
def archive(monkeypatch):
    """Serve `build_dataset.fetch_series` a synthetic archive, never the network."""
    payloads: dict[str, dict] = {"aq": _aq_payload(40), "wx": _wx_payload(40)}

    def fake_fetch(url, params, cache_name, *, force):  # noqa: ANN001, ARG001
        return payloads["aq"] if "air-quality" in url else payloads["wx"]

    monkeypatch.setattr(build_dataset, "fetch_series", fake_fetch)

    def build(hours: int = 40):
        payloads["aq"] = _aq_payload(hours)
        payloads["wx"] = _wx_payload(hours)
        return build_dataset.build_rows("2026-10-01", "2026-10-01", force=False)

    return build


class TestNaqiFeatureColumn:
    def test_the_feature_is_the_effective_reading(self, archive) -> None:
        """The column the model is fitted on is the one the app serves."""
        rows = archive()
        readings = curve(40)
        assert rows
        raised = 0
        for row in rows:
            i = int((datetime.fromisoformat(row.time) - START).total_seconds() // 3600)
            instant = compute_naqi(readings[i])
            trailing = compute_naqi_trailing(readings[: i + 1])
            effective = conservative_naqi(instant, trailing)
            assert row.naqi == pytest.approx(effective.index, abs=0.005)
            assert row.naqi_instant == pytest.approx(instant.index, abs=0.005)
            raised += row.naqi > row.naqi_instant
        # Without this the test could pass on a dataset where the trailing mean
        # never disagrees, which is the case where the bug is invisible.
        assert raised > 0, "the synthetic day must actually exercise the trailing mean"

    def test_the_instantaneous_value_is_kept_under_its_own_name(self, archive) -> None:
        """Both readings are recorded, so the difference is auditable."""
        row = archive()[14]
        assert row.naqi_instant < row.naqi
        assert row.naqi_trailing == pytest.approx(row.naqi, abs=0.005)
        assert row.naqi_trailing_hours == 15

    def test_the_afternoon_dip_is_recorded_as_the_day_it_belongs_to(self, archive) -> None:
        """The headline case: 14:00 reads Satisfactory alone, Moderate on its day.

        A dataset built on the instantaneous reading would file this hour as
        Satisfactory, and a model fitted on that column would learn to send
        people out on the hours CPCB calls Moderate.
        """
        row = archive()[14]
        assert band_for_index(row.naqi_instant).value == "satisfactory"
        assert row.band == "moderate"
        assert row.band == band_for_index(row.naqi).value

    def test_the_feature_never_falls_below_the_instantaneous_reading(self, archive) -> None:
        for row in archive():
            assert row.naqi >= row.naqi_instant

    def test_the_library_feature_builder_reproduces_the_column(self, archive) -> None:
        """Train/serve skew, stated as one assertion.

        The row's own recorded readings go back through
        `features_from_slot` -- the exact function `score.py` scores with -- and
        the `naqi` column has to come back out. If the builder ever reverts to
        the instantaneous reading, this is the line that fails.
        """
        for index in (7, 14, 20, 30):
            row = archive()[index]
            trailing = None if math.isnan(row.naqi_trailing) else row.naqi_trailing
            slot = HourSlot(
                weather=HourlyWeather(
                    time=datetime.fromisoformat(row.time),
                    temp_c=row.temp_c,
                    apparent_c=row.apparent_c,
                    precip_mm=row.precip_mm,
                    precip_prob=row.precip_prob,
                    humidity=row.humidity,
                    wind_kmh=row.wind_kmh,
                    uv_index=row.uv_index,
                    is_day=row.is_day,
                ),
                air=HourlyAir(
                    time=datetime.fromisoformat(row.time),
                    pm25=row.pm25,
                    pm10=row.pm10,
                    naqi=row.naqi_instant,
                    naqi_trailing=trailing,
                ),
            )
            assert features_from_slot(slot)["naqi"] == pytest.approx(row.naqi, abs=0.01)


class TestLabelSemanticsAreUnchanged:
    """A1 changes the feature. It must not quietly redefine the label."""

    def test_the_target_is_still_the_instantaneous_band_at_t_plus_6(self, archive) -> None:
        rows = archive()
        readings = curve(40)
        for row in rows:
            i = int((datetime.fromisoformat(row.time) - START).total_seconds() // 3600)
            future = compute_naqi(readings[i + build_dataset.HORIZON_H])
            assert row.target_band == future.band.value
            assert row.target_naqi == pytest.approx(future.index, abs=0.005)

    def test_the_decision_is_still_the_policy_on_the_target_band(self, archive) -> None:
        for row in archive():
            assert row.decision == build_dataset.apply_band_policy(
                row.target_band, row.precip_mm, row.precip_prob, row.apparent_c
            )

    def test_a_feature_and_a_target_do_not_collide(self, archive) -> None:
        """A row whose effective reading already matches its own label would mean
        the label leaked backwards into the feature."""
        build_dataset.assert_no_leakage(archive())
        build_dataset.assert_feature_is_effective(archive())


class TestDatasetMetadata:
    def test_the_raw_metadata_says_the_feature_column_is_effective(
        self, archive, tmp_path, monkeypatch
    ) -> None:
        """The artifact itself has to say it, not just the source code."""
        monkeypatch.setattr(build_dataset, "OUT_DIR", tmp_path)
        assert build_dataset.main(["--start", "2026-10-01", "--end", "2026-10-01"]) == 0

        meta = json.loads((tmp_path / "gono_dataset.json").read_text(encoding="utf-8"))
        semantics = meta["feature_semantics"]
        assert "EFFECTIVE" in semantics["naqi"]
        assert "naqi_instant" in semantics["naqi"]
        assert semantics["rows_where_effective_exceeds_instantaneous"] > 0
        assert "instantaneous reading" in semantics["target"]

        written = [
            json.loads(line)
            for line in (tmp_path / "gono_rows.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert written
        assert any(row["naqi"] > row["naqi_instant"] for row in written)
        assert written[0]["naqi"] >= written[0]["naqi_instant"]

    def test_the_eval_artifact_carries_the_same_note(self) -> None:
        """`run_eval.py` publishes the note too, so the raw artifact is honest.

        An eval artifact that does not say what its feature column means is how
        the two halves of this repository came to disagree about `naqi` while
        each was correct about its own code.
        """
        source = (Path(__file__).resolve().parents[1] / "scripts" / "run_eval.py").read_text(
            encoding="utf-8"
        )
        assert "NAQI_FEATURE_NOTE" in source
        assert '"feature_semantics"' in source


class TestOrderingGuard:
    def test_a_shuffled_archive_is_refused(self, monkeypatch) -> None:
        """The dataset cannot average across hours that are not in sequence."""
        payload = _aq_payload(40)
        payload["hourly"]["time"] = list(reversed(payload["hourly"]["time"]))

        def fake_fetch(url, params, cache_name, *, force):  # noqa: ANN001, ARG001
            return payload if "air-quality" in url else _wx_payload(40)

        monkeypatch.setattr(build_dataset, "fetch_series", fake_fetch)
        with pytest.raises(ValueError, match="ascending"):
            build_dataset.build_rows("2026-10-01", "2026-10-01", force=False)
