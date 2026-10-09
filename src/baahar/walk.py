"""Current-hour walking permission, shared by prose and Pocket Mode."""
from datetime import UTC, datetime, timedelta

from .models import DataSource, Decision, OutdoorPlan

MAX_PLAN_AGE = timedelta(minutes=15)


def utc_now() -> datetime:
    return datetime.now(UTC)


def eligibility(plan: OutdoorPlan, now: datetime | None = None) -> tuple[bool, str]:
    now = now or utc_now()
    if now.tzinfo is None or plan.generated_at.tzinfo is None:
        return False, "Assessment time is unavailable; refresh conditions before walking."
    age = now - plan.generated_at
    if age < timedelta(0) or age > MAX_PLAN_AGE:
        return False, "This assessment has expired; refresh conditions before walking."
    if plan.air_source is not DataSource.LIVE or plan.weather_source is not DataSource.LIVE:
        return False, "Recorded or unavailable data cannot authorize a walk now."
    slot = plan.current_slot
    if slot is None:
        # Support older serialized plans only when their selected hour is current.
        slot = plan.best_slot
    if slot is None or slot.time.tzinfo is None or not (
        slot.time <= now < slot.time + timedelta(hours=1)
    ):
        return False, "No current-hour assessment; refresh conditions before walking."
    if slot.air.time != slot.weather.time:
        return False, "Air and weather hours do not match; refresh conditions before walking."
    if slot.air_source is not DataSource.LIVE or slot.weather_source is not DataSource.LIVE:
        return False, "Recorded or unavailable current-hour data cannot authorize walking."
    from .score import score_heuristic

    current = score_heuristic([slot])[0]
    if current.decision is not Decision.GO or (
        plan.current_decision is not None and plan.current_decision is not Decision.GO
    ):
        return False, "Current conditions do not permit a walk. " + " ".join(current.reasons)
    if plan.overall is not Decision.GO:
        return False, "Hold off on walking and recheck conditions."
    return True, "Current-hour conditions permit considering a walk."
