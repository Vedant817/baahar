"""Indian NAQI from raw pollutant concentrations.

    Baahar reports **Indian NAQI**, computed the way India's Central Pollution
    Control Board (CPCB) defines it: a per-pollutant *sub-index* is derived from
    the measured concentration using the CPCB health breakpoints, and the
    overall NAQI is the **worst** sub-index.

    It is emphatically *not* the US EPA AQI. The two scales use different
    breakpoints, different averaging periods, and different band names. A US
    `us_aqi` value from Open-Meteo is a different quantity, and Baahar never
    presents one as the other.

Methodology and source
----------------------
CPCB launched the National Air Quality Index on 17 September 2014 under the
Swachh Bharat Abhiyan, covering eight pollutants (PM10, PM2.5, NO2, SO2, CO,
O3, NH3, Pb) with six categories: Good, Satisfactory, Moderate, Poor, Severe,
Hazardous. Breakpoint values below are transcribed from that published table
(cross-checked against the Wikipedia "Air quality index" article, section
*India*, which reproduces the CPCB table including the per-pollutant
breakpoints and the statement that "the worst sub-index reflects overall
NAQI"). Primary reference:
https://cpcb.nic.in/National-Air-Quality-Index/  See also `docs/SOURCES.md`.

Honest caveat: averaging period
-------------------------------
The CPCB breakpoints are defined on **24-hour mean** concentrations (8-hour for
O3 and CO). Open-Meteo publishes **hourly** values. Baahar therefore applies the
CPCB 24-hour breakpoints to hourly concentrations, which is an *approximation*
of official NAQI, not official NAQI. Every result carries
:data:`NAQI_BASIS` describing exactly this, and the UI labels the number
accordingly. We think a clearly-labelled approximation is honest; a
mislabelled number is not.

Above the top breakpoint, CPCB publishes no higher concentration band (it just
says "430+"). Baahar extrapolates the final segment's slope and clamps at 500,
because reporting a saturated 500 is more useful than a flat line.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

__all__ = [
    "NAQI_BASIS",
    "NaqiBand",
    "NaqiResult",
    "PollutantSpec",
    "POLLUTANTS",
    "band_for_index",
    "band_index_range",
    "compute_naqi",
    "naqi_from_pm",
]

#: Machine-readable provenance string, surfaced in the API, UI and eval artifacts.
NAQI_BASIS = "cpcb_24h_breakpoints_applied_to_hourly_concentrations"

_INF = math.inf


class NaqiBand(StrEnum):
    """The six CPCB NAQI categories."""

    GOOD = "good"
    SATISFACTORY = "satisfactory"
    MODERATE = "moderate"
    POOR = "poor"
    SEVERE = "severe"
    HAZARDOUS = "hazardous"


#: (index_low_inclusive, index_high_inclusive, band, cpcb_health_impact)
#: Health-impact text is CPCB's own wording, lightly abbreviated for a phone
#: screen. Kept close to the source so the app is not inventing medical advice.
BANDS: tuple[tuple[int, int, NaqiBand, str], ...] = (
    (0, 50, NaqiBand.GOOD, "Minimal effect."),
    (51, 100, NaqiBand.SATISFACTORY, "Minor breathing discomfort to sensitive people."),
    (
        101,
        200,
        NaqiBand.MODERATE,
        "Breathing discomfort for people with lung, asthma or heart conditions.",
    ),
    (201, 300, NaqiBand.POOR, "Breathing discomfort to most people on prolonged exposure."),
    (301, 400, NaqiBand.SEVERE, "Respiratory illness on prolonged exposure."),
    (
        401,
        500,
        NaqiBand.HAZARDOUS,
        "Affects healthy people and seriously affects those with existing disease.",
    ),
)

#: Ordered by typical impact in an Indian city, so the UI can name the single
#: pollutant a user is actually breathing.
_BAND_BY_NAME = {b.value: (lo, hi, b, txt) for lo, hi, b, txt in BANDS}


def band_for_index(index: float | None) -> NaqiBand | None:
    """Map an NAQI value to its band. Out-of-range values clamp."""
    if index is None or not math.isfinite(index):
        return None
    idx = int(round(index))
    for lo, hi, band, _ in BANDS:
        if lo <= idx <= hi:
            return band
    return NaqiBand.HAZARDOUS if idx > 500 else NaqiBand.GOOD


def band_index_range(band: NaqiBand | str) -> tuple[int, int]:
    """Inclusive index range for a band, by name."""
    entry = _BAND_BY_NAME[NaqiBand(band).value]
    return entry[0], entry[1]


def band_health_impact(band: NaqiBand | str) -> str:
    """CPCB's short health-impact statement for a band."""
    return _BAND_BY_NAME[NaqiBand(band).value][3]


@dataclass(frozen=True)
class PollutantSpec:
    """How to turn one pollutant's concentration into a CPCB sub-index."""

    key: str
    """Key used in Baahar's own API payloads."""
    source_var: str
    """Open-Meteo air-quality hourly variable name."""
    label: str
    source_unit: str
    cpcb_unit: str
    #: multiply a source-unit reading by this to get the CPCB unit
    scale: float
    #: (conc_low, conc_high, idx_low, idx_high) in CPCB units.
    #: ``conc_high == inf`` marks the open-ended top band.
    bands: tuple[tuple[float, float, float, float], ...]
    #: CPCB averaging period, for documentation only.
    averaging_period: str

    def to_cpcb_unit(self, value: float) -> float:
        return value * self.scale

    def sub_index(self, value_source_unit: float) -> float:
        """CPCB sub-index for a reading given in the source unit."""
        conc = self.to_cpcb_unit(value_source_unit)
        if math.isnan(conc) or math.isinf(conc):
            return 0.0
        conc = max(conc, 0.0)

        bands = self.bands
        for n, (c_lo, c_hi, i_lo, i_hi) in enumerate(bands):
            if conc > c_hi and c_hi != _INF:
                continue
            if c_hi == _INF:
                # No CPCB band above this concentration. Continue the previous
                # segment's slope, then clamp: saturating at 500 is more honest
                # than inventing a scale that does not exist.
                if n == 0:  # pragma: no cover - no spec is defined this way
                    return float(i_lo)
                p_lo, p_hi, pi_lo, pi_hi = bands[n - 1]
                slope = (pi_hi - pi_lo) / (p_hi - p_lo)
                return min(500.0, i_lo + (conc - c_lo) * slope)
            span = c_hi - c_lo
            if span <= 0:  # pragma: no cover - guards malformed tables
                return float(i_hi)
            return i_lo + (i_hi - i_lo) * (conc - c_lo) / span
        return 500.0


# ---------------------------------------------------------------------------
# CPCB breakpoint tables (2014 NAQI), transcribed from the published table.
# Ranges are expressed as continuous boundaries: CPCB writes "0-50, 51-100";
# the piecewise-linear definition needs "0-50, 50-100" so there is no gap.
# ---------------------------------------------------------------------------

POLLUTANTS: dict[str, PollutantSpec] = {
    "pm25": PollutantSpec(
        key="pm25",
        source_var="pm2_5",
        label="PM2.5",
        source_unit="µg/m³",
        cpcb_unit="µg/m³",
        scale=1.0,
        averaging_period="24 h",
        bands=(
            (0, 30, 0, 50),
            (30, 60, 51, 100),
            (60, 90, 101, 200),
            (90, 120, 201, 300),
            (120, 250, 301, 400),
            (250, _INF, 401, 500),
        ),
    ),
    "pm10": PollutantSpec(
        key="pm10",
        source_var="pm10",
        label="PM10",
        source_unit="µg/m³",
        cpcb_unit="µg/m³",
        scale=1.0,
        averaging_period="24 h",
        bands=(
            (0, 50, 0, 50),
            (50, 100, 51, 100),
            (100, 250, 101, 200),
            (250, 350, 201, 300),
            (350, 430, 301, 400),
            (430, _INF, 401, 500),
        ),
    ),
    "no2": PollutantSpec(
        key="no2",
        source_var="nitrogen_dioxide",
        label="NO2",
        source_unit="µg/m³",
        cpcb_unit="µg/m³",
        scale=1.0,
        averaging_period="24 h",
        bands=(
            (0, 40, 0, 50),
            (40, 80, 51, 100),
            (80, 180, 101, 200),
            (180, 280, 201, 300),
            (280, 400, 301, 400),
            (400, _INF, 401, 500),
        ),
    ),
    "o3": PollutantSpec(
        key="o3",
        source_var="ozone",
        label="O3",
        source_unit="µg/m³",
        cpcb_unit="µg/m³",
        scale=1.0,
        averaging_period="8 h",
        bands=(
            (0, 50, 0, 50),
            (50, 100, 51, 100),
            (100, 168, 101, 200),
            (168, 208, 201, 300),
            (208, 748, 301, 400),
            (748, _INF, 401, 500),
        ),
    ),
    "co": PollutantSpec(
        key="co",
        source_var="carbon_monoxide",
        label="CO",
        # Open-Meteo reports CO in µg/m³; CPCB breakpoints are in mg/m³.
        source_unit="µg/m³",
        cpcb_unit="mg/m³",
        scale=1 / 1000.0,
        averaging_period="8 h",
        bands=(
            (0, 1.0, 0, 50),
            (1.0, 2.0, 51, 100),
            (2.0, 10, 101, 200),
            (10, 17, 201, 300),
            (17, 34, 301, 400),
            (34, _INF, 401, 500),
        ),
    ),
    "so2": PollutantSpec(
        key="so2",
        source_var="sulphur_dioxide",
        label="SO2",
        source_unit="µg/m³",
        cpcb_unit="µg/m³",
        scale=1.0,
        averaging_period="24 h",
        bands=(
            (0, 40, 0, 50),
            (40, 80, 51, 100),
            (80, 380, 101, 200),
            (380, 800, 201, 300),
            (800, 1600, 301, 400),
            (1600, _INF, 401, 500),
        ),
    ),
    "nh3": PollutantSpec(
        key="nh3",
        source_var="ammonia",
        label="NH3",
        source_unit="µg/m³",
        cpcb_unit="µg/m³",
        scale=1.0,
        averaging_period="24 h",
        bands=(
            (0, 200, 0, 50),
            (200, 400, 51, 100),
            (400, 800, 101, 200),
            (800, 1200, 201, 300),
            (1200, 1800, 301, 400),
            (1800, _INF, 401, 500),
        ),
    ),
    "pb": PollutantSpec(
        key="pb",
        source_var="lead",
        label="Pb",
        source_unit="µg/m³",
        cpcb_unit="µg/m³",
        scale=1.0,
        averaging_period="24 h",
        bands=(
            (0, 0.5, 0, 50),
            (0.5, 1.0, 51, 100),
            (1.0, 2.0, 101, 200),
            (2.0, 3.0, 201, 300),
            (3.0, 3.5, 301, 400),
            (3.5, _INF, 401, 500),
        ),
    ),
}

#: Order used when several pollutants tie for the worst sub-index.
_TIEBREAK_ORDER = ["pm25", "pm10", "o3", "no2", "so2", "co", "nh3", "pb"]


@dataclass(frozen=True)
class NaqiResult:
    """An NAQI reading plus everything needed to explain it."""

    index: float
    band: NaqiBand | None
    band_label: str
    health_impact: str
    dominant_pollutant: str | None
    dominant_label: str | None
    sub_indices: dict[str, float] = field(default_factory=dict)
    missing: tuple[str, ...] = ()
    basis: str = NAQI_BASIS

    @property
    def is_usable(self) -> bool:
        """False when no pollutant at all was available."""
        return bool(self.sub_indices)

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": round(self.index, 1),
            "band": self.band.value if self.band else None,
            "band_label": self.band_label,
            "health_impact": self.health_impact,
            "dominant_pollutant": self.dominant_pollutant,
            "dominant_label": self.dominant_label,
            "sub_indices": {k: round(v, 1) for k, v in self.sub_indices.items()},
            "missing": list(self.missing),
            "basis": self.basis,
        }


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f):
        return None
    return f


def compute_naqi(readings: Mapping[str, Any]) -> NaqiResult:
    """Compute Indian NAQI from a mapping of Baahar pollutant keys to values.

    ``readings`` uses Baahar's own keys (``pm25``, ``pm10``, ``no2``, ``o3``,
    ``co``, ``so2``, ``nh3``, ``pb``) with values in Open-Meteo's source units.
    Unknown keys are ignored, so passing a whole upstream payload is safe.

    The overall index is the worst (maximum) sub-index, per CPCB.
    """
    subs: dict[str, float] = {}
    missing: list[str] = []

    for key, spec in POLLUTANTS.items():
        raw = _as_float(readings.get(key))
        if raw is None:
            missing.append(spec.label)
            continue
        subs[key] = spec.sub_index(raw)

    if not subs:
        return NaqiResult(
            index=float("nan"),
            band=None,
            band_label="unknown",
            health_impact="",
            dominant_pollutant=None,
            dominant_label=None,
            sub_indices={},
            missing=tuple(missing),
        )

    # Worst sub-index wins. Ties broken by _TIEBREAK_ORDER, then alphabetically,
    # so the reported pollutant is deterministic.
    dominant = max(subs.values())
    tied = {k for k, v in subs.items() if abs(v - dominant) < 1e-9}
    dominant_key = next((k for k in _TIEBREAK_ORDER if k in tied), sorted(tied)[0])

    band = band_for_index(dominant)
    return NaqiResult(
        index=dominant,
        band=band,
        band_label=band.value.capitalize() if band else "Unknown",
        health_impact=band_health_impact(band) if band else "",
        dominant_pollutant=dominant_key,
        dominant_label=POLLUTANTS[dominant_key].label,
        sub_indices=subs,
        missing=tuple(missing),
    )


def naqi_from_pm(pm25: float | None = None, pm10: float | None = None) -> NaqiResult:
    """Convenience wrapper for the two pollutants Open-Meteo always returns."""
    return compute_naqi({"pm25": pm25, "pm10": pm10})


def band_table() -> list[dict[str, Any]]:
    """The NAQI scale as data, for the UI legend and the docs."""
    return [
        {
            "index_low": lo,
            "index_high": hi,
            "band": band.value,
            "label": band.value.capitalize(),
            "health_impact": text,
        }
        for lo, hi, band, text in BANDS
    ]


def pollutant_table() -> list[dict[str, Any]]:
    """Breakpoints as data, so the docs cannot drift from the code."""
    rows: list[dict[str, Any]] = []
    for spec in POLLUTANTS.values():
        rows.append(
            {
                "key": spec.key,
                "label": spec.label,
                "source_var": spec.source_var,
                "source_unit": spec.source_unit,
                "cpcb_unit": spec.cpcb_unit,
                "averaging_period": spec.averaging_period,
                "breakpoints": [
                    {
                        "conc_low": c_lo,
                        "conc_high": None if c_hi == _INF else c_hi,
                        "index_low": i_lo,
                        "index_high": i_hi,
                    }
                    for c_lo, c_hi, i_lo, i_hi in spec.bands
                ],
            }
        )
    return rows


def readings_from_payload(hourly: Mapping[str, Any], index: int) -> dict[str, Any]:
    """Extract a Baahar pollutant mapping from one hour of an Open-Meteo payload.

    Tolerates ``None`` values, which Open-Meteo uses for missing data.
    """
    out: dict[str, Any] = {}
    for key, spec in POLLUTANTS.items():
        series = hourly.get(spec.source_var)
        if isinstance(series, list) and 0 <= index < len(series):
            out[key] = series[index]
    return out


def iter_specs() -> Iterable[PollutantSpec]:
    return POLLUTANTS.values()
