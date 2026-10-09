"""Fixed full-origin GPU Ridge study after preserved v1 startup failure; no local ML imports or repeat calls."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Modal imports this module before entering the function body.
if Path("/opt/scripts").is_dir():
    sys.path[:0] = ["/opt/src", "/opt/scripts"]

from probe_pollutant_lag_modal import digest, features, origins_digest, write
from train_pollutant_sequence_v3_modal import (
    GASES,
    supported_window,
    training_origin_weight,
    validate_pair,
)

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ROOT / "eval/raw/pollutant_linear_v2_gpu"
MANIFEST = Path(str(PREFIX) + "_manifest.json")
RESULT = Path(str(PREFIX) + "_results.json")


def remote_train(manifest):
    import sys
    import time

    sys.path[:0] = ["/opt/src", "/opt/scripts"]
    import modal
    import numpy as np
    import torch
    from analyze_linear_ozone_complementarity import BANDS, canonical, score
    from sklearn.impute import SimpleImputer
    from sklearn.metrics import f1_score
    from sklearn.preprocessing import StandardScaler

    started = time.monotonic()
    print("FUNCTION_ENTERED source validation starting", flush=True)
    for relative, sha in manifest["source_sha256"].items():
        if digest(Path("/opt") / relative) != sha:
            raise ValueError("Pinned source changed: " + relative)
    directory = Path("/artifacts/forecast_risk_v3")
    if digest(directory / "rows.jsonl") != manifest["replay"]["rows_sha256"]:
        raise ValueError("Replay SHA mismatch")
    rows = [json.loads(line) for line in (directory / "rows.jsonl").read_text().splitlines()]
    air, weather = {}, {}
    for fixture in manifest["replay"]["source_fixtures"]:
        path = directory / fixture["path"]
        if digest(path) != fixture["sha256"]:
            raise ValueError("Fixture SHA mismatch")
        hourly = json.loads(path.read_text())["hourly"]
        destination = air if "archival_aq_" in path.name else weather
        for i, stamp in enumerate(hourly["time"]):
            record = {k: v[i] for k, v in hourly.items() if k != "time"}
            if stamp in destination and destination[stamp] != record:
                raise ValueError("Conflicting timestamp")
            destination[stamp] = record
    print("SOURCE_LOADED constructing exact causal features", flush=True)
    checks = 0
    for row in rows:
        future = (datetime.fromisoformat(row["time"]) + timedelta(hours=6)).isoformat(timespec="minutes")
        index, label = canonical([float(air[future][g]) for g in GASES])
        if round(index, 2) != row["target_naqi"] or BANDS[label] != row["target_band"]:
            raise ValueError("Canonical exact future target mismatch")
        checks += 1
    parts = {}
    for name, (start, end) in manifest["partitions"].items():
        times = [r["time"] for r in rows if supported_window(r["time"], start, end, air)]
        if len(times) != manifest["expected_eligible_rows"][name] or times != sorted(times):
            raise ValueError("Full V3 support mismatch")
        x = np.asarray([features(t, air, weather, 24) for t in times], dtype=np.float64)
        y = np.asarray([[air[(datetime.fromisoformat(t) + timedelta(hours=6)).isoformat(timespec="minutes")][g]
                         for g in GASES] for t in times], dtype=np.float64)
        if x.shape != (len(times), 360) or not np.isfinite(y).all():
            raise ValueError("Feature/target shape or finiteness mismatch")
        parts[name] = {"times": times, "x": x, "y": y}
    print("FEATURES_COMPLETED exact support checked", flush=True)
    reference = json.loads((Path("/opt") / manifest["reference"]["path"]).read_text())
    frozen = {p["partition"]: p for p in reference["results"]}
    for name, part in parts.items():
        if name == "train":
            continue
        indices = [canonical(row)[0] for row in part["y"]]
        labels = [BANDS[canonical(row)[1]] for row in part["y"]]
        validate_pair(frozen[name], part["times"], indices, labels, part["y"].tolist())
    train = parts["train"]
    mean = train["y"].mean(axis=0)
    scale = np.maximum(train["y"].std(axis=0), 1e-6)
    weights = np.asarray([training_origin_weight(canonical(row)[1]) for row in train["y"]])
    if int((weights > 1).sum()) != 296 or len(weights) != 19663:
        raise ValueError("Training risk weight support changed")
    if not np.isfinite(np.nanmedian(train["x"], axis=0)).all():
        raise ValueError("Unobserved training feature")
    if not torch.cuda.is_available():
        raise RuntimeError("GPU required; no CPU fallback")
    print("GPU_CONFIRMED " + torch.cuda.get_device_name(0), flush=True)
    imputer = SimpleImputer(strategy="median")
    scaler = StandardScaler()
    transformed = scaler.fit_transform(imputer.fit_transform(train["x"]))
    medians = imputer.statistics_
    filled = np.where(np.isfinite(train["x"]), train["x"], medians)
    if not np.allclose(scaler.mean_, filled.mean(axis=0), rtol=1e-12, atol=1e-12):
        raise ValueError("Training-only input scaling check failed")
    x_gpu = torch.as_tensor(transformed, dtype=torch.float64, device="cuda")
    y_gpu = torch.as_tensor((train["y"] - mean) / scale, dtype=torch.float64, device="cuda")
    w_gpu = torch.as_tensor(weights, dtype=torch.float64, device="cuda")
    x_offset = (x_gpu * w_gpu[:, None]).sum(0) / w_gpu.sum()
    y_offset = (y_gpu * w_gpu[:, None]).sum(0) / w_gpu.sum()
    xc, yc = x_gpu - x_offset, y_gpu - y_offset
    gram = xc.T @ (xc * w_gpu[:, None])
    rhs = xc.T @ (yc * w_gpu[:, None])
    gram += 10.0 * torch.eye(gram.shape[0], dtype=torch.float64, device="cuda")
    coefficients = torch.linalg.solve(gram, rhs)
    intercept = y_offset - x_offset @ coefficients
    solve_residual = float((gram @ coefficients - rhs).abs().max().item())
    if not torch.isfinite(coefficients).all() or solve_residual > 1e-6:
        raise ValueError("GPU Ridge solve integrity failure")
    # Numerical implementation check on training-only tiny matrices, not a candidate fit.
    from sklearn.linear_model import Ridge
    parity_x = transformed[:64, :12]
    parity_y = ((train["y"] - mean) / scale)[:64]
    parity_w = weights[:64]
    parity_reference = Ridge(alpha=10.0, solver="cholesky").fit(parity_x, parity_y, sample_weight=parity_w)
    px = torch.as_tensor(parity_x, dtype=torch.float64, device="cuda")
    py = torch.as_tensor(parity_y, dtype=torch.float64, device="cuda")
    pw = torch.as_tensor(parity_w, dtype=torch.float64, device="cuda")
    pmx, pmy = (px * pw[:, None]).sum(0) / pw.sum(), (py * pw[:, None]).sum(0) / pw.sum()
    pcx, pcy = px - pmx, py - pmy
    pb = torch.linalg.solve(pcx.T @ (pcx * pw[:, None]) + 10 * torch.eye(12, dtype=torch.float64, device="cuda"),
                            pcx.T @ (pcy * pw[:, None]))
    parity_prediction = (px @ pb + pmy - pmx @ pb).cpu().numpy()
    parity_error = float(np.max(np.abs(parity_prediction - parity_reference.predict(parity_x))))
    if parity_error > 1e-8:
        raise ValueError("GPU weighted Ridge intercept/penalty parity failed")
    print("GPU_FIT_COMPLETED residual=" + str(solve_residual) + " parity=" + str(parity_error), flush=True)
    output_dir = Path("/artifacts/pollutant_linear_v2_gpu")
    output_dir.mkdir(exist_ok=True)
    write(output_dir / "progress.json", {"status": "FIT_COMPLETED", "training_origins": len(weights)})
    volume = modal.Volume.from_name("baahar-training")
    volume.commit()
    results = []
    for name, part in parts.items():
        if name == "train":
            continue
        eval_x = scaler.transform(imputer.transform(part["x"]))
        pred_gpu = torch.as_tensor(eval_x, dtype=torch.float64, device="cuda") @ coefficients + intercept
        pred_raw = pred_gpu.cpu().numpy() * scale + mean
        pred = np.maximum(pred_raw, 0)
        m = score(part["times"], part["y"].tolist(), pred.tolist(), scale.tolist())
        labels = [canonical(row)[1] for row in part["y"]]
        guesses = [canonical(row)[1] for row in pred]
        m["macro_f1"] = float(f1_score(labels, guesses, labels=sorted(set(labels)), average="macro", zero_division=0))
        m["pollutant_errors"] = {g: {"mae": v["mae"], "rmse": v["rmse"], "bias": v["bias"],
                                      "poor_plus_mae": v["poor_plus_mae"], "poor_plus_bias": v["poor_plus_bias"]}
                                 for g, v in m["pollutant_errors"].items()}
        m["risk"]["severe"] = m["risk"].pop("official_severe")
        for risk in m["risk"].values():
            risk["episodes"]["episodes"] = risk["episodes"].pop("support")
            risk.update(brier=None, ece=None, reliability=None, average_precision=None)
        m.update(predicted_pollutants=pred.tolist(), predicted_naqi=[canonical(row)[0] for row in pred],
                 predicted_legacy_bands=[BANDS[v] for v in guesses], negative_concentration_clips=int((pred_raw < 0).sum()))
        p = {k: v for k, v in frozen[name].items() if k != "models"}
        p["models"] = {"ridge_fixed": m, "v3_fixed_mean": frozen[name]["models"]["tcn_fixed_mean"],
                       **{k: frozen[name]["models"][k] for k in ("paired_lightgbm", "persistence")}}
        results.append(p)
    training = {"algorithm": "GPU weighted centered Ridge alpha10 float64", "gpu_name": torch.cuda.get_device_name(0), "gpu_solve_max_residual": solve_residual, "gpu_tiny_matrix_parity_max_error": parity_error, "context_hours": 24, "features": 360,
                "target": "t+6 absolute six gases", "target_mean": mean.tolist(), "target_std": scale.tolist(),
                "input_median": medians.tolist(), "input_mean": scaler.mean_.tolist(), "input_scale": scaler.scale_.tolist(),
                "origin_hashes": {name: origins_digest(part["times"]) for name, part in parts.items()},
                "no_checkpoint_or_hyperparameter_selection": True}
    result = {"manifest": manifest, "results": results, "support": reference["support"],
              "exact_future_target_checks": checks, "training": training,
              "training_weight_support": {"weighted_origins": 296, "eligible_origins": len(weights)},
              "elapsed_seconds": time.monotonic() - started, "target_contract": reference["target_contract"],
              "limitations": "Adaptive consumed CAMS/ERA5 modeled archive; no station/prospective/medical qualification. Endpoint target scales differ from V3 trajectory scales. No probability calibration or deployment."}
    # Coefficients stay hosted; fetch returns only metrics, metadata and predictions.
    np.savez(output_dir / "ridge_parameters.npz", coefficients=coefficients.T.cpu().numpy(), intercept=intercept.cpu().numpy(),
             input_median=medians, input_mean=scaler.mean_, input_scale=scaler.scale_, target_mean=mean, target_scale=scale)
    write(output_dir / "results.json", result)
    write(output_dir / "progress.json", {"status": "COMPLETED", "elapsed_seconds": result["elapsed_seconds"]})
    volume.commit()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--submit", action="store_true")
    mode.add_argument("--fetch", action="store_true")
    args = parser.parse_args()
    import modal

    if args.fetch:
        manifest = json.loads(MANIFEST.read_text())
        if RESULT.exists():
            print("Saved result exists; preserving it")
            return
        if manifest["status"] != "SUBMITTED":
            raise ValueError("Only submitted call can be fetched")
        try:
            result = modal.FunctionCall.from_id(manifest["call_id"]).get(timeout=5)
        except (TimeoutError, modal.exception.TimeoutError):
            print("PENDING " + manifest["call_id"])
            return
        write(RESULT, result)
        manifest.update(status="COMPLETED", result_sha256=digest(RESULT), completed_at=datetime.now(UTC).isoformat())
        write(MANIFEST, manifest)
        print("COMPLETED " + str(RESULT))
        return
    if MANIFEST.exists():
        raise SystemExit("Existing manifest; refusing duplicate submission")
    reference_path = ROOT / "eval/raw/pollutant_sequence_v3_results.json"
    frozen = json.loads((ROOT / "eval/raw/pollutant_sequence_v3_manifest.json").read_text())
    if frozen["status"] != "COMPLETED" or digest(reference_path) != frozen["result_sha256"]:
        raise ValueError("V3 reference is incomplete or changed")
    for relative in ("scripts/train_pollutant_sequence_v3_modal.py", "src/baahar/naqi.py", "src/baahar/__init__.py"):
        if digest(ROOT / relative) != frozen["source_sha256"][relative]:
            raise ValueError("Frozen V3 source contract changed: " + relative)
    files = [Path(__file__), ROOT / "scripts/report_pollutant_linear_v2_gpu.py", ROOT / "scripts/probe_pollutant_lag_modal.py",
             ROOT / "scripts/train_pollutant_sequence_v3_modal.py", ROOT / "scripts/analyze_linear_ozone_complementarity.py",
             ROOT / "docs/POLLUTANT_LINEAR_V2_GPU_PROTOCOL.md", reference_path,
             ROOT / "src/baahar/naqi.py", ROOT / "src/baahar/__init__.py"]
    manifest = {"status": "PREREGISTERED", "created_at": datetime.now(UTC).isoformat(), "run_name": "pollutant_linear_v2_gpu",
                "replaces_failed_call": "fc-01M4FQDNY8YWCV2VQ90CRFNKZE",
                "replay": frozen["replay"], "partitions": frozen["partitions"],
                "expected_eligible_rows": frozen["expected_eligible_rows"],
                "reference": {"path": reference_path.relative_to(ROOT).as_posix(), "result_sha256": digest(reference_path), "call_id": frozen["call_id"]},
                "protocol": {"algorithm": "GPU weighted centered Ridge", "alpha": 10.0, "context_hours": 24, "cpu": 2, "memory_mb": 8192,
                             "timeout_seconds": 7200, "retries": 0, "max_containers": 1, "gpu": "T4"},
                "source_sha256": {p.relative_to(ROOT).as_posix(): digest(p) for p in files}}
    image = modal.Image.debian_slim(python_version="3.12").pip_install("numpy==2.2.6", "scikit-learn==1.6.1", "torch==2.6.0").env({"OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2", "PYTHONPATH": "/opt/scripts:/opt/src"})
    for path in files:
        image = image.add_local_file(str(path), "/opt/" + path.relative_to(ROOT).as_posix())
    write(MANIFEST, manifest)
    app = modal.App("baahar-pollutant-linear-v2-gpu", image=image)
    function = app.function(gpu="T4", cpu=2, memory=8192, timeout=7200, retries=0, max_containers=1,
                            volumes={"/artifacts": modal.Volume.from_name("baahar-training")})(remote_train)
    with app.run(detach=True):
        call = function.spawn(manifest)
        manifest.update(status="SUBMITTED", call_id=call.object_id, app_id=app.app_id)
        write(MANIFEST, manifest)
        print(json.dumps({"call_id": call.object_id, "app_id": app.app_id, "url": "https://modal.com/apps/vedantmahajan271/main/" + app.app_id}))


if __name__ == "__main__":
    main()
