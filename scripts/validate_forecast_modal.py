"""Hosted rolling temporal diagnostics; never overwrite serving artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "eval/raw/forecast_rolling_manifest.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def remote_validate(manifest):
    from datetime import datetime, timedelta
    from importlib.metadata import version

    sys.path[:0] = ["/opt/src", "/opt/scripts"]
    import run_eval as ev

    rows_path = Path("/opt/rows.jsonl")
    if digest(rows_path) != manifest["rows_sha256"]:
        raise ValueError("Dataset hash changed")
    # Evaluation fits must never replace a deployed model.
    ev.save_ensemble_model = lambda *args, **kwargs: "NOT_SAVED_DIAGNOSTIC"
    ev.save_lgbm_model = lambda *args, **kwargs: "NOT_SAVED_DIAGNOSTIC"
    rows = ev.load_rows(rows_path)
    x, y = ev.to_matrix(rows)
    times = [datetime.fromisoformat(row["time"]) for row in rows]
    by_time = dict(zip(times, rows, strict=True))
    results = []
    for start, end in manifest["windows"]:
        boundary, stop = datetime.fromisoformat(start), datetime.fromisoformat(end)
        train = [i for i, t in enumerate(times) if t < boundary - timedelta(hours=6)]
        test = [
            i
            for i, t in enumerate(times)
            if boundary <= t < stop and t + timedelta(hours=6) in by_time
        ]
        x_train, medians = ev.impute(x[train])
        x_test, _ = ev.impute(x[test], medians=medians)
        yt = [int(y[i]) for i in test]
        target_weather = [by_time[times[i] + timedelta(hours=6)] for i in test]
        models = {}
        for name in manifest["models"]:
            if name == "persistence":
                pred = [ev.BAND_ORDINALS[rows[i]["band"]] for i in test]
                seconds = 0.0
            else:
                pred, seconds, _ = ev.fit_predict(name, x_train, y[train], x_test, medians, seed=0)
            cm = ev.confusion(yt, pred)
            safety = ev.safety_metrics(yt, pred, target_weather)
            safety["_policy_approximation"] = (
                "Aligned recorded t+6 weather used for both policies; oracle-weather diagnostic, not a deployed weather forecast"
            )
            air_risk = [j for j, label in enumerate(yt) if label >= 3]
            under = sum(pred[j] < 3 for j in air_risk)
            models[name] = {
                "metrics": ev.prf(cm),
                "confusion": cm,
                "policy": safety,
                "poor_or_worse_n": len(air_risk),
                "poor_or_worse_predicted_below_poor": under,
                "fit_seconds": seconds,
                "predictions": pred,
            }
        results.append(
            {
                "start": start,
                "end": end,
                "n_train": len(train),
                "n_test": len(test),
                "models": models,
                "labels": yt,
                "times": [rows[i]["time"] for i in test],
            }
        )
    return {
        "manifest": manifest,
        "versions": {n: version(n) for n in ["numpy", "scikit-learn", "lightgbm"]},
        "windows": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submit", action="store_true")
    parser.add_argument("--fetch", action="store_true")
    args = parser.parse_args()
    if args.submit == args.fetch:
        parser.error("Choose --submit or --fetch")
    import modal

    if args.fetch:
        manifest = json.loads(MANIFEST.read_text())
        if manifest["status"] == "COMPLETED":
            print("Already fetched")
            return
        try:
            result = modal.FunctionCall.from_id(manifest["call_id"]).get(timeout=5)
        except (TimeoutError, modal.exception.TimeoutError):
            print("Rolling validation still running")
            return
        output = ROOT / "eval/raw/forecast_rolling_results.json"
        write(output, result)
        manifest.update(status="COMPLETED", results=str(output.relative_to(ROOT)))
        write(MANIFEST, manifest)
        print("Fetched rolling diagnostics")
        return
    if MANIFEST.exists():
        raise ValueError("Refusing duplicate submission")
    manifest = {
        "status": "PREREGISTERED",
        "rows_sha256": digest(ROOT / "data/eval/gono_rows.jsonl"),
        "windows": [
            ["2026-02-01", "2026-03-01"],
            ["2026-04-01", "2026-05-01"],
            ["2026-06-01", "2026-07-01"],
            ["2026-08-01", "2026-09-01"],
        ],
        "models": ["majority", "persistence", "lgbm", "ensemble"],
        "embargo_hours": 6,
        "limitations": "Existing archive and previously selected configurations; rolling diagnostics, not pristine independent validation. No new parameter tuning; no model promotion. Synthetic extra pollution rows are not added.",
        "timeout_seconds": 1800,
        "compute_ceiling_estimate_usd": 1800 * (2 * 0.0000131 + 8 * 0.00000222),
    }
    image = (
        modal.Image.debian_slim(python_version="3.12")
        .pip_install(
            "numpy==2.2.6",
            "scikit-learn==1.6.1",
            "lightgbm==4.6.0",
            "httpx==0.28.1",
            "pydantic==2.11.7",
            "python-dotenv==1.1.1",
        )
        .env({"OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2"})
    )
    files = list((ROOT / "src/baahar").glob("*.py")) + [
        ROOT / "scripts/run_eval.py",
        ROOT / "scripts/build_dataset.py",
    ]
    manifest["source_sha256"] = {str(p.relative_to(ROOT)): digest(p) for p in files}
    for p in files:
        image = image.add_local_file(str(p), "/opt/" + p.relative_to(ROOT).as_posix())
    image = image.add_local_file(str(ROOT / "data/eval/gono_rows.jsonl"), "/opt/rows.jsonl")
    write(MANIFEST, manifest)
    app = modal.App("baahar-rolling-forecast-diagnostics", image=image)
    function = app.function(cpu=2, memory=8192, timeout=1800, retries=0, max_containers=1)(
        remote_validate
    )
    with app.run(detach=True):
        call = function.spawn(manifest)
        manifest.update(status="SUBMITTED", app_id=app.app_id, call_id=call.object_id)
        write(MANIFEST, manifest)
        print(
            json.dumps(
                {
                    "app_id": app.app_id,
                    "call_id": call.object_id,
                    "url": "https://modal.com/apps/vedantmahajan271/main/" + app.app_id,
                }
            )
        )


if __name__ == "__main__":
    main()
