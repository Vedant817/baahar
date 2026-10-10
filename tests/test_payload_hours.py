"""Payload hours must be comparable with the clock the walk policy uses.

Two regressions live here, and the rest of the suite cannot see either of them
because `tests/conftest.py` builds its hours with timezone-aware datetimes by
hand, while a real payload is parsed from text:

* Open-Meteo answers with wall-clock strings that carry no offset and report the
  offset separately. ``datetime.fromisoformat`` on those strings yields *naive*
  hours, and ``build_plan``'s current-hour lookup skips naive hours -- so a plan
  built from a live or recorded payload had no current hour at all, and Pocket
  Mode could never start outside the first second of an hour.
* ``slice_from_now`` anchored on ``item.time >= now``, which discards the hour
  that *contains* now for the 59 minutes of every hour that are not exactly on
  the boundary.
"""

from datetime import UTC, datetime, timedelta, timezone

from baahar.air import parse_air
from baahar.models import (
    DataSource,
    Decision,
    HourSlot,
    as_payload_time,
    payload_timezone,
    slice_from_now,
)
from baahar.score import build_plan
from baahar.weather import parse_weather

IST = timezone(timedelta(hours=5, minutes=30))

#: Three consecutive afternoon hours, as Open-Meteo words them.
TIMES = ["2026-10-10T13:00:00", "2026-10-10T14:00:00", "2026-10-10T15:00:00"]


def _payload():
    return {
        "utc_offset_seconds": 19800,
        "hourly": {
            "time": TIMES,
            "temperature_2m": [26.0, 27.0, 28.0],
            "apparent_temperature": [27.0, 28.0, 29.0],
            "precipitation": [0.0, 0.0, 0.0],
            "precipitation_probability": [5, 5, 5],
            "relative_humidity_2m": [60, 60, 60],
            "wind_speed_10m": [8, 8, 8],
            "uv_index": [3, 3, 3],
            "weather_code": [0, 0, 0],
            "is_day": [1, 1, 1],
        },
    }


def _air_payload():
    return {
        "utc_offset_seconds": 19800,
        "hourly": {
            "time": TIMES,
            "pm10": [40.0, 40.0, 40.0],
            "pm2_5": [20.0, 20.0, 20.0],
            "carbon_monoxide": [200.0, 200.0, 200.0],
            "nitrogen_dioxide": [10.0, 10.0, 10.0],
            "sulphur_dioxide": [5.0, 5.0, 5.0],
            "ozone": [60.0, 60.0, 60.0],
            "ammonia": [2.0, 2.0, 2.0],
            "us_aqi": [30.0, 30.0, 30.0],
        },
    }


def test_payload_offset_becomes_a_real_timezone():
    assert payload_timezone(_payload()).utcoffset(None) == timedelta(hours=5, minutes=30)


def test_payload_hours_are_localised_not_naive():
    hours = parse_weather(_payload())
    air = parse_air(_air_payload())
    for slot in hours:
        assert slot.time.tzinfo is not None, "a naive hour cannot be compared with now"
    for hour in air:
        assert hour.time.tzinfo is not None
    assert hours[0].time == datetime(2026, 10, 10, 13, 0, tzinfo=IST)


def test_a_timestamp_that_already_carries_an_offset_is_left_alone():
    aware = as_payload_time("2026-10-10T13:00:00+00:00", IST)
    assert aware == datetime(2026, 10, 10, 13, 0, tzinfo=UTC)


def test_slice_from_now_keeps_the_hour_that_contains_now():
    hours = parse_weather(_payload())
    for minute in (0, 10, 59):
        now = datetime(2026, 10, 10, 14, minute, tzinfo=IST)
        window = [h.time for h in slice_from_now(hours, 4, now=now)]
        assert datetime(2026, 10, 10, 14, 0, tzinfo=IST) in window
        assert window[0] == datetime(2026, 10, 10, 14, 0, tzinfo=IST)


def test_recorded_payload_slots_are_stamped_fixture_not_live():
    """A slot inside a recorded plan must not advertise a live source.

    `HourSlot` defaults both sources to LIVE, so a joined slot said "live" inside
    a plan the eligibility gate was about to refuse for being recorded. Any
    consumer reading the slot rather than the plan was told the opposite of the
    truth, in the unsafe direction.
    """
    from baahar import forecast

    slots, wsrc, asrc = forecast.fetch_joined(hours=6, offline=True)
    assert wsrc is DataSource.FIXTURE
    assert asrc is DataSource.FIXTURE
    assert slots, "the recorded fixture must still produce hours"
    for slot in slots:
        assert slot.weather_source is DataSource.FIXTURE
        assert slot.air_source is DataSource.FIXTURE


def test_a_plan_built_from_a_real_payload_has_a_current_hour():
    weather_hours = parse_weather(_payload())
    air_hours = {h.time: h for h in parse_air(_air_payload())}
    slots = [HourSlot(weather=w, air=air_hours[w.time]) for w in weather_hours]
    plan = build_plan(
        slots,
        generated_at=datetime(2026, 10, 10, 14, 30, tzinfo=IST),
        weather_source=DataSource.LIVE,
        air_source=DataSource.LIVE,
        scorer="heuristic",
    )
    assert plan.current_slot is not None, "a parsed payload must still produce a current hour"
    assert plan.current_slot.time == datetime(2026, 10, 10, 14, 0, tzinfo=IST)
    assert plan.current_decision in {Decision.GO, Decision.WAIT, Decision.SKIP}
