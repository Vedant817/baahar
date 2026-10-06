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
O3 and CO). Open-Meteo publishes **hourly** values, so no single hourly reading
*is* an official NAQI input. Baahar therefore reports two numbers per hour and
acts on the more conservative of them:

* :func:`compute_naqi` -- CPCB breakpoints applied to the **instantaneous**
  hourly concentration. Cheap, responsive to a spike, but not what CPCB means.
* :func:`compute_naqi_trailing` -- CPCB breakpoints applied to a **trailing
  mean** over each pollutant's own CPCB averaging period. This is much closer
  to official NAQI, and it is *sticky*: an afternoon reading that looks clean
  because the night's dust has not settled yet is not clean.

:func:`conservative_naqi` takes the higher of the two, so the number the product
acts on can never be lower than the reading it started from. Every result
carries a basis string naming how *it* was computed --
:data:`NAQI_BASIS_INSTANTANEOUS`, :data:`NAQI_BASIS_TRAILING`, or the combined
:data:`NAQI_BASIS` for the hour objects `parse_air` builds -- and the UI labels
the number accordingly. We think a clearly-labelled approximation is honest; a
mislabelled number is not. A function that only ever reads a single hour
therefore never claims a trailing mean, whatever the dataclass default says.

Measured on the recorded Bengaluru archive (Nov 2025 - Oct 2026, 8,112 hours),
the trailing mean runs up to 23 index points above the instantaneous value and
crosses a band boundary upward on 13 of them. That is small, which is why this
went unnoticed -- but it is one-directional, and the direction is the unsafe one.

Above the top breakpoint, CPCB publishes no higher concentration band (it just
says "430+"). Baahar extrapolates the final segment's slope and clamps at 500,
because reporting a saturated 500 is more useful than a flat line.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

__all__ = [
    "AVERAGING_PERIOD_HOURS",
    "MIN_TRAILING_HOURS",
    "NAQI_BASIS",
    "NAQI_BASIS_INSTANTANEOUS",
    "NAQI_BASIS_TRAILING",
    "HISTORY_TIME_KEYS",
    "NaqiBand",
    "NaqiResult",
    "PollutantSpec",
    "POLLUTANTS",
    "TrailingNaqi",
    "assert_chronological",
    "band_for_index",
    "band_index_range",
    "compute_naqi",
    "compute_naqi_trailing",
    "conservative_naqi",
    "naqi_from_pm",
    "parse_naqi_basis",
]

#: Machine-readable provenance string, surfaced in the API, UI and eval artifacts.
#:
#: It names *two* things because the number Baahar acts on is built from two
#: inputs (see :func:`conservative_naqi`), and a provenance string that named
#: only one of them would be the kind of quiet mislabelling this module exists to
#: avoid. The two halves are joined by ``NAQI_BASIS_SEPARATOR`` so the value
#: stays parseable: :func:`parse_naqi_basis` splits it back apart.
#:
#: The instantaneous half keeps the *exact* literal that used to stand alone,
#: so anything pinning the old string still finds its substring and the old
#: meaning has not silently moved.
NAQI_BASIS_INSTANTANEOUS = "cpcb_24h_breakpoints_applied_to_hourly_concentrations"
NAQI_BASIS_TRAILING = "cpcb_breakpoints_applied_to_trailing_period_means"
NAQI_BASIS_SEPARATOR = "+"
NAQI_BASIS = f"{NAQI_BASIS_INSTANTANEOUS}{NAQI_BASIS_SEPARATOR}{NAQI_BASIS_TRAILING}"


def parse_naqi_basis(basis: str = NAQI_BASIS) -> tuple[str, ...]:
    """Split a basis string into its named parts, in the order they combine."""
    return tuple(basis.split(NAQI_BASIS_SEPARATOR))


#: CPCB averaging period per pollutant, in hours. This is the window a trailing
#: mean must use: 24 h for the particulates and gases, 8 h for O3 and CO. Using
#: one window for everything would be wrong in both directions -- a 24 h O3 mean
#: dilutes a real afternoon ozone peak with clean night-time air, and an 8 h
#: PM2.5 mean tracks a single spike that CPCB deliberately smooths away.
AVERAGING_PERIOD_HOURS: dict[str, int] = {
    "pm25": 24,
    "pm10": 24,
    "no2": 24,
    "so2": 24,
    "nh3": 24,
    "pb": 24,
    "o3": 8,
    "co": 8,
}

#: Minimum hours of history before a trailing mean is reported at all. Below
#: this, a "24-hour mean" is a fiction, and a mean over two samples is closer to
#: the instantaneous reading than to the official number while looking more
#: authoritative. Refusing to produce one is the honest answer.
MIN_TRAILING_HOURS = 3

#: Keys a caller may use to stamp an hour inside a history mapping. If any of
#: them is present, :func:`compute_naqi_trailing` checks the series is in
#: ascending time order before it averages anything.
HISTORY_TIME_KEYS: tuple[str, ...] = ("time", "timestamp")

_INF = math.inf


def _as_epoch(value: Any) -> float | None:
    """Seconds since the epoch for a datetime, an ISO string or a number."""
    if value is None:
        return None
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, str):
        try:
            moment = datetime.fromisoformat(value)
        except ValueError:
            return None
    else:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.timestamp()


def _stamp_of(row: Mapping[str, Any]) -> Any:
    """The hour a history row claims to be, if it claims one at all.

    Returns the raw value under the first key in :data:`HISTORY_TIME_KEYS` that
    is present, so the error message from :func:`assert_chronological` quotes the
    caller's own timestamp rather than a normalised one.
    """
    for key in HISTORY_TIME_KEYS:
        if key in row:
            return row[key]
    return None


def assert_chronological(times: Sequence[Any], *, where: str) -> None:
    """Raise ``ValueError`` unless ``times`` is strictly ascending.

    A trailing mean over an out-of-order series is silently wrong, and it is
    wrong in the unsafe direction: mixing a dirty afternoon into a clean
    overnight window can pull the mean *down*, so the number reads better than
    the hours it was measured from. Sorting quietly here would hide an upstream
    data bug behind a correct-looking number, so this refuses instead -- the
    same discipline as ``assert_no_leakage`` in ``scripts/build_dataset.py``:
    state the invariant, then let the reader see it break.

    Entries that carry no recognisable timestamp (``None``, or a string that is
    not ISO-8601) are skipped rather than guessed at. If two *known* stamps are
    out of order, that is still an error.
    """
    known = [
        (i, raw, stamp) for i, raw in enumerate(times) if (stamp := _as_epoch(raw)) is not None
    ]
    for (i, prev_raw, prev), (j, cur_raw, cur) in zip(known, known[1:], strict=False):
        if cur <= prev:
            raise ValueError(
                f"{where}: entry {j} ({cur_raw!r}) is not in ascending time "
                f"order after entry {i} ({prev_raw!r}). A trailing mean over an "
                "out-of-order series can come out LOWER than the hours it was "
                "measured from, which is the unsafe direction. Fix the series "
                "upstream; this function will not sort it for you."
            )


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
    #: Instantaneous by default, because the only calculators that build a
    #: :class:`NaqiResult` without saying otherwise are the ones that read a
    #: single hour (:func:`compute_naqi`, :func:`naqi_from_pm`). Defaulting this
    #: to the combined basis would make every one of them publish a trailing
    #: mean it never computed -- the exact quiet mislabelling this module
    #: exists to prevent. :func:`compute_naqi_trailing` and
    #: :func:`parse_air` set their own basis explicitly.
    basis: str = NAQI_BASIS_INSTANTANEOUS

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

    **Instantaneous only.** This applies the CPCB breakpoints to the values as
    given, which for a single hour is an approximation of official NAQI, not
    official NAQI -- the breakpoints are defined on averaged concentrations. Use
    :func:`compute_naqi_trailing` for the averaged reading and
    :func:`conservative_naqi` for the number the product should act on. This
    function's behaviour is unchanged from before; it remains the honest
    single-reading calculator it always was.

    The result therefore carries :data:`NAQI_BASIS_INSTANTANEOUS`, which names
    the instantaneous reading and nothing else. It used to inherit the combined
    :data:`NAQI_BASIS` from the dataclass default, which made a function that
    never averages anything claim a trailing mean -- and two consumers
    (``scripts/build_dataset.py`` and ``scripts/run_briefing_eval.py``) publish
    these results straight into eval artifacts.

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


# ---------------------------------------------------------------------------
# Trailing means, and the conservative combination of the two readings
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TrailingNaqi:
    """NAQI from trailing means, with the evidence that backs it."""

    #: The NAQI computed from the trailing means. Same shape as any other
    #: result, so callers do not have to special-case it.
    result: NaqiResult
    #: How many hours of history actually backed each pollutant's mean. Keyed by
    #: Baahar pollutant key; a pollutant absent here had too little history and
    #: was left out entirely rather than guessed at.
    hours_used: dict[str, int] = field(default_factory=dict)

    @property
    def is_usable(self) -> bool:
        return self.result.is_usable

    @property
    def index(self) -> float:
        return self.result.index

    @property
    def hours(self) -> int:
        """Hours behind the mean that produced the *reported* sub-index.

        That is the hours behind the dominant pollutant, not the deepest window
        we happened to have. A number and its evidence have to agree.
        """
        key = self.result.dominant_pollutant
        return self.hours_used.get(key, 0) if key else 0

    @property
    def window_hours(self) -> int:
        """CPCB averaging period of the dominant pollutant."""
        key = self.result.dominant_pollutant
        return AVERAGING_PERIOD_HOURS.get(key, 0) if key else 0

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.result.to_dict(),
            "trailing_hours_used": dict(self.hours_used),
            "trailing_window_hours": self.window_hours,
        }


def _trailing_mean(
    history: Sequence[Mapping[str, Any]], key: str, window: int
) -> tuple[float, int]:
    """Mean of ``key`` over the last ``window`` hours that have a reading.

    Returns ``(mean, hours_used)``. Hours with a missing value are skipped
    rather than treated as zero -- a gap in the upstream feed is not evidence of
    clean air, and counting it as zero would let one gap quietly halve a mean
    over a polluted day. The window is therefore a window *of hours present*,
    and :attr:`TrailingNaqi.hours_used` records how many that actually was, so
    a short window is visible instead of silent.
    """
    values: list[float] = []
    for row in history[-window:]:
        value = _as_float(row.get(key))
        if value is None:
            continue
        if value < 0.0:
            # A negative concentration is not a measurement at all, and the two
            # honest ways to handle one differ in *direction*. Clamping to zero
            # would pull the mean DOWN -- a worse-looking day caused by a
            # broken sensor, in the same direction as a gap in the feed. Worse,
            # it invents a reading the archive does not contain. So the hour is
            # dropped instead, exactly like a missing one, and `hours_used`
            # records that it is gone. Dropping it cannot make the reported
            # number look cleaner than the hours that were measured.
            continue
        values.append(value)
    if not values:
        return float("nan"), 0
    return math.fsum(values) / len(values), len(values)


def compute_naqi_trailing(history: Sequence[Mapping[str, Any]]) -> TrailingNaqi | None:
    """Indian NAQI from trailing means over each pollutant's CPCB period.

    ``history`` is a chronological sequence of Baahar readings mappings -- one
    per hour, oldest first, with the hour being scored as the **last** element.
    Use Baahar's own keys (``pm25``, ``o3``, ...) in Open-Meteo source units;
    unknown keys and ``None`` values are ignored.

    Each pollutant is averaged over its own CPCB averaging period (24 h, or 8 h
    for O3 and CO) and then run through the same breakpoints as
    :func:`compute_naqi`. This is much closer to official NAQI than the
    instantaneous reading, because the breakpoints were defined on averaged
    concentrations in the first place.

    The window may be partial -- early hours of a series have less than 24 h of
    history -- and however many hours exist are used. How many is reported per
    pollutant in :attr:`TrailingNaqi.hours_used`, because a mean over three hours
    and a mean over twenty-four are not the same claim and the reader is
    entitled to know which one they are looking at.

    **Order is checked, not assumed.** If the history mappings carry a timestamp
    (any key in :data:`HISTORY_TIME_KEYS`) the series must be strictly ascending,
    or this raises ``ValueError``. Averaging an out-of-order window silently
    mixes hours from the wrong day and can lower the mean, which is the unsafe
    direction; sorting here would hide the upstream bug behind a plausible
    number.

    Returns ``None`` when there is less than :data:`MIN_TRAILING_HOURS` of usable
    history for any pollutant. A mean over one or two samples would be arithmetic
    dressed up as a 24-hour average, and this module does not invent numbers.
    """
    assert_chronological(
        [_stamp_of(row) for row in history],
        where="compute_naqi_trailing(history)",
    )
    if len(history) < MIN_TRAILING_HOURS:
        return None

    means: dict[str, float] = {}
    hours_used: dict[str, int] = {}
    for key, window in AVERAGING_PERIOD_HOURS.items():
        mean, used = _trailing_mean(history, key, window)
        if used < MIN_TRAILING_HOURS:
            continue
        means[key] = mean
        hours_used[key] = used

    if not means:
        return None
    result = replace(compute_naqi(means), basis=NAQI_BASIS_TRAILING)
    if not result.is_usable:
        return None
    return TrailingNaqi(result=result, hours_used=hours_used)


def conservative_naqi(instant: NaqiResult, trailing: TrailingNaqi | None) -> NaqiResult:
    """The more conservative of the instantaneous and trailing-mean readings.

    This is the value Baahar acts on. Two readings of the same hour disagreeing
    is not a reason to pick the nicer one: CPCB's own definition is built on
    averaged concentrations, so when the trailing mean is worse, the trailing
    mean is the more faithful answer and the instantaneous hour is the artefact.

    The returned result is never lower than ``instant``. Ties keep the
    instantaneous reading, so an hour where the two agree is byte-identical to
    what the product showed before this change.

    If ``trailing`` is ``None`` -- too little history, or nothing upstream --
    the instantaneous reading is returned untouched, because refusing to produce
    any number is not an option and the instantaneous value is the only one we
    honestly have.
    """
    if trailing is None or not trailing.is_usable:
        return instant
    if not instant.is_usable:
        return trailing.result
    return trailing.result if trailing.result.index > instant.index else instant


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

    Tolerates ``None`` values, which Open-Meteo uses for missing data. Used by
    the dataset builder, which reads archives rather than live forecasts.
    """
    out: dict[str, Any] = {}
    for key, spec in POLLUTANTS.items():
        series = hourly.get(spec.source_var)
        if isinstance(series, list) and 0 <= index < len(series):
            out[key] = series[index]
    return out
