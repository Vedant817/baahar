"""Opt-in private Modal writer; no local model weights or training dependencies.

The caller must enforce the briefing contract on the returned draft. Recorded
inference fixtures belong in data/samples only after an actual cloud response;
an unavailable cloud writer raises UpstreamError for the caller's honest fallback.
"""

from __future__ import annotations

import importlib
import os
import re
from contextlib import suppress
from typing import Any

from .briefing_contract import build_contract_case
from .http_client import UpstreamError

APP_NAME = "baahar-briefing-private"
CLASS_NAME = "BriefingModel"
RESPONSE_TIMEOUT = 60
CANDIDATES = {
    "qwen3_4b": (
        "Qwen/Qwen3-4B-Instruct-2507",
        "cdbee75f17c01a7cc42f958dc650907174af0554",
    ),
    "qwen25_7b": (
        "Qwen/Qwen2.5-7B-Instruct",
        "a09a35458c702b33eeacc393d103063234e8bc28",
    ),
}


def validate_selection(run_id: str, candidate: str) -> tuple[str, str]:
    """Restrict SDK parameters and artifact paths to explicit run identities."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", run_id):
        raise UpstreamError("Modal briefing run is missing or invalid.")
    if candidate not in CANDIDATES:
        raise UpstreamError("Modal briefing candidate is missing or unsupported.")
    return CANDIDATES[candidate]


def generate_modal(case: dict[str, Any]) -> dict[str, Any]:
    """Submit once, wait at most 60 seconds for its result, cancel on timeout.

    Uses Modal's authenticated Python SDK, without a public web endpoint or a
    separate inference key. Vendor errors deliberately never reach the user.
    """
    run_id = os.getenv("BAAHAR_MODAL_RUN_ID", "")
    candidate = os.getenv("BAAHAR_MODAL_CANDIDATE", "")
    model, revision = validate_selection(run_id, candidate)
    try:
        modal = importlib.import_module("modal")
    except ImportError:
        raise UpstreamError(
            "Modal writer is unavailable; install the optional modal group."
        ) from None
    call = None
    try:
        cls = modal.Cls.from_name(APP_NAME, CLASS_NAME)
        worker = cls(run_id=run_id, candidate=candidate)
        call = worker.generate.spawn(case["facts"])
        response = call.get(timeout=RESPONSE_TIMEOUT)
    except Exception as exc:
        timed_out = isinstance(exc, TimeoutError) or type(exc).__name__ == "TimeoutError"
        if timed_out and call is not None:
            with suppress(Exception):
                call.cancel(terminate_containers=True)
        if timed_out:
            raise UpstreamError(
                "Modal briefing timed out; cancellation requested, no retry."
            ) from None
        raise UpstreamError(
            "Modal briefing unavailable; check authentication and deployment."
        ) from None
    if (
        not isinstance(response, dict)
        or response.get("run_id") != run_id
        or response.get("candidate") != candidate
        or response.get("model") != model
        or response.get("revision") != revision
        or not isinstance(response.get("raw_text"), str)
        or not response["raw_text"].strip()
        or response.get("terminated") is not True
    ):
        raise UpstreamError("Modal briefing returned an invalid or unfinished draft.")
    return response


def write_modal(plan: Any, *, park: Any = None, notice_this: str | None = None) -> str:
    """Return a raw grounded draft; optional untrusted notice text is excluded."""
    return generate_modal(build_contract_case(plan, park))["raw_text"]
