"""Security regressions found by review, pinned as tests.

Each test here corresponds to a defect that shipped. The comments say what the
bad behaviour looked like, because "we added a check" is not a reason and a
reviewer three months from now cannot tell whether the check is load-bearing.

All offline: ElevenLabs is mocked, the Gemini writer's HTTP call is mocked, and
nothing here touches the network.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from baahar import brief as brief_mod
from baahar.app import _audio_file, _is_loopback, app
from baahar.models import DataSource
from baahar.score import build_plan


@pytest.fixture
def go_plan(go_slot):
    from baahar.parks import park_by_id

    return build_plan(
        [go_slot],
        park=park_by_id("cubbon"),
        weather_source=DataSource.LIVE,
        air_source=DataSource.LIVE,
    )


class TestCacheClearIsLocalOnly:
    """B1: `POST /api/cache/clear` was open to any caller.

    Pair it with `/api/brief?model=gemma&voice=1` and one unauthenticated caller
    can spend the maintainer's Gemini and ElevenLabs quota at will: every call
    misses the cache and pays for two model round trips, roughly 45 s each.
    """

    def test_a_remote_caller_is_refused(self) -> None:
        client = TestClient(app, client=("203.0.113.7", 51000))
        resp = client.post("/api/cache/clear")
        assert resp.status_code == 403, resp.text
        assert "loopback" in resp.json()["detail"]

    def test_loopback_still_works_because_it_is_a_dev_tool(self) -> None:
        """The guard must not turn a local workflow into a dead end."""
        client = TestClient(app, client=("127.0.0.1", 51000))
        resp = client.post("/api/cache/clear")
        assert resp.status_code == 200, resp.text
        assert "removed" in resp.json()

    def test_ipv6_loopback_also_works(self) -> None:
        client = TestClient(app, client=("::1", 51000))
        assert client.post("/api/cache/clear").status_code == 200

    def test_a_forwarded_header_cannot_impersonate_loopback(self) -> None:
        """`X-Forwarded-For` is attacker-controlled, so it proves nothing.

        Honouring it here would make the guard decoration rather than a control.
        """
        client = TestClient(app, client=("203.0.113.7", 51000))
        resp = client.post("/api/cache/clear", headers={"X-Forwarded-For": "127.0.0.1"})
        assert resp.status_code == 403, resp.text

    @pytest.mark.parametrize(
        ("host", "expected"),
        [
            ("127.0.0.1", True),
            ("127.1.2.3", True),
            ("::1", True),
            ("203.0.113.7", False),
            ("0.0.0.0", False),
            ("", False),
            (None, False),
            # A hostname is not an address. TestClient's default peer is the
            # string "testclient", and treating that as trusted would be a
            # bypass wearing a disguise.
            ("testclient", False),
        ],
    )
    def test_loopback_detection(self, host: str | None, expected: bool) -> None:
        assert _is_loopback(host) is expected


class TestGeminiKeyIsNotInTheUrl:
    """B2: the key was sent as `?key=...`.

    Query strings are written to proxy logs, CDN access logs and crash dumps by
    default. The other two writers in the same file already used headers.
    """

    def test_the_key_travels_in_a_header(self, go_plan, monkeypatch) -> None:
        captured: dict[str, object] = {}

        def fake_post(self, url, **kwargs):
            captured["url"] = url
            captured["params"] = kwargs.get("params")
            captured["headers"] = kwargs.get("headers")
            return httpx.Response(
                200,
                json={
                    "candidates": [
                        {"content": {"parts": [{"text": "Go at six. The air is clean."}]}}
                    ]
                },
            )

        monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-a-real-credential")
        from baahar import config

        config.get_settings.cache_clear()
        try:
            monkeypatch.setattr(httpx.Client, "post", fake_post)
            brief_mod.write_gemma(go_plan)
        finally:
            config.get_settings.cache_clear()

        assert not captured.get("params"), f"key leaked into the query string: {captured}"
        assert captured["headers"] == {"x-goog-api-key": "test-key-not-a-real-credential"}
        assert "key=" not in str(captured["url"])


class TestAudioIsServedNotLeaked:
    """B3: `Briefing.audio_url` was a `file://` URI.

    It reached the public JSON as
    `file:///C:/Users/<maintainer>/.../brief_123.mp3`, which leaks the build
    layout and the Windows account name. Nothing in the front end reads the
    field, so nothing is lost by serving it over HTTP instead.
    """

    @pytest.fixture
    def fake_elevenlabs(self, monkeypatch, tmp_path):
        """Stub the TTS call and point the cache at a temp directory."""
        monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key-not-a-real-credential")
        monkeypatch.setenv("ELEVENLABS_VOICE_ID", "voice-under-test")
        monkeypatch.setattr(brief_mod, "audio_dir", lambda: tmp_path / "audio")

        def fake_post(self, url, **kwargs):
            return httpx.Response(200, content=b"ID3fake-mp3-bytes")

        monkeypatch.setattr(httpx.Client, "post", fake_post)
        from baahar import config

        config.get_settings.cache_clear()
        yield tmp_path / "audio"
        config.get_settings.cache_clear()

    def test_the_url_is_an_app_path_not_a_file_uri(self, fake_elevenlabs) -> None:
        url = brief_mod.speak("Go at six. The air is clean enough.")
        assert url is not None
        assert url.startswith(brief_mod.AUDIO_ROUTE + "/"), url
        assert "file://" not in url
        assert "Users" not in url

    def test_the_url_carries_no_build_path(self, go_plan, fake_elevenlabs) -> None:
        repo = str(Path(__file__).resolve().parents[1])
        briefing = brief_mod.generate(go_plan, writer="template", park=go_plan.park, voice=True)
        assert briefing.audio_url is not None
        assert "file://" not in briefing.audio_url
        assert repo not in briefing.audio_url
        assert "Users" not in briefing.audio_url

    def test_the_clip_is_actually_served_over_http(self, fake_elevenlabs) -> None:
        url = brief_mod.speak("Go at six. The air is clean enough.")
        assert url is not None
        resp = TestClient(app).get(url)
        assert resp.status_code == 200, resp.text
        assert resp.content == b"ID3fake-mp3-bytes"
        assert resp.headers["content-type"].startswith("audio/mpeg")


class TestVoiceFailureIsVisible:
    """Asking for a spoken briefing must never quietly produce none.

    `baahar brief --voice` against a free ElevenLabs plan answers HTTP 402. The
    original code returned None from that, the CLI printed nothing about it and
    exited 0, so the run looked successful with no audio in it. Same failure
    mode this repo has already been bitten by on the briefing writer.
    """

    def _plan_with_no_provider(self, go_plan, monkeypatch):
        from baahar import config

        monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
        monkeypatch.delenv("ELEVENLABS_VOICE_ID", raising=False)
        config.get_settings.cache_clear()

    def test_unconfigured_provider_reports_why(self, go_plan, monkeypatch) -> None:
        self._plan_with_no_provider(go_plan, monkeypatch)
        try:
            briefing = brief_mod.generate(go_plan, writer="template", park=go_plan.park, voice=True)
        finally:
            from baahar import config

            config.get_settings.cache_clear()
        assert briefing.audio_url is None
        assert briefing.note and "speech not produced" in briefing.note

    def test_paid_plan_wall_names_the_actual_cause(self, go_plan, monkeypatch) -> None:
        """HTTP 402 is not a transient fault and the reader cannot guess it."""
        import httpx

        from baahar import config

        monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key-not-a-real-credential")
        monkeypatch.setenv("ELEVENLABS_VOICE_ID", "voice-id")
        config.get_settings.cache_clear()

        class Resp:
            status_code = 402
            text = '{"detail":{"status":"paid_plan_required"}}'
            content = b""

        def fake_post(self, *a, **k):
            return Resp()

        monkeypatch.setattr(httpx.Client, "post", fake_post)
        try:
            briefing = brief_mod.generate(go_plan, writer="template", park=go_plan.park, voice=True)
        finally:
            config.get_settings.cache_clear()
        assert briefing.audio_url is None
        assert briefing.note is not None
        assert "402" in briefing.note
        assert "paid plan" in briefing.note

    def test_voice_not_requested_leaves_no_speech_note(self, go_plan) -> None:
        briefing = brief_mod.generate(go_plan, writer="template", park=go_plan.park, voice=False)
        assert briefing.audio_url is None
        assert "speech not produced" not in (briefing.note or "")

    def test_speak_result_returns_exactly_one_of_url_or_reason(self, go_plan, monkeypatch) -> None:
        self._plan_with_no_provider(go_plan, monkeypatch)
        try:
            url, reason = brief_mod.speak_result("Go at six.")
        finally:
            from baahar import config

            config.get_settings.cache_clear()
        assert url is None
        assert reason and "speech not produced" in reason

    @pytest.mark.parametrize(
        "name",
        [
            "../briefings/abc.json",
            "../../pyproject.toml",
            "../../../../../../etc/passwd",
            "..\\..\\pyproject.toml",
            "..\\..\\..\\Users\\someone\\.ssh\\id_rsa",
            "/etc/passwd",
            "C:/Windows/win.ini",
            "subdir/../../escape.mp3",
            "brief_1.mp3\\..\\..\\..\\..\\..\\..\\..\\..\\pyproject.toml",
        ],
    )
    def test_the_resolver_refuses_any_path_outside_the_cache(self, name: str) -> None:
        """B3's second half: do not trade a URL leak for a file-read hole.

        Tested against the resolver rather than only through HTTP, because
        Starlette already rejects an unescaped ``/`` in a path segment on Linux.
        That would let the HTTP-level test pass with no guard at all on CI,
        while the Windows separator is still there in production.
        """
        assert _audio_file(name) is None, name

    @pytest.mark.parametrize(
        "name",
        [
            "../briefings/abc.json",
            "../../pyproject.toml",
            "..%2f..%2fpyproject.toml",
            "..\\..\\pyproject.toml",
            "/etc/passwd",
            "C:/Windows/win.ini",
            "subdir/../../escape.mp3",
        ],
    )
    def test_a_traversal_request_is_404_over_http(self, name: str) -> None:
        assert TestClient(app).get(f"/api/audio/{name}").status_code == 404

    def test_a_missing_clip_is_404(self) -> None:
        assert TestClient(app).get("/api/audio/brief_does_not_exist.mp3").status_code == 404
