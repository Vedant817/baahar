"""Keep the recorded historical checker counterexample rejected."""

import json

from baahar.briefing_contract import evaluate
from baahar.config import REPO_ROOT


def test_historical_skip_walking_now_counterexample_is_rejected():
    evidence = json.loads((REPO_ROOT / "eval/raw/runtime_boundary_v2.json").read_text())
    verdict = evaluate(evidence["counterexample"], {"facts": evidence["facts"]})
    assert not verdict["accepted"]
    assert "unsafe_invitation" in verdict["errors"]
