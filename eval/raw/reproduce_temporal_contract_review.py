"""Explicit synthetic offline review probe; not a recorded API fixture."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from baahar.briefing_contract import build_contract_case, deterministic_fallback, evaluate
from baahar.models import HourlyAir, HourlyWeather, HourSlot
from baahar.pocket import build_pocket
from baahar.score import build_plan

now = datetime(2026, 10, 8, 4, 30, tzinfo=UTC)
slots = [
    HourSlot(
        weather=HourlyWeather(
            time=now + timedelta(hours=h),
            apparent_c=25,
            temp_c=25,
            precip_mm=0,
            precip_prob=0,
            is_day=1,
        ),
        air=HourlyAir(time=now + timedelta(hours=h), naqi=naqi),
    )
    for h, naqi in [(0, 350), (2, 50)]
]
plan = build_plan(slots, scorer="heuristic", generated_at=now)
facts = build_contract_case(plan)
text = deterministic_fallback(facts)
result = {
    "provenance": "explicit synthetic offline counterexample, not field observation",
    "current_naqi": 350,
    "future_naqi": 50,
    "future_offset_hours": 2,
    "overall": plan.overall.value,
    "best_time": plan.best_time.isoformat(),
    "facts": facts,
    "fallback": text,
    "check": evaluate(text, facts),
    "pocket_active": build_pocket(plan).active,
}
target = Path(__file__).with_name("temporal_contract_review_20261008.json")
target.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
print(json.dumps(result, indent=2, default=str))
