"""The after-walk journal.

These tests matter more than they look. The journal is the only path by which
real human observations enter this project, and `AGENTS.md` forbids an agent
fabricating them. So the storage and the rendering have to be boring and
trustworthy: nothing dropped, nothing invented, no crash on a hand-edited line.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from baahar.journal import (
    IST,
    SPECIES_SEEN_LABELS,
    Entry,
    Outcome,
    append,
    journal_path,
    load,
    normalise_species_seen,
    record,
    render_markdown,
    summarise,
)

WHEN = datetime(2026, 10, 6, 6, 30, tzinfo=IST)


@pytest.fixture
def jpath(tmp_path):
    return tmp_path / "journal.jsonl"


class TestStorage:
    def test_empty_journal_loads_cleanly(self, jpath) -> None:
        assert load(jpath) == []

    def test_round_trip(self, jpath) -> None:
        record(
            "went",
            planned_decision="GO",
            planned_window="06:00-07:00",
            park="Cubbon Park",
            naqi=74.0,
            naqi_band="satisfactory",
            minutes_planned=20,
            minutes_walked=18,
            reached_for_phone=3,
            note="reached for the phone a few times",
            when=WHEN,
            path=jpath,
        )
        entries = load(jpath)
        assert len(entries) == 1
        e = entries[0]
        assert e.outcome == Outcome.WENT.value
        assert e.park == "Cubbon Park"
        assert e.naqi == 74.0
        assert e.minutes_walked == 18
        assert e.reached_for_phone == 3

    def test_append_only(self, jpath) -> None:
        """History must not be rewritable by a later run."""
        for i in range(3):
            record("went", note=f"walk {i}", when=WHEN + timedelta(days=i), path=jpath)
        entries = load(jpath)
        assert len(entries) == 3
        assert [e.note for e in entries] == ["walk 0", "walk 1", "walk 2"]

    def test_one_json_object_per_line(self, jpath) -> None:
        """JSONL, so a crash mid-write cannot destroy earlier entries."""
        record("went", path=jpath)
        record("skipped", path=jpath)
        lines = jpath.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        for line in lines:
            json.loads(line)  # each line stands alone

    def test_corrupt_line_is_skipped_not_fatal(self, jpath) -> None:
        record("went", note="good", path=jpath)
        with jpath.open("a", encoding="utf-8") as fh:
            fh.write("{not json at all\n")
        record("went", note="also good", path=jpath)
        entries = load(jpath)
        assert [e.note for e in entries] == ["good", "also good"]

    def test_unknown_fields_are_preserved(self, jpath) -> None:
        """A future field must survive a round trip rather than being dropped."""
        append(
            Entry(walked_at=WHEN.isoformat(), outcome="went", note="x"),
            jpath,
        )
        raw = json.loads(jpath.read_text(encoding="utf-8").strip())
        raw["future_field"] = 42
        jpath.write_text(json.dumps(raw) + "\n", encoding="utf-8")
        assert load(jpath)[0].extra["future_field"] == 42

    def test_env_var_overrides_the_path(self, jpath, monkeypatch) -> None:
        monkeypatch.setenv("BAAHAR_JOURNAL", str(jpath))
        assert journal_path() == jpath

    def test_non_ascii_notes_survive(self, jpath) -> None:
        record("went", note="बाहर — the canopy was full of noise", path=jpath)
        assert "बाहर" in load(jpath)[0].note


class TestSummary:
    def test_counts_are_complete(self, jpath) -> None:
        record("went", minutes_walked=20, reached_for_phone=0, path=jpath)
        record("shortened", minutes_walked=8, reached_for_phone=4, path=jpath)
        record("skipped", path=jpath)
        stats = summarise(load(jpath))
        assert stats["n_entries"] == 3
        assert stats["walks_recorded"] == 2
        assert stats["total_minutes_walked"] == 28
        assert stats["times_reached_for_phone"] == 4

    def test_phone_reaches_sum_across_walks(self, jpath) -> None:
        """The one number the design claim rests on."""
        for n in (2, 5, 0):
            record("went", reached_for_phone=n, path=jpath)
        assert summarise(load(jpath))["times_reached_for_phone"] == 7

    def test_every_outcome_bucket_exists(self, jpath) -> None:
        stats = summarise(load(jpath))
        for outcome in Outcome:
            assert outcome.value in stats["counts"]


class TestMarkdown:
    def test_empty_journal_tells_you_how_to_start(self) -> None:
        out = render_markdown([])
        assert "No walks recorded" in out
        assert "baahar journal" in out

    def test_latest_entry_by_default(self, jpath) -> None:
        record("went", note="first", path=jpath)
        record("skipped", note="second", path=jpath)
        out = render_markdown(load(jpath))
        assert "second" in out
        assert "first" not in out

    def test_include_all_lists_every_walk(self, jpath) -> None:
        record("went", note="first", path=jpath)
        record("skipped", note="second", path=jpath)
        out = render_markdown(load(jpath), include_all=True)
        assert "first" in out
        assert "second" in out

    def test_includes_the_human_signals(self, jpath) -> None:
        record(
            "went",
            planned_decision="GO",
            planned_window="06:00-07:00",
            park="Cubbon Park",
            naqi=74.0,
            naqi_band="satisfactory",
            minutes_planned=20,
            minutes_walked=18,
            reached_for_phone=3,
            note="reached for it",
            when=WHEN,
            path=jpath,
        )
        out = render_markdown(load(jpath))
        for expected in (
            "Cubbon Park",
            "06:00-07:00",
            "74",
            "satisfactory",
            "18",
            "3 times",
            "reached for it",
        ):
            assert expected in out, expected

    def test_date_is_human_readable(self, jpath) -> None:
        """Regression: a GNU-only %-d format silently emitted raw ISO strings."""
        record("went", when=WHEN, path=jpath)
        out = render_markdown(load(jpath))
        assert "6 Oct 2026" in out
        assert "06:30 IST" in out
        assert "T06:30" not in out

    def test_stats_footer_only_when_more_than_one(self, jpath) -> None:
        record("went", path=jpath)
        assert "entries" not in render_markdown(load(jpath))
        record("went", path=jpath)
        assert "entries" in render_markdown(load(jpath), include_all=True)

    def test_skipped_is_a_first_class_outcome(self, jpath) -> None:
        """Not going out on a day Baahar said GO is the most useful entry."""
        record("skipped", planned_decision="GO", note="kept working", path=jpath)
        out = render_markdown(load(jpath))
        assert "Outcome:** skipped" in out
        assert "GO" in out


class TestSpeciesCue:
    """The one claim in the project with a denominator only a human can supply.

    The seasonal cue says "researchers have logged a dozen of these within 5 km".
    Whether that is *useful* depends entirely on whether a walker ends up seeing
    one, and no eval harness can answer that. These tests keep the answer
    recordable without letting a typo become a data point.
    """

    def test_species_cue_round_trips(self, jpath) -> None:
        record(
            "went",
            species_suggested="a Chocolate Pansy",
            species_seen="yes",
            path=jpath,
        )
        entries = load(jpath)
        assert entries[0].species_suggested == "a Chocolate Pansy"
        assert entries[0].species_seen == "yes"

    def test_rendered_markdown_names_both(self, jpath) -> None:
        record("went", species_suggested="a Chocolate Pansy", species_seen="yes", path=jpath)
        out = render_markdown(load(jpath))
        assert "a Chocolate Pansy" in out
        assert SPECIES_SEEN_LABELS["yes"] in out

    def test_no_species_cue_means_no_line(self, jpath) -> None:
        record("went", note="ordinary walk", path=jpath)
        assert "Species cue" not in render_markdown(load(jpath))

    @pytest.mark.parametrize(
        ("given", "expected"),
        [
            ("yes", "yes"),
            ("YES", "yes"),
            ("y", "yes"),
            ("seen", "yes"),
            ("no", "no"),
            ("n", "no"),
            ("not-seen", "no"),
            ("unrecognised", "unrecognised"),
            ("didnt-recognise", "unrecognised"),
            ("not looked", "not-looked"),
            ("", None),
            (None, None),
        ],
    )
    def test_answers_are_normalised(self, given, expected) -> None:
        assert normalise_species_seen(given) == expected

    def test_an_unrecognised_answer_is_dropped_not_stored(self, jpath) -> None:
        """A typo must not silently become an observation.

        Storing "yess" or "maybe" verbatim would put a made-up category into a
        journal that a human is supposed to trust.
        """
        assert normalise_species_seen("yess") is None
        assert normalise_species_seen("maybe") is None
        record("went", species_suggested="a Gecko", species_seen="yess", path=jpath)
        assert load(jpath)[0].species_seen is None

    def test_missing_answer_is_distinguished_from_a_no(self, jpath) -> None:
        """Suggesting a cue and not answering is not the same as answering 'no'."""
        record("went", species_suggested="a Gecko", path=jpath)
        out = render_markdown(load(jpath))
        assert "no answer recorded" in out
        assert SPECIES_SEEN_LABELS["no"] not in out

    def test_unrecognised_is_separate_from_no(self, jpath) -> None:
        """A name that did not land failed before the wildlife did."""
        assert SPECIES_SEEN_LABELS["unrecognised"] != SPECIES_SEEN_LABELS["no"]
        record(
            "went",
            species_suggested="a Wandering Glider",
            species_seen="unrecognised",
            path=jpath,
        )
        assert "did not recognise the name" in render_markdown(load(jpath))

    def test_summary_counts_the_species_answers(self, jpath) -> None:
        record("went", species_suggested="a", species_seen="yes", path=jpath)
        record("went", species_suggested="b", species_seen="no", path=jpath)
        record("went", species_suggested="c", species_seen="yes", path=jpath)
        record("went", path=jpath)  # no cue at all
        stats = summarise(load(jpath))
        assert stats["species_asked"] == 3
        assert stats["species_sightings"]["yes"] == 2
        assert stats["species_sightings"]["no"] == 1

    def test_no_percentage_before_three_walks(self, jpath) -> None:
        """A rate off one walk is the exact fabrication RESULTS.md refuses.

        One walk where someone saw the butterfly is not a 100% success rate. It is
        an anecdote, and the rendered output should not dress it as a rate.
        """
        record("went", species_suggested="a Chocolate Pansy", species_seen="yes", path=jpath)
        out = render_markdown(load(jpath))
        assert "%" not in out
        assert "100%" not in out

    def test_two_walks_still_no_percentage(self, jpath) -> None:
        record("went", species_suggested="a", species_seen="yes", path=jpath)
        record("went", species_suggested="b", species_seen="yes", path=jpath)
        out = render_markdown(load(jpath), include_all=True)
        assert "100%" not in out

    def test_three_walks_report_a_rate_with_the_caveat(self, jpath) -> None:
        record("went", species_suggested="a", species_seen="yes", path=jpath)
        record("went", species_suggested="b", species_seen="no", path=jpath)
        record("went", species_suggested="c", species_seen="yes", path=jpath)
        out = render_markdown(load(jpath), include_all=True)
        assert "Seen on 2 of them (67%)" in out
        assert "small denominator" in out
        assert "not as a benchmark" in out

    def test_the_rate_says_so_when_nothing_was_seen(self, jpath) -> None:
        """A 0% result must read as data, not as an error."""
        for _ in range(3):
            record("went", species_suggested="a", species_seen="no", path=jpath)
        out = render_markdown(load(jpath), include_all=True)
        assert "Seen on 0 of them (0%)" in out
        assert "small denominator" in out

    def test_older_entries_without_the_field_still_load(self, jpath) -> None:
        """Journal entries predate these fields; they must not break the reader."""
        jpath.write_text(
            json.dumps(
                {
                    "walked_at": WHEN.isoformat(),
                    "outcome": "went",
                    "note": "an older entry",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        entries = load(jpath)
        assert entries[0].species_suggested is None
        assert entries[0].species_seen is None
        assert "Species cue" not in render_markdown(entries)
