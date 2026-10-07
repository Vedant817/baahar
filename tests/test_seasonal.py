"""Tests for the seasonal cue layer.

The honesty rules in `baahar.seasonal` are the whole point of this module, so
they are tested as behaviour rather than left as documentation. If someone
rewrites the cue wording to be punchier, the phrase tests below are what stop
it.

No test here touches the network. The committed snapshot under `data/seasonal/`
is a recorded real response from the iNaturalist API, treated as a fixture in
exactly the same way `data/samples/` is.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from baahar import seasonal
from baahar.app import app
from baahar.models import DataSource, Decision
from baahar.pocket import (
    alternate_cues,
    briefing_cue,
    build_pocket,
    cue_evidence,
    cue_pool,
)
from baahar.score import build_plan

# Phrases that would turn a fact about the observation record into a promise to
# the reader. A record means someone logged it, not that the reader will see it.
#
# Checked against the instruction only. The provenance line has to *contain* the
# phrase "not that you will see it" in order to disclaim exactly this, so the same
# list cannot be applied to both.
FORBIDDEN_IN_CUE = (
    "you will see",
    "you'll see",
    "you can definitely",
    "guaranteed",
    "definitely see",
    "will spot",
    "there is a",
    "there are",
    "always here",
    "easy to spot",
    "research grade",
)

# The month the committed snapshot covers. BASE in conftest is 2026-10-06.
SNAPSHOT_YEAR = 2026
SNAPSHOT_MONTH = 10


def _read_committed_snapshot() -> dict:
    path = seasonal.SEASONAL_DIR / f"blr_{SNAPSHOT_YEAR}_{SNAPSHOT_MONTH:02d}.json"
    assert path.exists(), (
        f"the committed seasonal snapshot is missing: {path}. "
        "Re-record it with `uv run python scripts/refresh_seasonal.py`."
    )
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _clear_cache():
    """`load_snapshot` is memoised; a test that fakes a file must not leak."""
    seasonal.load_snapshot.cache_clear()
    yield
    seasonal.load_snapshot.cache_clear()


@pytest.fixture
def go_plan(go_slot, cubbon):
    return build_plan(
        [go_slot],
        park=cubbon,
        weather_source=DataSource.LIVE,
        air_source=DataSource.LIVE,
    )


# ── The committed fixture is itself a contract ───────────────────────────────


class TestCommittedSnapshot:
    def test_snapshot_is_committed_and_populated(self) -> None:
        payload = _read_committed_snapshot()
        assert payload["city"].lower().startswith("bengaluru")
        assert payload["radius_km"] > 0
        assert payload["observations_examined"] > 0
        assert len(payload["species"]) >= 3

    def test_snapshot_records_the_query_that_produced_it(self) -> None:
        """A claim nobody can re-check is a rumour."""
        payload = _read_committed_snapshot()
        query = payload["query"]
        assert query["api"].startswith("https://api.inaturalist.org/")
        params = query["params"]
        assert params["quality_grade"] == "research"
        assert params["radius"] > 0
        assert params["month"] == SNAPSHOT_MONTH

    def test_every_species_entry_is_self_describing(self) -> None:
        payload = _read_committed_snapshot()
        for entry in payload["species"]:
            assert entry["id"] > 0
            assert entry["name"]
            assert entry["preferred_common_name"]
            assert entry["observations"] >= 1
            assert entry.get("order"), f"{entry['name']} has no taxonomic order"

    def test_snapshot_states_what_a_record_does_not_mean(self) -> None:
        payload = _read_committed_snapshot()
        note = payload["honesty_note"].lower()
        assert "not" in note
        assert "research grade" in note

    def test_species_are_diversified_across_taxonomic_groups(self) -> None:
        """Three butterflies in a row is a worse walk than three different things.

        This is an editorial rule, so it is a test rather than a preference.
        """
        payload = _read_committed_snapshot()
        orders = [e.get("order") for e in payload["species"]]
        assert len(orders) == len(set(orders)), f"duplicate orders in snapshot: {orders}"

    def test_snapshot_is_committed_not_built_at_runtime(self) -> None:
        """It must be in the repo, or the offline path silently loses its cues."""
        assert seasonal.SEASONAL_DIR.exists()
        assert list(seasonal.SEASONAL_DIR.glob("blr_*.json"))


class TestCheckCommand:
    def test_check_reports_the_recorded_snapshots(self) -> None:
        """`baahar check` is how a stale snapshot becomes visible.

        Without this, a snapshot that expired last month looks exactly like a
        feature that never worked, because the fallback is silent by design.
        """
        from typer.testing import CliRunner

        from baahar.cli import app

        result = CliRunner().invoke(app, ["check"])
        assert result.exit_code == 0, result.output
        out = result.output
        assert "seasonal cues" in out
        assert f"blr_{SNAPSHOT_YEAR}_{SNAPSHOT_MONTH:02d}.json" in out

    def test_check_never_prints_a_secret_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from typer.testing import CliRunner

        from baahar.cli import app

        monkeypatch.setenv("GEMINI_API_KEY", "sentinel-super-secret-key-12345")
        out = CliRunner().invoke(app, ["check"]).output
        assert "keys are never printed" in out
        assert "sentinel-super-secret-key-12345" not in out


# ── Wording ──────────────────────────────────────────────────────────────────


class TestCueWording:
    def test_cues_come_from_the_committed_snapshot(self) -> None:
        cues = seasonal.cues_for(year=SNAPSHOT_YEAR, month=SNAPSHOT_MONTH, limit=3)
        assert len(cues) == 3
        assert all(c.common_name for c in cues)
        assert all(c.scientific_name for c in cues)

    def test_no_cue_promises_a_sighting(self) -> None:
        cues = seasonal.cues_for(year=SNAPSHOT_YEAR, month=SNAPSHOT_MONTH, limit=8)
        assert cues
        for cue in cues:
            for phrase in FORBIDDEN_IN_CUE:
                assert phrase not in cue.text.lower(), f"overclaims: {phrase!r} in {cue.text!r}"

    def test_evidence_disclaims_the_promise_it_must_disclaim(self) -> None:
        """The disclaimer contains the very words banned in an instruction.

        Asserted as a required substring rather than a forbidden one, because
        "not that you will see it" is the entire job of that line.
        """
        cues = seasonal.cues_for(year=SNAPSHOT_YEAR, month=SNAPSHOT_MONTH, limit=8)
        for cue in cues:
            assert "not that you will see it" in cue.evidence

    def test_instruction_stays_one_short_line(self) -> None:
        """The screen's own rule: one instruction, in large type.

        The statistics live in `evidence`, shown small underneath. A four-line cue
        with a footnote in the middle of it is a readout, not an instruction.
        """
        cues = seasonal.cues_for(year=SNAPSHOT_YEAR, month=SNAPSHOT_MONTH, limit=8)
        for cue in cues:
            assert len(cue.text) <= 45, f"cue too long to read at a glance: {cue.text!r}"
            assert "\n" not in cue.text
            assert cue.text.startswith("Look for ")
            assert cue.text.endswith(".")

    def test_evidence_carries_the_numbers_and_the_source(self) -> None:
        """A cue with no number and no source is just a vibe."""
        cues = seasonal.cues_for(year=SNAPSHOT_YEAR, month=SNAPSHOT_MONTH, limit=8)
        for cue in cues:
            lowered = cue.evidence.lower()
            assert "research grade" in lowered
            assert "km" in lowered
            assert "not that you will see" in lowered
            assert cue.source_url.startswith("https://www.inaturalist.org/")

    def test_instruction_carries_no_statistics(self) -> None:
        """The count belongs in the footnote, not in the thing you read."""
        cues = seasonal.cues_for(year=SNAPSHOT_YEAR, month=SNAPSHOT_MONTH, limit=8)
        for cue in cues:
            assert "km" not in cue.text
            assert str(cue.observations) not in cue.text

    def test_evidence_for_resolves_the_right_species(self) -> None:
        cues = seasonal.cues_for(year=SNAPSHOT_YEAR, month=SNAPSHOT_MONTH, limit=4)
        for cue in cues:
            assert seasonal.evidence_for(cue.text) == cue.evidence

    def test_evidence_for_returns_nothing_for_a_hand_written_cue(self) -> None:
        assert (
            seasonal.evidence_for("Listen for the first two birds, then ignore the traffic.") == ""
        )

    def test_count_phrasing_matches_the_record_count(self) -> None:
        assert seasonal._fmt_count(1) == "at least one"
        assert seasonal._fmt_count(3) == "a couple of"
        assert seasonal._fmt_count(6) == "several"
        assert seasonal._fmt_count(14) == "around a dozen"
        assert seasonal._fmt_count(40) == "dozens of"
        assert seasonal._fmt_count(300) == "over a hundred"

    def test_article_agrees_with_the_species_name(self) -> None:
        assert seasonal._article("Brahminy Kite") == "a"
        assert seasonal._article("Indian Red Bug") == "an"
        assert seasonal._article("Asian Common Toad") == "an"

    def test_vowel_starting_species_reads_correctly(self) -> None:
        """Regression guard: the snapshot once produced 'a Indian Red Bug'."""
        payload = _read_committed_snapshot()
        for entry in payload["species"]:
            common = entry["preferred_common_name"]
            expected = "an" if common[0].lower() in "aeiou" else "a"
            assert seasonal._article(common) == expected

    def test_scientific_name_is_kept_for_verification(self) -> None:
        """Common names are ambiguous; the binomial is what a reader can check."""
        cues = seasonal.cues_for(year=SNAPSHOT_YEAR, month=SNAPSHOT_MONTH, limit=8)
        for cue in cues:
            assert " " in cue.scientific_name, cue.scientific_name
            assert cue.taxon_id > 0


# ── Radius honesty ───────────────────────────────────────────────────────────


class TestRadius:
    def test_requested_radius_is_clamped_to_the_snapshot(self) -> None:
        """Asking for 50 km must not turn 5 km of evidence into a 50 km claim."""
        cues = seasonal.cues_for(year=SNAPSHOT_YEAR, month=SNAPSHOT_MONTH, limit=1, radius_km=50.0)
        assert cues
        assert cues[0].radius_km == 5.0
        assert "5 km" in cues[0].evidence
        assert "50 km" not in cues[0].evidence

    def test_smaller_radius_is_honoured(self) -> None:
        cues = seasonal.cues_for(year=SNAPSHOT_YEAR, month=SNAPSHOT_MONTH, limit=1, radius_km=2.0)
        assert cues[0].radius_km == 2.0
        assert "2 km" in cues[0].evidence

    def test_evidence_names_the_place_the_radius_was_measured_from(self) -> None:
        cues = seasonal.cues_for(year=SNAPSHOT_YEAR, month=SNAPSHOT_MONTH, limit=1)
        assert cues[0].anchor.lower().startswith("bengaluru")
        assert "bengaluru" in cues[0].evidence.lower()


# ── Missing and malformed data ───────────────────────────────────────────────


class TestDegradation:
    def test_month_with_no_snapshot_returns_empty(self) -> None:
        assert seasonal.cues_for(year=1999, month=1) == []

    def test_empty_snapshot_returns_no_cues(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(seasonal, "SEASONAL_DIR", tmp_path)
        (tmp_path / "blr_2026_10.json").write_text(
            json.dumps({"city": "Bengaluru", "species": []}), encoding="utf-8"
        )
        assert seasonal.cues_for(year=2026, month=10) == []

    def test_corrupt_snapshot_is_survivable(self, tmp_path, monkeypatch) -> None:
        """A truncated file must not take the whole screen down."""
        monkeypatch.setattr(seasonal, "SEASONAL_DIR", tmp_path)
        (tmp_path / "blr_2026_10.json").write_text("{not json", encoding="utf-8")
        assert seasonal.cues_for(year=2026, month=10) == []

    def test_entries_missing_fields_are_skipped_not_fatal(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(seasonal, "SEASONAL_DIR", tmp_path)
        (tmp_path / "blr_2026_10.json").write_text(
            json.dumps(
                {
                    "city": "Bengaluru",
                    "radius_km": 5,
                    "species": [
                        {"id": 0, "name": "X", "preferred_common_name": "Y", "observations": 3},
                        {"id": 5, "name": "Zebra sp.", "observations": 2},  # no common name
                        {"id": 6, "preferred_common_name": "Nameless sp."},  # no count
                        {
                            "id": 7,
                            "name": "Vulpes",
                            "preferred_common_name": "Red Fox",
                            "observations": 4,
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        cues = seasonal.cues_for(year=2026, month=10)
        assert [c.common_name for c in cues] == ["Red Fox"]

    def test_available_snapshots_lists_files(self) -> None:
        assert f"blr_{SNAPSHOT_YEAR}_{SNAPSHOT_MONTH:02d}.json" in seasonal.available_snapshots()

    def test_snapshot_path_matches_the_convention(self) -> None:
        assert seasonal.snapshot_path(2026, 10).name == "blr_2026_10.json"


# ── Integration with Pocket Mode ─────────────────────────────────────────────


class TestPocketIntegration:
    def test_seasonal_cues_appear_in_the_pool(self, go_plan) -> None:
        assert any(c.tag == "seasonal" for c in cue_pool(go_plan))

    def test_hand_written_cues_outrank_seasonal_ones(self, go_plan) -> None:
        """A condition-matched cue must never be displaced by a species.

        'Find the coolest patch of shade' is the instruction that keeps someone
        safe in 34 degree heat. It comes first for that reason.
        """
        pool = cue_pool(go_plan)
        first_seasonal = next(i for i, c in enumerate(pool) if c.tag == "seasonal")
        assert first_seasonal > 0
        assert pool[0].tag != "seasonal"

    def test_condition_cues_come_first_as_a_block(self, go_plan) -> None:
        tags = [c.tag for c in cue_pool(go_plan)]
        first_seasonal = tags.index("seasonal")
        assert "seasonal" not in tags[:first_seasonal]

    def test_briefing_cue_is_never_a_species_claim(self, go_plan) -> None:
        """Keeps `eval/RESULTS.md` section B describing the prompt that ships.

        An LLM asked to include a species line will restate it more confidently.
        The fix is to never give it one.
        """
        cue = briefing_cue(go_plan)
        pool = cue_pool(go_plan)
        assert cue == pool[0].text
        assert pool[0].tag != "seasonal"
        for phrase in ("iNaturalist", "research grade", "Look for"):
            assert phrase not in cue

    def test_briefing_cue_stays_hand_written_without_a_snapshot(
        self, go_plan, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setattr(seasonal, "SEASONAL_DIR", tmp_path)
        seasonal.load_snapshot.cache_clear()
        assert briefing_cue(go_plan)
        assert all(c.tag != "seasonal" for c in cue_pool(go_plan))

    def test_pocket_note_is_empty_while_a_hand_written_cue_is_shown(self, go_plan) -> None:
        """The first cue is a hand-written one, so it gets no data-source line.

        The seasonal cues are still reachable, through `cue_evidence`.
        """
        pocket = build_pocket(go_plan)
        assert pocket.seasonal_note == ""
        assert pocket.notice_this == briefing_cue(go_plan)
        assert pocket.notice_this.startswith("Listen")

    def test_pocket_note_appears_once_a_seasonal_cue_is_the_notice(self, go_plan) -> None:
        seasonal_cue = next(c for c in cue_pool(go_plan) if c.tag == "seasonal")
        note = seasonal.evidence_for(seasonal_cue.text)
        assert "research grade" in note
        assert "not that you will see it" in note

    def test_pocket_carries_no_credit_line_without_a_snapshot(
        self, go_plan, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setattr(seasonal, "SEASONAL_DIR", tmp_path)
        seasonal.load_snapshot.cache_clear()
        pocket = build_pocket(go_plan)
        assert pocket.seasonal_note == ""
        assert all(c.tag != "seasonal" for c in cue_pool(go_plan))
        assert cue_evidence(go_plan) == {}

    def test_shuffle_eventually_reaches_the_seasonal_cues(self, go_plan) -> None:
        """Regression guard: the seasonal cues were once unreachable.

        The web UI cycles through `cues_remaining`, so returning only the first
        two hand-written cues left the species suggestions permanently off-screen.
        """
        seasonal_texts = [c.text for c in cue_pool(go_plan) if c.tag == "seasonal"]
        assert seasonal_texts, "expected seasonal cues in the pool"
        shown = alternate_cues(go_plan)
        for text in seasonal_texts:
            assert text in shown

    def test_unbounded_shuffle_returns_the_whole_remainder(self, go_plan) -> None:
        pool = cue_pool(go_plan)
        assert alternate_cues(go_plan) == [c.text for c in pool[1:]]

    def test_shuffle_count_is_respected_when_given(self, go_plan) -> None:
        assert len(alternate_cues(go_plan, count=2)) == 2

    def test_shuffle_still_works_with_no_snapshot(self, go_plan, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(seasonal, "SEASONAL_DIR", tmp_path)
        seasonal.load_snapshot.cache_clear()
        assert alternate_cues(go_plan, count=2)

    def test_hazardous_plan_does_not_get_species_cues(self, hazardous_slot) -> None:
        """Safety framing outranks novelty, always."""
        from baahar.parks import park_by_id

        plan = build_plan(
            [hazardous_slot],
            park=park_by_id("hesaraghatta"),
            weather_source=DataSource.LIVE,
            air_source=DataSource.LIVE,
        )
        pool = cue_pool(plan)
        assert pool
        assert all(c.tag == "air" for c in pool)

    def test_heat_plan_does_not_get_species_cues(self, slot) -> None:
        """33 degree apparent heat wins the screen over a butterfly."""
        hot = slot(0, temp_c=36.0, apparent_c=34.0, pm25=20.0, is_day=1)
        plan = build_plan([hot])
        pool = cue_pool(plan)
        assert pool
        assert all(c.tag == "heat" for c in pool)
        assert cue_evidence(plan) == {}

    def test_rain_plan_still_gets_species_cues(self, slot) -> None:
        """Rain cues are atmospheric, not protective, so they do not suppress.

        Documented as a deliberate choice rather than an oversight. 30% rain
        probability is the boundary case: the rain cue activates at >=30 and the
        decision is still a GO, so this is the one real shape where the two rules
        disagree.
        """
        wet = slot(0, temp_c=26.0, apparent_c=28.0, precip_prob=30.0, pm25=20.0, is_day=1)
        plan = build_plan([wet])
        assert plan.overall is Decision.GO
        pool = cue_pool(plan)
        assert pool[0].tag == "rain"
        assert any(c.tag == "seasonal" for c in pool)

    def test_wait_plan_does_not_get_species_cues(self, slot) -> None:
        """There is no walk yet, so there is nothing for a species cue to be about."""
        wet = slot(0, temp_c=26.0, apparent_c=28.0, precip_prob=80.0, pm25=20.0, is_day=1)
        plan = build_plan([wet])
        assert plan.overall is Decision.WAIT
        assert all(c.tag != "seasonal" for c in cue_pool(plan))


# ── The API contract the front end depends on ────────────────────────────────


class TestApiContract:
    @pytest.fixture
    def client(self, monkeypatch):
        # Replay the recorded day from its start. Wall-clock slicing can select
        # a rainy afternoon instead, making these morning GO contract tests
        # fail depending on when pytest runs.
        from baahar import air, weather
        from baahar.models import slice_from_now

        def recorded_start(items, hours):
            return slice_from_now(items, hours, now=items[0].time) if items else []

        monkeypatch.setattr(air, "slice_from_now", recorded_start)
        monkeypatch.setattr(weather, "slice_from_now", recorded_start)
        return TestClient(app)

    def test_cue_tags_align_with_cues_in_order(self, client) -> None:
        """The UI indexes `cue_tags[i]` against `cues[i]`.

        A mismatch here would put an iNaturalist credit line under a hand-written
        cue, so it is worth an explicit test rather than a visual check.
        """
        resp = client.get("/api/brief", params={"offline": "true", "model": "template"})
        assert resp.status_code == 200
        body = resp.json()
        cues = [body["pocket"]["notice_this"], *body["meta"]["cues_remaining"]]
        tags = body["meta"]["cue_tags"]
        assert len(cues) == len(tags)
        assert tags[:3] == ["morning"] * 3
        assert "seasonal" in tags
        for text, tag in zip(cues, tags, strict=True):
            if tag == "seasonal":
                assert text.startswith("Look for ")
                assert body["meta"]["cue_evidence"][text]

    def test_evidence_mapping_covers_every_seasonal_cue(self, client) -> None:
        body = client.get("/api/brief", params={"offline": "true", "model": "template"}).json()
        evidence = body["meta"]["cue_evidence"]
        seasonal_cues = [
            c
            for c, t in zip(
                [body["pocket"]["notice_this"], *body["meta"]["cues_remaining"]],
                body["meta"]["cue_tags"],
                strict=True,
            )
            if t == "seasonal"
        ]
        assert seasonal_cues
        for text in seasonal_cues:
            note = evidence[text]
            assert "research grade" in note
            assert "not that you will see" in note

    def test_hand_written_cues_have_no_evidence_entry(self, client) -> None:
        """Hand-written lines are the author's, so they get no data-source line."""
        body = client.get("/api/brief", params={"offline": "true", "model": "template"}).json()
        evidence = body["meta"]["cue_evidence"]
        cues = [body["pocket"]["notice_this"], *body["meta"]["cues_remaining"]]
        tags = body["meta"]["cue_tags"]
        for text, tag in zip(cues, tags, strict=True):
            if tag != "seasonal":
                assert text not in evidence

    def test_pocket_note_is_empty_for_a_hand_written_notice(self, client) -> None:
        """The headline cue is hand-written, so the payload credits no source."""
        body = client.get("/api/brief", params={"offline": "true", "model": "template"}).json()
        assert body["pocket"]["seasonal_note"] == ""

    def test_evidence_mapping_is_the_only_way_to_the_credit(self, client) -> None:
        """The shuffle changes the visible cue without a new payload, so the
        credit has to be resolvable per cue rather than only for `notice_this`.
        """
        body = client.get("/api/brief", params={"offline": "true", "model": "template"}).json()
        assert body["meta"]["cue_evidence"]

    def test_briefing_text_contains_no_species_claim(self, client) -> None:
        """The writer never sees a seasonal cue, so it cannot amplify one."""
        body = client.get("/api/brief", params={"offline": "true", "model": "template"}).json()
        text = body["briefing"]["text"]
        for phrase in ("iNaturalist", "research grade", "Pansy", "Gecko", "Look for"):
            assert phrase not in text

    def test_offline_mode_still_serves_seasonal_cues(self, client) -> None:
        """Offline means no network, not less product."""
        body = client.get("/api/brief", params={"offline": "true", "model": "template"}).json()
        assert body["meta"]["cue_tags"].count("seasonal") >= 1


# ── The recording script's pure logic ────────────────────────────────────────


class TestTally:
    def test_tally_groups_by_taxon_and_drops_unverified(self) -> None:
        observations = [
            {
                "taxon": {
                    "id": 7,
                    "name": "Haliastur indus",
                    "preferred_common_name": "Brahminy Kite",
                    "rank": "species",
                },
                "num_identification_agreements": 3,
            },
            {
                "taxon": {
                    "id": 7,
                    "name": "Haliastur indus",
                    "preferred_common_name": "Brahminy Kite",
                    "rank": "species",
                },
                "num_identification_agreements": 5,
            },
            {
                "taxon": {
                    "id": 8,
                    "name": "Corvus splendens",
                    "preferred_common_name": "Large Crow",
                    "rank": "species",
                },
                # Nobody has agreed with this ID, so it is not evidence.
                "num_identification_agreements": 0,
            },
        ]
        species = seasonal.tally(observations)
        assert [s["preferred_common_name"] for s in species] == ["Brahminy Kite"]
        assert species[0]["observations"] == 2
        assert species[0]["best_agreements"] == 5

    def test_tally_drops_names_that_collide_with_hand_written_cues(self) -> None:
        observations = [
            {
                "taxon": {
                    "id": 9,
                    "name": "X y",
                    "preferred_common_name": "Unknown Bird",
                    "rank": "species",
                },
                "num_identification_agreements": 4,
            }
        ]
        assert seasonal.tally(observations) == []

    def test_tally_orders_by_count(self) -> None:
        def obs(taxon_id: int, name: str, common: str, agreements: int) -> dict:
            return {
                "taxon": {"id": taxon_id, "name": name, "preferred_common_name": common},
                "num_identification_agreements": agreements,
            }

        species = seasonal.tally(
            [
                obs(1, "A a", "Alpha", 2),
                obs(2, "B b", "Beta", 2),
                obs(3, "C c", "Gamma", 2),
                obs(3, "C c", "Gamma", 2),
                obs(3, "C c", "Gamma", 2),
            ]
        )
        assert species[0]["preferred_common_name"] == "Gamma"
        assert [s["observations"] for s in species] == [3, 1, 1]

    def test_tally_breaks_count_ties_alphabetically(self) -> None:
        """Deterministic output, so re-recording a snapshot is reproducible."""
        observations = [
            {
                "taxon": {"id": 2, "name": "B b", "preferred_common_name": "Beta"},
                "num_identification_agreements": 1,
            },
            {
                "taxon": {"id": 1, "name": "A a", "preferred_common_name": "Alpha"},
                "num_identification_agreements": 1,
            },
        ]
        assert [s["preferred_common_name"] for s in seasonal.tally(observations)] == [
            "Alpha",
            "Beta",
        ]

    def test_tally_drops_records_with_no_taxon_id(self) -> None:
        observations = [
            {
                "taxon": {"id": 0, "name": "X x", "preferred_common_name": "Nameless"},
                "num_identification_agreements": 3,
            }
        ]
        assert seasonal.tally(observations) == []

    def test_tally_survives_entries_with_no_taxon(self) -> None:
        assert seasonal.tally([{}, {"taxon": None}, {"taxon": {}}]) == []

    def test_tally_handles_an_empty_batch(self) -> None:
        assert seasonal.tally([]) == []
