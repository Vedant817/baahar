"""Offline integrity checks using actual recorded BTM pollutant values."""

import importlib.util
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "station_audit", ROOT / "scripts/audit_station_support_modal.py"
)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)
FIXTURE = json.loads(
    (ROOT / "data/samples/station_source_probe_v1.json").read_text(encoding="utf-8")
)
RECORDS = FIXTURE["responses"][2]["payload"]["data"]


def test_recorded_units_and_co_conversion():
    for record in RECORDS:
        parameter, unit, value = record["parameter_name"], record["unit"], record["value"]
        normalized = AUDIT.normalize_value(parameter, unit, value)
        assert normalized == value * (1000 if parameter == "CO" else 1)
    with pytest.raises(ValueError, match="unit"):
        AUDIT.normalize_value("CO", "µg/m³", 1)
    with pytest.raises(ValueError, match="unit"):
        AUDIT.normalize_value("Ozone", "�g/m�", 1)
    assert AUDIT.normalize_value("Ozone", "µg/m³", -1) is None
    assert AUDIT.normalize_value("Ozone", "µg/m³", float("nan")) is None


def recorded_sequence():
    # Timing scaffolding tests context integrity; concentrations are actual fixture values.
    values = {}
    for record in RECORDS:
        values.setdefault(AUDIT.PARAMETERS[record["parameter_name"]], []).append(
            AUDIT.normalize_value(record["parameter_name"], record["unit"], record["value"])
        )
    start = datetime(2024, 4, 1)
    indexed = {
        (start + timedelta(hours=h), gas): observed[h % len(observed)]
        for gas, observed in values.items()
        for h in range(30)
    }
    return start, indexed


def test_exact_complete_thirty_hour_context_required():
    start, indexed = recorded_sequence()
    origin, end = start + timedelta(hours=23), start + timedelta(hours=30)
    assert AUDIT.eligible_window(origin, start, end, indexed) is None
    key = (origin + timedelta(hours=6), "o3")
    del indexed[key]
    assert AUDIT.eligible_window(origin, start, end, indexed) == "incomplete_or_invalid_sequence"
    indexed[key] = None
    assert AUDIT.eligible_window(origin, start, end, indexed) == "incomplete_or_invalid_sequence"


def test_phase_boundaries_cannot_borrow_external_rows():
    start, indexed = recorded_sequence()
    end = start + timedelta(hours=30)
    assert (
        AUDIT.eligible_window(start + timedelta(hours=22), start, end, indexed) == "phase_boundary"
    )
    assert (
        AUDIT.eligible_window(start + timedelta(hours=24), start, end, indexed) == "phase_boundary"
    )
