"""The GO / WAIT / SKIP scorer.

Implementations:

* **heuristic** -- the documented policy in :mod:`baahar.features`. Always
  available, zero heavy dependencies, fully explainable.
* **lgbm** -- tuned LightGBM classifier over the base 13-feature set.
* **ensemble** -- weighted consensus blend (LightGBM + HistGB + RF).
* **tabpfn** -- a TabPFN classifier over the feature rows in
  :mod:`baahar.features`. Optional, because it needs PyTorch.

Design rules that the eval section depends on:

* **The ML paths are never allowed to fail loudly at the user.** If a model
  is unavailable, the plan falls back to the heuristic and *says so* in
  ``scorer``/``scorer_note``/``degraded``. A judge running
  ``uv sync`` without optional extras gets a working product, not a stack trace.
* **Safety is asymmetric.** A learned model that says GO where the policy says
  SKIP is treated as a bug: the policy wins. We are not willing to let a model
  trained on forecast features talk a human into hazardous air. The
  ``skip_as_go`` eval metric measures exactly this.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from .config import REPO_ROOT, get_settings
from .features import (
    comfort_from_features,
    decision_rank,
    features_from_slot,
    heuristic_decision,
)
from .models import (
    DataSource,
    Decision,
    HourSlot,
    OutdoorPlan,
    SlotScore,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Artifact paths
# ---------------------------------------------------------------------------
DEFAULT_TABPFN_ARTIFACT = REPO_ROOT / "eval" / "artifacts" / "tabpfn_gono.pkl"
DEFAULT_LGBM_ARTIFACT = REPO_ROOT / "eval" / "artifacts" / "lgbm_gono.pkl"
DEFAULT_ENSEMBLE_ARTIFACT = REPO_ROOT / "eval" / "artifacts" / "ensemble_gono.pkl"


# ---------------------------------------------------------------------------
# Heuristic scorer
# ---------------------------------------------------------------------------
def score_heuristic(slots: Sequence[HourSlot]) -> list[SlotScore]:
    """Score every hour with the documented policy."""
    out: list[SlotScore] = []
    for slot in slots:
        decision, reasons = heuristic_decision(slot)
        features = features_from_slot(slot)
        out.append(
            SlotScore(
                time=slot.weather.time,
                decision=decision,
                comfort=comfort_from_features(features),
                reasons=reasons,
                signals=_signals(slot),
                scorer="heuristic",
            )
        )
    return out


def _signals(slot: HourSlot) -> dict[str, Any]:
    """The handful of numbers shown in the "why" panel.

    ``naqi`` here is the *effective* (conservative) value the decision was
    actually made on, so the panel cannot disagree with the recommendation.
    The two inputs behind it are included too -- a user told to stay in has a
    right to see which reading raised the number and over how many hours.
    """
    air, weather = slot.air, slot.weather
    return {
        "naqi": air.naqi_effective,
        "naqi_band": air.naqi_band,
        "naqi_instant": air.naqi,
        "naqi_trailing": air.naqi_trailing,
        "naqi_trailing_hours": air.naqi_trailing_hours,
        "dominant_pollutant": air.dominant_label,
        "pm25": air.pm25,
        "pm10": air.pm10,
        "temp_c": weather.temp_c,
        "apparent_c": weather.apparent_c,
        "precip_mm": weather.precip_mm,
        "precip_prob": weather.precip_prob,
        "humidity": weather.humidity,
        "wind_kmh": weather.wind_kmh,
        "uv_index": weather.uv_index,
    }


def _band_idx_to_decision(band_idx: int, slot: HourSlot) -> Decision:
    """Map predicted NAQI band ordinal and current weather to Decision."""
    weather = slot.weather
    precip_mm = weather.precip_mm or 0.0
    precip_prob = weather.precip_prob or 0.0
    apparent_c = weather.apparent_c if weather.apparent_c is not None else 30.0

    if band_idx >= 4:
        return Decision.SKIP
    if precip_mm >= 2.5 or precip_prob >= 70.0 or apparent_c >= 35.0:
        return Decision.SKIP
    if band_idx == 3:
        return Decision.WAIT
    if apparent_c >= 30.0 or precip_prob >= 40.0:
        return Decision.WAIT
    if not weather.is_day:
        return Decision.WAIT
    return Decision.GO


def _predict_decisions(
    model: Any,
    x: Any,
    slots: Sequence[HourSlot],
    tau_mod: float | None = None,
) -> list[Decision]:
    """Helper to convert model predictions to Decisions across 3-class, 6-band, or direct outputs."""
    import numpy as np

    if hasattr(model, "predict_proba"):
        probs = np.asarray(model.predict_proba(x))
        if probs.shape[1] == 3:
            class_indices = np.argmax(probs, axis=1)
            return _resolve_labels(class_indices, slots)
        if probs.shape[1] >= 5:
            preds = np.argmax(probs, axis=1)
            if tau_mod is not None:
                for i in range(len(preds)):
                    if preds[i] < 2 and probs[i, 2] >= tau_mod:
                        preds[i] = 2
            decisions = []
            for i, slot in enumerate(slots):
                band_idx = int(preds[i])
                decisions.append(_band_idx_to_decision(band_idx, slot))
            return decisions

    if hasattr(model, "predict"):
        preds = model.predict(x)
        decisions = []
        for i, pred in enumerate(preds):
            if isinstance(pred, (str, Decision)):
                decisions.append(_to_decision(str(pred)))
            elif isinstance(pred, (int, np.integer)):
                if pred <= 2 and getattr(model, "n_classes_", None) == 3:
                    decisions.append(TABPFN_LABELS[int(pred)])
                else:
                    decisions.append(_band_idx_to_decision(int(pred), slots[i]))
            else:
                decisions.append(Decision.WAIT)
        return decisions

    return [heuristic_decision(s)[0] for s in slots]


# ---------------------------------------------------------------------------
# LightGBM scorer
# ---------------------------------------------------------------------------
def lgbm_available() -> tuple[bool, str]:
    """Whether LightGBM is importable and available."""
    try:
        import lightgbm  # noqa: F401
        import numpy  # noqa: F401
    except ImportError as exc:
        return False, f"not installed ({exc.name or exc})"
    return True, "installed and available"


def load_lgbm_model(path: Any | None = None) -> Any | None:
    """Load a cached LightGBM classifier, or None if unavailable. Never raises."""
    import pickle
    from pathlib import Path

    raw = path or get_settings().lgbm_model_path
    candidate = Path(raw) if raw else DEFAULT_LGBM_ARTIFACT
    if not candidate.exists():
        log.info("no LightGBM artifact at %s; using the policy", candidate)
        return None
    try:
        with candidate.open("rb") as fh:
            return pickle.load(fh)
    except Exception as exc:  # noqa: BLE001
        log.warning("could not load LightGBM model from %s: %s", candidate, exc)
        return None


def save_lgbm_model(model: Any, path: Any | None = None) -> str:
    """Persist a fitted LightGBM classifier."""
    import pickle
    from pathlib import Path

    target = Path(path) if path else DEFAULT_LGBM_ARTIFACT
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as fh:
        pickle.dump(model, fh)
    return str(target)


def _model_components(model: Any) -> list[tuple[str, Any]]:
    if isinstance(model, dict):
        return [(key, model[key]) for key in ("lgb", "hgb", "rf") if key in model]
    return [("model", model)]


def _feature_order(model: Any, artifact: Any) -> tuple[str, ...]:
    from .features import (
        BASE_FEATURE_NAMES,
        COMPACT_FEATURE_NAMES,
        TABPFN_FEATURE_ORDER,
    )

    if isinstance(model, dict) and "feature_order" in model:
        order = tuple(model["feature_order"])
        known = set(COMPACT_FEATURE_NAMES) | set(TABPFN_FEATURE_ORDER) | set(BASE_FEATURE_NAMES)
        if not order or len(set(order)) != len(order) or any(n not in known for n in order):
            raise ValueError(
                f"Invalid feature_order in artifact {artifact}; re-run scripts/run_eval.py"
            )
        return order
    for _, component in _model_components(model):
        expected = getattr(component, "n_features_in_", None)
        if expected is not None:
            for order in (TABPFN_FEATURE_ORDER, BASE_FEATURE_NAMES, COMPACT_FEATURE_NAMES):
                if int(expected) == len(order):
                    return order
            raise ValueError(
                f"Artifact {artifact} expects {expected} features; supported legacy widths are "
                f"{len(TABPFN_FEATURE_ORDER)}, {len(BASE_FEATURE_NAMES)} and {len(COMPACT_FEATURE_NAMES)}; "
                "re-run scripts/run_eval.py to record feature_order"
            )
    raise ValueError(
        f"Artifact {artifact} has no feature_order or component n_features_in_; "
        "re-run scripts/run_eval.py to record the fitted feature contract"
    )


def _validate_width(model: Any, x: Any, artifact: Any) -> None:
    for name, component in _model_components(model):
        expected = getattr(component, "n_features_in_", None)
        if expected is None:
            raise ValueError(
                f"Artifact {artifact} component {name} has no n_features_in_; "
                "re-run scripts/run_eval.py with fitted components"
            )
        if x.shape[1] != int(expected):
            raise ValueError(
                f"Feature width mismatch in artifact {artifact}: component {name} expects "
                f"{expected} features, matrix has {x.shape[1]}; "
                "re-run scripts/run_eval.py to refit and save the matching feature_order"
            )


def score_lgbm(slots: Sequence[HourSlot], model: Any | None = None) -> list[SlotScore]:
    """Score hours with LightGBM, falling back per-hour to the heuristic."""
    if model is None:
        model = load_lgbm_model()

    if model is None:
        log.info("no LightGBM model available; every hour scored by policy")
        return score_heuristic(slots)

    try:
        import numpy as np
    except ImportError as exc:
        log.warning("LightGBM model found but numpy is unavailable (%s); using policy", exc)
        return score_heuristic(slots)

    artifact = get_settings().lgbm_model_path or DEFAULT_LGBM_ARTIFACT
    order = _feature_order(model, artifact)

    from .features import DEFAULT_IMPUTATION_MEDIANS, matrix_from_slots

    x = np.array(matrix_from_slots(slots, order=order), dtype="float64")
    _validate_width(model, x, artifact)
    if np.isnan(x).any():
        medians = model.get("medians") if isinstance(model, dict) and "medians" in model else None
        if medians is None:
            medians = np.array([DEFAULT_IMPUTATION_MEDIANS.get(n, 0.0) for n in order])
        inds = np.where(np.isnan(x))
        x[inds] = np.take(medians, inds[1])

    predictor = model["lgb"] if isinstance(model, dict) else model
    decisions = _predict_decisions(predictor, x, slots)

    out: list[SlotScore] = []
    for slot, decision in zip(slots, decisions, strict=True):
        policy_decision, reasons = heuristic_decision(slot)
        # Safety asymmetry: the model may not talk a user into SKIP conditions.
        if decision_rank(decision) < decision_rank(policy_decision):
            decision = policy_decision
            reasons = list(reasons) + ["Kept the policy's stricter call."]
        out.append(
            SlotScore(
                time=slot.weather.time,
                decision=decision,
                comfort=comfort_from_features(features_from_slot(slot)),
                reasons=reasons,
                signals=_signals(slot),
                scorer="lgbm",
            )
        )
    return out


# ---------------------------------------------------------------------------
# Consensus Ensemble scorer
# ---------------------------------------------------------------------------
def ensemble_available() -> tuple[bool, str]:
    """Whether LightGBM, HistGB, and RF are importable and available."""
    try:
        import lightgbm  # noqa: F401
        import numpy  # noqa: F401
        import sklearn  # noqa: F401
    except ImportError as exc:
        return False, f"not installed ({exc.name or exc})"
    return True, "installed and available"


def load_ensemble_model(path: Any | None = None) -> Any | None:
    """Load a cached Consensus Ensemble bundle, or None if unavailable. Never raises."""
    import pickle
    from pathlib import Path

    raw = path or get_settings().ensemble_model_path
    candidate = Path(raw) if raw else DEFAULT_ENSEMBLE_ARTIFACT
    if not candidate.exists():
        log.info("no Ensemble artifact at %s; using the policy", candidate)
        return None
    try:
        with candidate.open("rb") as fh:
            return pickle.load(fh)
    except Exception as exc:  # noqa: BLE001
        log.warning("could not load Ensemble model from %s: %s", candidate, exc)
        return None


def save_ensemble_model(
    model: Any, path: Any | None = None, *, feature_order: Sequence[str] | None = None
) -> str:
    """Persist a fitted Consensus Ensemble bundle."""
    import pickle
    from pathlib import Path

    model = dict(model)
    model["feature_order"] = list(
        feature_order
        if feature_order is not None
        else _feature_order(model, path or DEFAULT_ENSEMBLE_ARTIFACT)
    )
    target = Path(path) if path else DEFAULT_ENSEMBLE_ARTIFACT
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as fh:
        pickle.dump(model, fh)
    return str(target)


def score_ensemble(
    slots: Sequence[HourSlot], model: Any | None = None, tau_mod: float = 0.31
) -> list[SlotScore]:
    """Score hours with the consensus ensemble, falling back per-hour to the heuristic."""
    if model is None:
        model = load_ensemble_model()

    if model is None:
        log.info("no Ensemble model available; every hour scored by policy")
        return score_heuristic(slots)

    try:
        import numpy as np
    except ImportError as exc:
        log.warning("Ensemble model found but numpy is unavailable (%s); using policy", exc)
        return score_heuristic(slots)

    artifact = get_settings().ensemble_model_path or DEFAULT_ENSEMBLE_ARTIFACT
    order = _feature_order(model, artifact)

    from .features import DEFAULT_IMPUTATION_MEDIANS, matrix_from_slots

    x = np.array(matrix_from_slots(slots, order=order), dtype="float64")
    _validate_width(model, x, artifact)
    if np.isnan(x).any():
        medians = model.get("medians") if isinstance(model, dict) and "medians" in model else None
        if medians is None:
            medians = np.array([DEFAULT_IMPUTATION_MEDIANS.get(n, 0.0) for n in order])
        inds = np.where(np.isnan(x))
        x[inds] = np.take(medians, inds[1])

    if isinstance(model, dict) and "lgb" in model and "hgb" in model and "rf" in model:
        p_lgb = model["lgb"].predict_proba(x)
        p_hgb = model["hgb"].predict_proba(x)
        p_rf = model["rf"].predict_proba(x)

        n_classes = 6

        def _expand(p: np.ndarray, clfs: Sequence[int]) -> np.ndarray:
            full = np.zeros((p.shape[0], n_classes), dtype=np.float64)
            for idx, c in enumerate(clfs):
                if c < n_classes:
                    full[:, c] = p[:, idx]
            return full

        p_lgb_full = _expand(p_lgb, getattr(model["lgb"], "classes_", range(p_lgb.shape[1])))
        p_hgb_full = _expand(p_hgb, getattr(model["hgb"], "classes_", range(p_hgb.shape[1])))
        p_rf_full = _expand(p_rf, getattr(model["rf"], "classes_", range(p_rf.shape[1])))
        w = model.get("weights", (0.50, 0.35, 0.15))
        p_blend = w[0] * p_lgb_full + w[1] * p_hgb_full + w[2] * p_rf_full
        tau = model.get("tau_mod", tau_mod)

        preds = np.argmax(p_blend, axis=1)
        for i in range(len(preds)):
            if preds[i] < 2 and p_blend[i, 2] >= tau:
                preds[i] = 2
        decisions = [_band_idx_to_decision(int(preds[i]), slot) for i, slot in enumerate(slots)]
    else:
        decisions = _predict_decisions(model, x, slots, tau_mod=tau_mod)

    out: list[SlotScore] = []
    for slot, decision in zip(slots, decisions, strict=True):
        policy_decision, reasons = heuristic_decision(slot)
        # Safety asymmetry: the model may not talk a user into SKIP conditions.
        if decision_rank(decision) < decision_rank(policy_decision):
            decision = policy_decision
            reasons = list(reasons) + ["Kept the policy's stricter call."]
        out.append(
            SlotScore(
                time=slot.weather.time,
                decision=decision,
                comfort=comfort_from_features(features_from_slot(slot)),
                reasons=reasons,
                signals=_signals(slot),
                scorer="ensemble",
            )
        )
    return out


# ---------------------------------------------------------------------------
# TabPFN scorer
# ---------------------------------------------------------------------------
def tabpfn_available() -> tuple[bool, str]:
    """Whether the TabPFN path can run, plus a human-readable reason if not.

    Three gates, checked cheapest first:

    1. Is the package importable? (``uv sync --group ml``)
    2. Is a Prior Labs licence acceptance recorded? ``tabpfn >= 2.x`` refuses to
       download weights until ``TABPFN_TOKEN`` is set, *even though the weights
       are public on Hugging Face*. That is a licence gate rather than a
       technical one, so Baahar does not attempt to route around it.
    3. Otherwise, assume it will work and let a genuine failure surface at fit
       time, where `score_tabpfn` degrades to the policy.
    """
    try:
        import tabpfn  # noqa: F401
        from tabpfn import TabPFNClassifier  # noqa: F401
    except ImportError as exc:
        return False, f"not installed ({exc.name or exc})"
    if not get_settings().has_tabpfn_license:
        return False, "Prior Labs licence not accepted (TABPFN_TOKEN unset)"
    return True, "installed and licensed"


#: TabPFN's own CPU guard. Above ~5000 rows it refuses to fit on CPU unless this
#: is set, because inference cost grows with dataset size. Measured on this
#: machine (2026-10-06, CPU only): 6,504 rows fit in 1.6 s and 1,626 predictions
#: take 312 s, so the full eval is about five minutes -- a reasonable wait, not a
#: reason to skip the model under test.
#:
#: This is a performance default, not a licence or correctness condition. The
#: package offers the switch itself, alongside "use a GPU" and "use the hosted
#: API", so lifting it is a supported configuration.
#:
#: Set it *before* importing `tabpfn`. The guard reads a pydantic settings object
#: that snapshots values at import time, so assigning the variable afterwards is
#: silently ignored and the failure looks identical to the guard not existing.
CPU_LARGE_DATASET_ENV = "TABPFN_ALLOW_CPU_LARGE_DATASET"


def _resolve_labels(preds: Sequence[Any], slots: Sequence[HourSlot]) -> list[Decision]:
    """Map TabPFN class indices to decisions, using the ordered label list.

    TabPFN returns indices into whatever label set it was fitted with, so the
    ordering here must match :data:`TABPFN_LABELS` exactly.
    """
    out: list[Decision] = []
    for pred in preds:
        idx = int(pred) if not hasattr(pred, "item") else int(pred.item())
        try:
            out.append(TABPFN_LABELS[idx])
        except (IndexError, ValueError):
            log.warning("TabPFN returned unexpected class index %s; using heuristic", idx)
            out.append(Decision.WAIT)
    return out


#: Label order used when fitting. Frozen: the model encodes these positions.
TABPFN_LABELS: tuple[Decision, ...] = (Decision.GO, Decision.WAIT, Decision.SKIP)


def fit_tabpfn(rows: Sequence[Any], *, seed: int = 0):
    """Fit a TabPFN classifier on labelled rows.

    Kept in one place so `scripts/run_eval.py` and the live scorer fit the same
    way, and so the fitted artifact can be cached to disk for the web app.
    """
    os.environ.setdefault(CPU_LARGE_DATASET_ENV, "1")

    import numpy as np
    from tabpfn import TabPFNClassifier

    from .features import TABPFN_FEATURE_ORDER

    x = np.array(
        [[row.features[name] for name in TABPFN_FEATURE_ORDER] for row in rows],
        dtype="float32",
    )
    y = np.array([list(TABPFN_LABELS).index(_to_decision(row.label)) for row in rows])
    if np.isnan(x).any():
        from .features import DEFAULT_IMPUTATION_MEDIANS

        medians = np.array([DEFAULT_IMPUTATION_MEDIANS.get(n, 0.0) for n in TABPFN_FEATURE_ORDER])
        inds = np.where(np.isnan(x))
        x[inds] = np.take(medians, inds[1])

    clf = TabPFNClassifier(device="cpu", random_state=seed)
    clf.fit(x, y)
    return clf


def _to_decision(label: str) -> Decision:
    try:
        return Decision(label)
    except ValueError:
        return Decision.WAIT


def score_tabpfn(slots: Sequence[HourSlot], model: Any | None = None) -> list[SlotScore]:
    """Score hours with TabPFN, falling back per-hour to the heuristic.

    If the model is not fitted and no cached artifact exists, every hour falls
    back to the policy rather than failing.
    """
    if model is None:
        model = load_tabpfn_model()

    if model is None:
        log.info("no TabPFN model available; every hour scored by policy")
        return score_heuristic(slots)

    try:
        import numpy as np
    except ImportError as exc:
        log.warning("TabPFN model found but numpy is unavailable (%s); using policy", exc)
        return score_heuristic(slots)

    from .features import DEFAULT_IMPUTATION_MEDIANS, TABPFN_FEATURE_ORDER, matrix_from_slots

    expected = getattr(model, "n_features_in_", None)
    if expected is not None and int(expected) != len(TABPFN_FEATURE_ORDER):
        raise ValueError(
            f"fitted TabPFN model expects {expected} features but "
            f"baahar.features.FEATURE_NAMES defines {len(TABPFN_FEATURE_ORDER)} "
            f"({', '.join(TABPFN_FEATURE_ORDER)}). The model was fitted against a "
            "different feature set -- re-run `uv run python scripts/run_eval.py` "
            "to refit it against the current definition, or delete the artifact. "
            "This is not something to paper over by reordering columns: the "
            "values would silently mean something else."
        )

    x = np.array(
        matrix_from_slots(slots, order=TABPFN_FEATURE_ORDER),
        dtype="float32",
    )
    if np.isnan(x).any():
        medians = model.get("medians") if isinstance(model, dict) and "medians" in model else None
        if medians is None:
            medians = np.array(
                [DEFAULT_IMPUTATION_MEDIANS.get(n, 0.0) for n in TABPFN_FEATURE_ORDER]
            )
        inds = np.where(np.isnan(x))
        x[inds] = np.take(medians, inds[1])

    preds = model.predict_proba(x)
    class_idx = preds.argmax(axis=1)
    decisions = _resolve_labels(class_idx, slots)

    out: list[SlotScore] = []
    for slot, decision in zip(slots, decisions, strict=True):
        policy_decision, reasons = heuristic_decision(slot)
        # Safety asymmetry: the model may not talk a user into SKIP conditions.
        if decision_rank(decision) < decision_rank(policy_decision):
            decision = policy_decision
            reasons = list(reasons) + ["Kept the policy's stricter call."]
        out.append(
            SlotScore(
                time=slot.weather.time,
                decision=decision,
                comfort=comfort_from_features(features_from_slot(slot)),
                reasons=reasons,
                signals=_signals(slot),
                scorer="tabpfn",
            )
        )
    return out


def load_tabpfn_model(path: Any | None = None):
    """Load a cached TabPFN classifier, or ``None`` if there isn't one."""
    import pickle
    from pathlib import Path

    raw = path or get_settings().tabpfn_model_path
    candidate = Path(raw) if raw else DEFAULT_TABPFN_ARTIFACT
    if not candidate.exists():
        log.info("no TabPFN artifact at %s; using the policy", candidate)
        return None
    try:
        with candidate.open("rb") as fh:
            return pickle.load(fh)
    except Exception as exc:  # noqa: BLE001
        log.warning("could not load TabPFN model from %s: %s", candidate, exc)
        return None


def save_tabpfn_model(model: Any, path: Any | None = None) -> str:
    """Persist a fitted classifier so the web app can reuse it."""
    import pickle
    from pathlib import Path

    target = Path(path) if path else DEFAULT_TABPFN_ARTIFACT
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as fh:
        pickle.dump(model, fh)
    return str(target)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def choose_scorer(
    requested: str = "auto", *, fit_on: Sequence[Any] | None = None
) -> tuple[str, str]:
    """Resolve a scorer request into ``(scorer_name, note)``."""
    requested = (requested or "auto").lower()

    if requested == "heuristic":
        return "heuristic", "Heuristic policy requested explicitly."

    if requested == "lgbm":
        available, reason = lgbm_available()
        if not available:
            return (
                "heuristic",
                f"LightGBM requested but {reason}. Run `uv sync --group ml` to add it.",
            )
        if load_lgbm_model() is None:
            return (
                "heuristic",
                "LightGBM installed but no model artifact found; using the policy.",
            )
        return "lgbm", "LightGBM requested and model artifact loaded."

    if requested == "ensemble":
        available, reason = ensemble_available()
        if not available:
            return (
                "heuristic",
                f"Ensemble requested but {reason}. Run `uv sync --group ml` to add it.",
            )
        if load_ensemble_model() is None:
            return (
                "heuristic",
                "Ensemble installed but no model artifact found; using the policy.",
            )
        return "ensemble", "Consensus ensemble requested and model artifact loaded."

    available, reason = tabpfn_available()
    fix = (
        "Register at https://ux.priorlabs.ai, accept the licence, then set "
        "TABPFN_TOKEN in .env. See docs/NEEDS_HUMAN.md."
        if "licence" in reason
        else "Run `uv sync --group dev --group ml` to add it."
    )

    if requested == "tabpfn":
        if not available:
            return "heuristic", f"TabPFN requested but {reason}. {fix}"
        return "tabpfn", "TabPFN requested and available."

    # auto mode: prioritize ensemble artifact, then lgbm artifact, then tabpfn
    ens_avail, _ = ensemble_available()
    if ens_avail and load_ensemble_model() is not None:
        return "ensemble", "Consensus ensemble available; using fitted artifact."

    lgb_avail, _ = lgbm_available()
    if lgb_avail and load_lgbm_model() is not None:
        return "lgbm", "LightGBM available; using fitted artifact."

    if not available:
        return "heuristic", f"TabPFN {reason}; using the documented policy."
    if fit_on:
        return "tabpfn", "TabPFN available and fitted on recorded data."

    if load_tabpfn_model() is not None:
        return "tabpfn", "TabPFN available; using the model fitted by scripts/run_eval.py."
    return "heuristic", "TabPFN installed but not fitted; using the policy."


def score_slots(
    slots: Sequence[HourSlot], scorer: str = "auto"
) -> tuple[list[SlotScore], str, str]:
    """Score slots with the chosen scorer. Returns ``(scores, scorer, note)``."""
    name, note = choose_scorer(scorer)
    if name == "ensemble":
        try:
            return score_ensemble(slots), name, note
        except Exception as exc:  # noqa: BLE001
            log.warning("Ensemble scoring failed (%s); using policy", exc)
            return score_heuristic(slots), "heuristic", f"Ensemble failed ({exc}); used policy."
    if name == "lgbm":
        try:
            return score_lgbm(slots), name, note
        except Exception as exc:  # noqa: BLE001
            log.warning("LightGBM scoring failed (%s); using policy", exc)
            return score_heuristic(slots), "heuristic", f"LightGBM failed ({exc}); used policy."
    if name == "tabpfn":
        try:
            return score_tabpfn(slots), name, note
        except Exception as exc:  # noqa: BLE001
            log.warning("TabPFN scoring failed (%s); using policy", exc)
            return score_heuristic(slots), "heuristic", f"TabPFN failed ({exc}); used policy."
    return score_heuristic(slots), name, note


def display_window(
    scores: Sequence[SlotScore], best: SlotScore | None, window_hours: int
) -> list[SlotScore]:
    """The hours to show, chosen so the recommended hour is always one of them."""
    if not scores:
        return []
    if best is None:
        return list(scores[:window_hours])

    try:
        best_index = next(i for i, s in enumerate(scores) if s.time == best.time)
    except StopIteration:  # pragma: no cover - defensive
        return list(scores[:window_hours])

    if best_index < window_hours:
        return list(scores[:window_hours])

    start = max(0, best_index - window_hours + 2)
    return list(scores[start : best_index + 2])


def pick_best(scores: Sequence[SlotScore]) -> SlotScore | None:
    """Best hour to go out: GO beats WAIT beats SKIP, then comfort, then sooner."""
    if not scores:
        return None
    return sorted(
        scores,
        key=lambda s: (decision_rank(s.decision), -s.comfort, s.time),
    )[0]


def build_plan(
    slots: Sequence[HourSlot],
    *,
    city: str | None = None,
    window_hours: int | None = None,
    scorer: str = "auto",
    park: Any | None = None,
    weather_source: DataSource = DataSource.LIVE,
    air_source: DataSource = DataSource.LIVE,
    generated_at: datetime | None = None,
) -> OutdoorPlan:
    """Turn scored hours into the user-facing plan."""
    settings = get_settings()
    city = city or settings.city
    window_hours = window_hours or settings.plan_hours

    scores, scorer_name, note = score_slots(slots, scorer)
    best = pick_best(scores)

    degraded: list[str] = []
    if weather_source is DataSource.FIXTURE:
        degraded.append("weather from recorded fixture, not a live forecast")
    if air_source is DataSource.FIXTURE:
        degraded.append("air quality from recorded fixture, not a live forecast")
    if air_source is DataSource.UNAVAILABLE:
        degraded.append("air quality unavailable; NAQI unknown")
    if scorer_name == "heuristic" and scorer != "heuristic":
        degraded.append(f"heuristic scorer in use ({note})")

    best_slot: HourSlot | None = None
    if best is not None:
        for slot in slots:
            if slot.weather.time == best.time:
                best_slot = slot
                break

    if best is None:
        overall = Decision.SKIP
        headline = "No usable hours in the window."
    else:
        overall = best.decision
        headline = _headline(overall, best)

    return OutdoorPlan(
        city=city,
        generated_at=generated_at or datetime.now(tz=UTC),
        window_hours=window_hours,
        overall=overall,
        best_slot=best_slot,
        best_time=best.time if best else None,
        headline=headline,
        slots=display_window(scores, best, window_hours),
        park=park,
        scorer=scorer_name,
        scorer_note=note,
        degraded=degraded,
        weather_source=weather_source,
        air_source=air_source,
    )


def _headline(decision: Decision, best: SlotScore) -> str:
    when = best.time.strftime("%H:%M")
    if decision is Decision.GO:
        return f"Go at {when}."
    if decision is Decision.WAIT:
        # pick_best sorts GO ahead of WAIT, so a WAIT landing here means no hour
        # in the window is a GO at all. Saying "Wait for 22:00" in that case
        # reads as a recommendation for an hour we are not recommending -- the
        # user is told to hold off for the exact slot the table below marks
        # WAIT. State the absence instead.
        return f"No GO hour in this window. Best is {when}, and it is only a WAIT."
    reason = best.reasons[0] if best.reasons else "conditions are poor all window"
    return f"Skip it. {reason}"
