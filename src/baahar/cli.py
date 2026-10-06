"""Typer CLI: `baahar brief`, `score`, `parks`, `journal`, `check`, `serve`.

The CLI is the fastest path to the product and the easiest thing for a judge to
run. It must work with no keys and no network, which is why every command
degrades to recorded fixtures or the deterministic template writer rather than
erroring out.
"""

from __future__ import annotations

import contextlib
import json
import logging
import sys
from datetime import datetime
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from . import brief as brief_mod
from . import forecast as forecast_mod
from . import journal as journal_mod
from . import parks as parks_mod
from . import pocket as pocket_mod
from . import score as score_mod
from .config import get_settings
from .models import BriefResponse, Decision

console = Console()
err = Console(stderr=True)

app = typer.Typer(
    name="baahar",
    help="Baahar (बाहर) -- find Bengaluru's next safe outdoor hour, then put the phone away.",
    no_args_is_help=True,
    add_completion=False,
)

DECISION_STYLE = {
    Decision.GO: "bold green",
    Decision.WAIT: "bold yellow",
    Decision.SKIP: "bold red",
}


def _build(
    *,
    city: str | None,
    lat: float | None,
    lon: float | None,
    hours: int | None,
    offline: bool | None,
    writer: str,
    voice: bool,
    walk_minutes: int | None,
    scorer: str,
    park_id: str | None,
) -> BriefResponse:
    """Shared pipeline for `brief` and the API."""
    settings = get_settings()
    target_lat = lat if lat is not None else settings.lat
    target_lon = lon if lon is not None else settings.lon

    slots, wsrc, asrc = forecast_mod.fetch_joined(
        lat=target_lat, lon=target_lon, hours=hours, offline=offline
    )

    park = None
    if park_id:
        park = parks_mod.park_by_id(park_id)
        if park is None:
            raise typer.BadParameter(f"unknown park id {park_id!r}; try `baahar parks`")
    else:
        park = parks_mod.pick_park(lat=target_lat, lon=target_lon)

    plan = score_mod.build_plan(
        slots,
        city=city or settings.city,
        scorer=scorer,
        park=park,
        weather_source=wsrc,
        air_source=asrc,
    )
    pocket = pocket_mod.build_pocket(
        plan, walk_minutes=pocket_mod.ensure_walk_minutes(walk_minutes)
    )
    briefing = brief_mod.generate(
        plan,
        writer=writer,
        park=park,
        voice=voice,
        notice_this=pocket_mod.briefing_cue(plan),
    )
    return BriefResponse(plan=plan, briefing=briefing, pocket=pocket)


@app.command()
def brief(
    city: Annotated[str | None, typer.Option(help="City name used in output.")] = None,
    lat: Annotated[float | None, typer.Option(help="Latitude.")] = None,
    lon: Annotated[float | None, typer.Option(help="Longitude.")] = None,
    hours: Annotated[int | None, typer.Option(help="Hours of forecast to score.")] = None,
    offline: Annotated[bool, typer.Option(help="Force recorded fixtures.")] = False,
    model: Annotated[
        str, typer.Option(help="Briefing writer: auto | gemma | tinker | template.")
    ] = "auto",
    voice: Annotated[bool, typer.Option(help="Also speak the briefing (ElevenLabs).")] = False,
    walk_minutes: Annotated[int | None, typer.Option(help="Pocket Mode walk length.")] = None,
    scorer: Annotated[str, typer.Option(help="Scorer: auto | heuristic | tabpfn.")] = "auto",
    park: Annotated[str | None, typer.Option(help="Force a park by id.")] = None,
) -> None:
    """Print the full brief: decision, hour table, park, and briefing."""
    resp = _build(
        city=city,
        lat=lat,
        lon=lon,
        hours=hours,
        offline=offline or None,
        writer=model,
        voice=voice,
        walk_minutes=walk_minutes,
        scorer=scorer,
        park_id=park,
    )
    render_brief(resp)


def render_brief(resp: BriefResponse) -> None:
    plan, briefing, pocket = resp.plan, resp.briefing, resp.pocket

    console.print()
    console.rule(f"Baahar · {plan.city}", style="cyan")
    console.print()

    console.print(f"  {plan.overall.value}", style=DECISION_STYLE[plan.overall], end="")
    console.print(f"  {plan.headline}", style="bold")
    console.print()

    for item in plan.degraded:
        console.print(f"  ! {item}", style="yellow")

    slots = plan.slots[: plan.window_hours]
    if slots:
        table = Table(box=None, pad_edge=False, show_header=True, header_style="dim")
        table.add_column("time", style="bold", no_wrap=True)
        table.add_column("call", no_wrap=True)
        table.add_column("comfort", justify="right", no_wrap=True)
        table.add_column("NAQI", justify="right", no_wrap=True)
        table.add_column("feels", justify="right", no_wrap=True)
        table.add_column("why", style="dim")
        for slot in slots:
            sig = slot.signals
            feels = sig.get("apparent_c")
            temp = sig.get("temp_c")
            if temp is not None and feels is not None:
                feels_txt = f"{temp:.0f}/{feels:.0f}°"
            elif temp is not None:
                feels_txt = f"{temp:.0f}°"
            else:
                feels_txt = "-"
            naqi = sig.get("naqi")
            table.add_row(
                slot.time.strftime("%H:%M"),
                f"[{DECISION_STYLE[slot.decision]}]{slot.decision.value}[/]",
                f"{slot.comfort:.0f}",
                f"{naqi:.0f}" if naqi is not None else "-",
                feels_txt,
                slot.reasons[0] if slot.reasons else "",
            )
        console.print(table)
        console.print()

    if plan.park:
        console.print(f"  Park: [bold]{plan.park.name}[/] ({plan.park.area})")
        console.print(f"        {plan.park.vibe} [dim]{plan.park.crowding_hint}[/]")
        console.print(f"        [dim]{plan.park.gate_note}[/]")
        console.print()

    console.print("  Briefing", style="bold")
    for line in _wrap(briefing.text, 74):
        console.print(f"  {line}")
    console.print()
    console.print(
        f"  [dim]writer={briefing.writer} model={briefing.model} "
        f"words={briefing.word_count} latency={briefing.latency_ms}ms[/]"
    )
    if briefing.note:
        console.print(f"  [dim]{briefing.note}[/]")

    console.print()
    console.print("  Pocket Mode", style="bold")
    console.print(f"    {pocket.headline}", style="bold white")
    console.print(f"    [dim]{pocket.subline}[/]")
    console.print(f"    notice this: {pocket.notice_this}")
    console.print(f"    walk: {pocket.walk_minutes} min")
    console.print(f"    [dim]{pocket.safety_note}[/]")
    console.print()
    console.print(f"  [dim]{resp.disclaimer}[/]")
    console.print()
    console.print('  [dim]after the walk: uv run baahar journal --outcome went --note "..."[/]')
    console.print()


def _wrap(text: str, width: int) -> list[str]:
    words, lines, current = text.split(), [], ""
    for word in words:
        if len(current) + len(word) + 1 > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    return lines


@app.command()
def score(
    lat: Annotated[float | None, typer.Option()] = None,
    lon: Annotated[float | None, typer.Option()] = None,
    hours: Annotated[int | None, typer.Option()] = None,
    offline: Annotated[bool, typer.Option()] = False,
    scorer: Annotated[str, typer.Option(help="auto | heuristic | tabpfn")] = "auto",
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Print only the GO/WAIT/SKIP table."""
    settings = get_settings()
    slots, wsrc, asrc = forecast_mod.fetch_joined(
        lat=lat if lat is not None else settings.lat,
        lon=lon if lon is not None else settings.lon,
        hours=hours,
        offline=offline or None,
    )
    plan = score_mod.build_plan(slots, scorer=scorer, weather_source=wsrc, air_source=asrc)

    if as_json:
        # `print_json` takes a JSON *string*, not a dict. Passing the dict raises
        # TypeError, which the CI smoke test did not catch because the command
        # was piped into `head` and the pipeline reported head's exit code.
        console.print_json(json.dumps(plan.model_dump(mode="json"), default=str))
        return

    table = Table(title=f"Baahar score · {plan.city} · scorer={plan.scorer}", box=None)
    table.add_column("time", style="bold")
    table.add_column("call")
    table.add_column("comfort", justify="right")
    table.add_column("NAQI", justify="right")
    table.add_column("band")
    table.add_column("why", style="dim")
    for slot in plan.slots:
        sig = slot.signals
        table.add_row(
            slot.time.strftime("%H:%M"),
            f"[{DECISION_STYLE[slot.decision]}]{slot.decision.value}[/]",
            f"{slot.comfort:.0f}",
            f"{sig['naqi']:.0f}" if sig.get("naqi") is not None else "-",
            str(sig.get("naqi_band") or "-"),
            slot.reasons[0] if slot.reasons else "",
        )
    console.print()
    console.print(table)
    console.print()
    console.print(f"  {plan.overall.value}: {plan.headline}")
    if plan.scorer_note:
        console.print(f"  [dim]{plan.scorer_note}[/]")
    console.print()


@app.command("parks")
def parks_cmd(
    lat: Annotated[float | None, typer.Option()] = None,
    lon: Annotated[float | None, typer.Option()] = None,
    limit: Annotated[int, typer.Option()] = 6,
) -> None:
    """List curated parks, nearest first."""
    settings = get_settings()
    target_lat = lat if lat is not None else settings.lat
    target_lon = lon if lon is not None else settings.lon
    table = Table(title="Baahar parks · Bengaluru", box=None)
    table.add_column("id", style="bold")
    table.add_column("name")
    table.add_column("km", justify="right")
    table.add_column("shade")
    table.add_column("vibe", style="dim")
    for park in parks_mod.nearest_parks(target_lat, target_lon, limit=limit):
        table.add_row(
            park.id,
            park.name,
            f"{parks_mod.distance_to(target_lat, target_lon, park):.1f}",
            park.shade,
            park.vibe[:70],
        )
    console.print()
    console.print(table)
    console.print()


@app.command()
def journal(
    outcome: Annotated[
        str | None,
        typer.Option(help="went | shortened | skipped. Omit to just print the journal."),
    ] = None,
    note: Annotated[str, typer.Option(help="One line. The most useful field.")] = "",
    park: Annotated[str | None, typer.Option(help="Park name.")] = None,
    naqi: Annotated[float | None, typer.Option(help="NAQI Baahar showed.")] = None,
    band: Annotated[str | None, typer.Option(help="NAQI band label.")] = None,
    decided: Annotated[str | None, typer.Option(help="What Baahar decided: GO/WAIT/SKIP")] = None,
    window: Annotated[str | None, typer.Option(help="Planned window, e.g. 06:00-07:00")] = None,
    felt_c: Annotated[float | None, typer.Option(help="Temperature you actually felt.")] = None,
    walked_min: Annotated[int | None, typer.Option(help="Minutes actually walked.")] = None,
    planned_min: Annotated[int | None, typer.Option(help="Minutes Pocket Mode offered.")] = None,
    phone: Annotated[
        int | None, typer.Option(help="How many times you reached for the phone.")
    ] = None,
    species: Annotated[
        str | None,
        typer.Option("--species", help="The species Baahar suggested, if a cue was shown."),
    ] = None,
    saw: Annotated[
        str | None,
        typer.Option(
            "--saw",
            help=(
                "Did you see it? yes | no | unrecognised | not-looked. "
                "'unrecognised' means the name did not land, which is a different "
                "failure from not spotting the bird."
            ),
        ),
    ] = None,
    as_markdown: Annotated[
        bool, typer.Option("--markdown", help="Print the field-test block.")
    ] = False,
    all_entries: Annotated[bool, typer.Option("--all", help="Include every walk.")] = False,
) -> None:
    """Record and print the after-walk journal.

    The walk is the only part of Baahar a human has to do, and the notes from it
    are the part an agent must never invent. So this command exists to make
    writing them take ten seconds:

        uv run baahar journal --outcome went --note "kept reaching for the phone"

    Then paste the output straight into the field-test section of the write-up.
    """
    valid = {"went", "shortened", "skipped"}
    if outcome is not None and outcome not in valid:
        raise typer.BadParameter(f"--outcome must be one of {sorted(valid)}")

    if outcome is not None:
        if saw is not None and journal_mod.normalise_species_seen(saw) is None:
            raise typer.BadParameter(
                f"--saw must be one of {list(journal_mod.SPECIES_SEEN_VALUES)}"
            )
        path = journal_mod.record(
            outcome,
            planned_decision=decided,
            planned_window=window,
            park=park,
            naqi=naqi,
            naqi_band=band,
            felt_c=felt_c,
            minutes_planned=planned_min,
            minutes_walked=walked_min,
            reached_for_phone=phone,
            species_suggested=species,
            species_seen=saw,
            note=note,
        )
        err.print(f"[dim]recorded -> {path}[/]")

    entries = journal_mod.load()
    if as_markdown:
        console.print()
        console.print(journal_mod.render_markdown(entries, include_all=all_entries))
        console.print()
        return

    if not entries:
        console.print()
        console.print("[dim]No walks recorded yet.[/]")
        console.print('  uv run baahar journal --outcome went --note "..."')
        console.print()
        return

    stats = journal_mod.summarise(entries)
    table = Table(title="Baahar journal", box=None)
    table.add_column("when", style="bold")
    table.add_column("said", no_wrap=True)
    table.add_column("did", no_wrap=True)
    table.add_column("NAQI", justify="right")
    table.add_column("park")
    table.add_column("phone", justify="right")
    table.add_column("note", style="dim")
    for entry in entries[-15:]:
        table.add_row(
            entry.walked_at[5:16].replace("T", " "),
            entry.planned_decision or "-",
            entry.outcome,
            f"{entry.naqi:.0f}" if entry.naqi is not None else "-",
            (entry.park or "-")[:22],
            str(entry.reached_for_phone) if entry.reached_for_phone is not None else "-",
            (entry.note or "")[:44],
        )
    console.print()
    console.print(table)
    console.print(
        f"  {stats['n_entries']} entries · {stats['walks_recorded']} walks · "
        f"{stats['total_minutes_walked']} min · {stats['times_reached_for_phone']} phone reaches"
    )
    console.print()
    console.print("  [dim]uv run baahar journal --markdown  -> paste into the write-up[/]")
    console.print()


@app.command()
def serve(
    host: Annotated[str, typer.Option()] = "127.0.0.1",
    port: Annotated[int, typer.Option()] = 8000,
    reload: Annotated[bool, typer.Option()] = False,
) -> None:
    """Start the web app (API + Pocket Mode UI)."""
    import uvicorn

    console.print(f"[cyan]Baahar[/] serving on http://{host}:{port}")
    uvicorn.run("baahar.app:app", host=host, port=port, reload=reload, log_level="info")


@app.command()
def check() -> None:
    """Show which keys and data sources are available. Never prints secrets."""
    settings = get_settings()
    console.print()
    console.print("Baahar environment", style="bold")
    console.print(f"  city              {settings.city} ({settings.lat}, {settings.lon})")
    console.print(f"  offline mode      {'on' if settings.offline else 'off'}")
    console.print("  keys present:")
    for name, present in settings.which_keys().items():
        mark = "[green]yes[/]" if present else "[dim]no[/]"
        console.print(f"    {name:<14} {mark}")
    console.print()
    console.print("  data sources:")
    for module_name in ("open-meteo forecast", "open-meteo air quality", "WAQI stations"):
        console.print(f"    {module_name:<24} keyless / optional")
    print_seasonal_status()
    console.print()
    console.print("  [dim]keys are never printed, only presence.[/]")
    console.print()


def print_seasonal_status() -> None:
    """Which months have a recorded species snapshot, and which does not.

    Worth surfacing because the answer changes monthly and the fallback is
    silent. Without this line, a snapshot that has gone stale looks exactly like
    a feature that never worked.
    """
    from . import seasonal

    names = seasonal.available_snapshots()
    console.print()
    console.print("  seasonal cues (recorded iNaturalist snapshots):")
    if not names:
        console.print("    [yellow]none recorded[/] - hand-written cues only")
        console.print("    [dim]record one: uv run python scripts/refresh_seasonal.py[/]")
        return

    now = datetime.now()
    this_month = f"blr_{now.year}_{now.month:02d}.json"
    for name in names:
        if name == this_month:
            console.print(f"    {name:<24} [green]current month[/]")
        else:
            console.print(f"    {name:<24} [dim]stale[/]")
    if this_month not in names:
        console.print(f"    [yellow]no snapshot for {now:%Y-%m} - hand-written cues only[/]")
        console.print("    [dim]record one: uv run python scripts/refresh_seasonal.py[/]")


@app.command("version")
def version_cmd() -> None:
    from . import __version__

    console.print(f"baahar {__version__}")


def main() -> None:
    _force_utf8_output()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    app()


def _force_utf8_output() -> None:
    """Make stdout/stderr decodable on Windows consoles.

    Baahar prints box-drawing characters and the Hindi name Baahar (बाहर). On a
    Windows console configured for cp1252 those bytes are not decodable, so
    redirecting output (`baahar brief > out.txt`, or piping into another process)
    crashes the reader. Replacing undecodable bytes is far better than a
    UnicodeDecodeError for a human reading a text file.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        with contextlib.suppress(ValueError, OSError):  # pragma: no cover
            reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    main()
