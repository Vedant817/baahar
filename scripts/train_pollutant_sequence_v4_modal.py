"""Source-pinned hosted pollutant trajectory experiment; never installs torch locally."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ROOT / "eval/raw/pollutant_sequence_v4"
MANIFEST = Path(str(PREFIX) + "_manifest.json")
GASES = ("pm2_5", "pm10", "nitrogen_dioxide", "ozone", "sulphur_dioxide", "carbon_monoxide")
WEATHER = (
    "temperature_2m",
    "apparent_temperature",
    "precipitation",
    "relative_humidity_2m",
    "wind_speed_10m",
)
BANDS = ("good", "satisfactory", "moderate", "poor", "severe", "hazardous")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")


def encode_residual(future, current, scale):
    """Current must be raw timestamp-t concentrations; scale is absolute train std."""
    return (future - current[:, None, :]) / scale


def decode_residual(output, current, scale):
    """Reconstruct all future horizons without consulting future observations."""
    return current[:, None, :] + output * scale


def training_origin_weight(ordinal):
    """Fixed supervised training priority; never a predictor or evaluation threshold."""
    if ordinal not in range(6):
        raise ValueError("Unknown canonical ordinal")
    return 2.0 if ordinal >= 3 else 1.0


def validate_pair(frozen, times, truth, labels, actual_pollutants):
    """Refuse comparisons with different origins or any changed actual targets."""
    if (
        frozen["times"] != times
        or frozen["actual_naqi"] != truth
        or frozen["actual_legacy_bands"] != labels
        or frozen["actual_pollutants"] != actual_pollutants
    ):
        raise ValueError("Paired reference origins/targets differ")


def supported_window(stamp, start, end, air):
    """Require complete phase-local causal context and six exact future hours."""
    t = datetime.fromisoformat(stamp)
    if t - timedelta(hours=23) < datetime.fromisoformat(start) or t + timedelta(
        hours=6
    ) >= datetime.fromisoformat(end):
        return False
    for offset in range(-23, 7):
        key = (t + timedelta(hours=offset)).isoformat(timespec="minutes")
        record = air.get(key)
        if record is None or any(
            record.get(v) is None or not math.isfinite(record[v]) for v in GASES
        ):
            return False
    return True


def feature_window(stamp, air, weather):
    """Only read source hours t-23..t; missing weather remains missing for train imputation."""
    t = datetime.fromisoformat(stamp)
    features = []
    for offset in range(-23, 1):
        current = t + timedelta(hours=offset)
        key = current.isoformat(timespec="minutes")
        values = [air[key][v] for v in GASES] + [weather.get(key, {}).get(v) for v in WEATHER]
        numeric = [float(v) if v is not None and math.isfinite(v) else float("nan") for v in values]
        numeric += [
            math.sin(2 * math.pi * current.hour / 24),
            math.cos(2 * math.pi * current.hour / 24),
            math.sin(2 * math.pi * (current.month - 1) / 12),
            math.cos(2 * math.pi * (current.month - 1) / 12),
        ]
        features.append(numeric)
    return features


def event_metrics(times, truth, predictions, threshold):
    positives = [
        (datetime.fromisoformat(t), p >= threshold)
        for t, y, p in zip(times, truth, predictions, strict=True)
        if y >= threshold
    ]
    episodes = []
    for stamp, hit in positives:
        if not episodes or stamp - episodes[-1][-1][0] > timedelta(hours=6):
            episodes.append([])
        episodes[-1].append((stamp, hit))
    return {
        "episodes": len(episodes),
        "any_hit": sum(any(h for _, h in e) for e in episodes),
        "full_hit": sum(all(h for _, h in e) for e in episodes),
        "onset_hit": sum(e[0][1] for e in episodes),
    }


def remote_train(manifest):
    import sys
    import time

    sys.path[:0] = ["/opt/src", "/opt/scripts"]
    import build_dataset as bd
    import modal
    import numpy as np
    import torch
    from lightgbm import LGBMRegressor
    from sklearn.metrics import average_precision_score, f1_score
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset

    from baahar.naqi import band_for_index

    started = time.monotonic()
    volume = modal.Volume.from_name("baahar-training")
    torch.set_num_threads(2)
    for relative, sha in manifest["source_sha256"].items():
        if digest(Path("/opt") / relative) != sha:
            raise ValueError("Implementation source SHA mismatch: " + relative)
    replay = manifest["replay"]
    directory = Path("/artifacts/forecast_risk_v3")
    if digest(directory / "rows.jsonl") != replay["rows_sha256"]:
        raise ValueError("Replay row SHA mismatch")
    rows = [json.loads(line) for line in (directory / "rows.jsonl").read_text().splitlines()]
    air, weather = {}, {}
    for fixture in replay["source_fixtures"]:
        path = directory / fixture["path"]
        if digest(path) != fixture["sha256"]:
            raise ValueError("Fixture SHA mismatch: " + fixture["path"])
        hourly = json.loads(path.read_text())["hourly"]
        destination = air if "archival_aq_" in path.name else weather
        for i, stamp in enumerate(hourly["time"]):
            value = {key: entries[i] for key, entries in hourly.items() if key != "time"}
            if stamp in destination and destination[stamp] != value:
                raise ValueError("Conflicting source timestamp")
            destination[stamp] = value
    # Verify exact target time rather than trusting positional archive offsets.
    for row in rows:
        stamp = row["time"] if "time" in row else row["timestamp"]
        future = (datetime.fromisoformat(stamp) + timedelta(hours=6)).isoformat(timespec="minutes")
        reading = air[future]
        actual = bd.compute_naqi({bd.AQ_VAR_TO_KEY[k]: reading.get(k) for k in GASES})
        if round(actual.index, 2) != row["target_naqi"] or actual.band != row["target_band"]:
            raise ValueError("Exact future canonical target mismatch")
    stamps = [row.get("time", row.get("timestamp")) for row in rows]
    parts = {}
    for name, (start, end) in manifest["partitions"].items():
        selected = [t for t in stamps if supported_window(t, start, end, air)]
        if not selected:
            raise ValueError("No eligible rows: " + name)
        x = np.asarray([feature_window(t, air, weather) for t in selected], dtype=np.float32)
        y = np.asarray(
            [
                [
                    [
                        air[
                            (datetime.fromisoformat(t) + timedelta(hours=h)).isoformat(
                                timespec="minutes"
                            )
                        ][g]
                        for g in GASES
                    ]
                    for h in range(1, 7)
                ]
                for t in selected
            ],
            dtype=np.float64,
        )
        parts[name] = {
            "times": selected,
            "x": x,
            "y": y,
            "current": np.asarray([[air[t][g] for g in GASES] for t in selected], dtype=np.float64),
            "support_start": (
                datetime.fromisoformat(selected[0]) - timedelta(hours=23)
            ).isoformat(),
            "support_end": (datetime.fromisoformat(selected[-1]) + timedelta(hours=6)).isoformat(),
        }
        if len(selected) != manifest["expected_eligible_rows"][name]:
            raise ValueError("Support audit eligibility mismatch: " + name)
    train = parts["train"]
    medians = np.nanmedian(train["x"], axis=(0, 1))
    if not np.isfinite(medians).all():
        raise ValueError("Unobserved training input channel")
    filled = np.where(np.isfinite(train["x"]), train["x"], medians)
    means, stds = filled.mean(axis=(0, 1)), filled.std(axis=(0, 1))
    stds = np.maximum(stds, 1e-6)
    ymean, ystd = train["y"].mean(axis=(0, 1)), np.maximum(train["y"].std(axis=(0, 1)), 1e-6)
    for part in parts.values():
        mask = ~np.isfinite(part["x"])
        values = np.where(mask, medians, part["x"])
        part["inputs"] = np.concatenate(
            [(values - means) / stds, mask.astype(np.float32)], axis=2
        ).astype(np.float32)
        part["targets"] = encode_residual(part["y"], part["current"], ystd).astype(np.float32)
        reconstructed = decode_residual(part["targets"], part["current"], ystd)
        if reconstructed.shape != part["y"].shape or not np.isfinite(reconstructed).all():
            raise ValueError("Residual reconstruction shape/finiteness failure")
        if not np.allclose(reconstructed, part["y"], rtol=2e-6, atol=1e-4):
            raise ValueError("Residual encode/decode round-trip failure")
        zero = decode_residual(np.zeros_like(part["targets"]), part["current"], ystd)
        if not np.array_equal(zero, np.broadcast_to(part["current"][:, None, :], zero.shape)):
            raise ValueError("Zero residual is not timestamp-t persistence")
    support = {}
    for name, part in parts.items():
        indices = [
            float(
                bd.compute_naqi(
                    {bd.AQ_VAR_TO_KEY[g]: float(v) for g, v in zip(GASES, row, strict=True)}
                ).index
            )
            for row in part["y"][:, -1]
        ]
        ordinal = [BANDS.index(band_for_index(v)) for v in indices]
        support[name] = {
            "eligible_rows": len(indices),
            "support_start": part["support_start"],
            "support_end": part["support_end"],
            "poor_or_worse_hours": sum(v >= 3 for v in ordinal),
            "very_poor_or_worse_hours": sum(v >= 4 for v in ordinal),
            "severe_hours": sum(v >= 5 for v in ordinal),
            "very_poor_episodes": event_metrics(part["times"], ordinal, ordinal, 4),
        }
    write(Path("/artifacts/pollutant_sequence_v4_support.json"), support)

    training_ordinals = [
        BANDS.index(
            band_for_index(
                float(
                    bd.compute_naqi(
                        {bd.AQ_VAR_TO_KEY[g]: float(v) for g, v in zip(GASES, row, strict=True)}
                    ).index
                )
            )
        )
        for row in train["y"][:, -1]
    ]
    training_weights = np.asarray(
        [training_origin_weight(v) for v in training_ordinals], dtype=np.float32
    )
    if int((training_weights > 1).sum()) != support["train"]["poor_or_worse_hours"]:
        raise ValueError("Training weight support mismatch")

    class Block(nn.Module):
        def __init__(self, channels, dilation):
            super().__init__()
            self.padding = 2 * dilation
            self.conv1 = nn.Conv1d(channels, channels, 3, dilation=dilation)
            self.conv2 = nn.Conv1d(channels, channels, 3, dilation=dilation)
            self.dropout = nn.Dropout(0.1)

        def forward(self, x):
            value = self.dropout(torch.relu(self.conv1(nn.functional.pad(x, (self.padding, 0)))))
            value = self.dropout(
                torch.relu(self.conv2(nn.functional.pad(value, (self.padding, 0))))
            )
            return torch.relu(x + value)

    class TCN(nn.Module):
        def __init__(self):
            super().__init__()
            self.input = nn.Conv1d(30, 32, 1)
            self.blocks = nn.Sequential(*(Block(32, d) for d in (1, 2, 4, 8)))
            self.head = nn.Linear(32, 36)

        def forward(self, x):
            return self.head(self.blocks(self.input(x.transpose(1, 2)))[:, :, -1]).reshape(-1, 6, 6)

    output_dir = Path("/artifacts/pollutant_sequence_v4")
    output_dir.mkdir(exist_ok=True)
    predictions = {name: {} for name in parts}
    histories = {}
    device = torch.device("cuda")
    for seed in manifest["seeds"]:
        np.random.seed(seed)
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        model = TCN().to(device)
        optimizer = torch.optim.AdamW(model.parameters(), lr=0.001, weight_decay=0.0001)
        loader = DataLoader(
            TensorDataset(
                torch.from_numpy(train["inputs"]),
                torch.from_numpy(train["targets"]),
                torch.from_numpy(training_weights),
            ),
            batch_size=256,
            shuffle=True,
            generator=torch.Generator().manual_seed(seed),
        )
        best, stale, history = math.inf, 0, []
        checkpoint = output_dir / f"tcn_seed_{seed}.pt"
        for epoch in range(60):
            if time.monotonic() - started > 6900:
                raise TimeoutError("Training exceeded finite wall-clock budget")
            model.train()
            for x, y, weights in loader:
                optimizer.zero_grad()
                element_loss = nn.functional.smooth_l1_loss(
                    model(x.to(device)), y.to(device), reduction="none"
                )
                origin_loss = element_loss.mean(dim=(1, 2))
                weights = weights.to(device)
                loss = (origin_loss * weights).sum() / weights.sum()
                loss.backward()
                optimizer.step()
            model.eval()
            with torch.no_grad():
                development = parts["development"]
                values = torch.cat(
                    [
                        model(torch.from_numpy(development["inputs"][i : i + 256]).to(device)).cpu()
                        for i in range(0, len(development["times"]), 256)
                    ]
                )
                residual_score = float(
                    torch.mean(torch.abs(values - torch.from_numpy(development["targets"])))
                )
                decoded = decode_residual(values.numpy(), development["current"], ystd)
                score = float(np.mean(np.abs(decoded - development["y"]) / ystd))
                if not np.isclose(score, residual_score, rtol=2e-6, atol=2e-6):
                    raise ValueError("Development residual/absolute scaled-MAE mismatch")
            history.append({"epoch": epoch + 1, "development_standardized_mae": score})
            write(
                output_dir / "progress.json",
                {
                    "seed": seed,
                    "epoch": epoch + 1,
                    "development_standardized_mae": score,
                    "elapsed_seconds": time.monotonic() - started,
                    "status": "TRAINING",
                },
            )
            print(
                f"seed={seed} epoch={epoch + 1} development_standardized_mae={score:.6f}",
                flush=True,
            )
            if score < best:
                best, stale = score, 0
                torch.save(model.state_dict(), checkpoint)
                write(output_dir / f"history_seed_{seed}.json", history)
                volume.commit()
            else:
                stale += 1
                if stale >= 8:
                    break
        model.load_state_dict(torch.load(checkpoint, map_location=device, weights_only=True))
        histories[str(seed)] = {"epochs": history, "best_development_standardized_mae": best}
        for name, part in parts.items():
            if name == "train":
                continue
            model.eval()
            with torch.no_grad():
                value = torch.cat(
                    [
                        model(torch.from_numpy(part["inputs"][i : i + 256]).to(device)).cpu()
                        for i in range(0, len(part["times"]), 256)
                    ]
                ).numpy()
            predictions[name][f"tcn_seed_{seed}"] = decode_residual(value, part["current"], ystd)[
                :, -1
            ]
    trees = []
    for gas in range(6):
        tree = LGBMRegressor(**manifest["tree_parameters"])
        tree.fit(train["inputs"].reshape(len(train["times"]), -1), train["y"][:, -1, gas])
        trees.append(tree)
    import joblib

    joblib.dump(
        {
            "trees": trees,
            "medians": medians,
            "means": means,
            "stds": stds,
            "target_means": ymean,
            "target_stds": ystd,
            "manifest": manifest,
        },
        output_dir / "preprocessing_and_trees.joblib",
    )

    def naqi(values):
        return [
            float(
                bd.compute_naqi(
                    {bd.AQ_VAR_TO_KEY[k]: float(v) for k, v in zip(GASES, row, strict=True)}
                ).index
            )
            for row in values
        ]

    reference_path = Path("/opt") / manifest["reference"]["path"]
    if digest(reference_path) != manifest["reference"]["result_sha256"]:
        raise ValueError("V3 reference SHA mismatch")
    reference = json.loads(reference_path.read_text())
    if (
        reference["manifest"]["replay"] != manifest["replay"]
        or reference["manifest"]["partitions"] != manifest["partitions"]
    ):
        raise ValueError("Reference dataset or partitions differ")
    reference_periods = {p["partition"]: p for p in reference["results"]}
    results = []
    for name, part in parts.items():
        if name == "train":
            continue
        candidates = predictions[name]
        candidates["tcn_fixed_mean"] = np.mean(
            [candidates[f"tcn_seed_{s}"] for s in manifest["seeds"]], axis=0
        )
        candidates["paired_lightgbm"] = np.column_stack(
            [tree.predict(part["inputs"].reshape(len(part["times"]), -1)) for tree in trees]
        )
        candidates["persistence"] = np.asarray([[air[t][g] for g in GASES] for t in part["times"]])
        truth = naqi(part["y"][:, -1])
        labels = [band_for_index(v) for v in truth]
        truth_ordinal = [BANDS.index(v) for v in labels]
        models = {}
        for model_name, raw in candidates.items():
            predicted_gases = np.maximum(raw, 0)
            predicted = naqi(predicted_gases)
            categories = [band_for_index(v) for v in predicted]
            predicted_ordinal = [BANDS.index(v) for v in categories]
            risk = {}
            for risk_name, threshold in (
                ("poor_or_worse", 3),
                ("very_poor_or_worse", 4),
                ("severe", 5),
            ):
                y = np.asarray(truth_ordinal) >= threshold
                p = np.asarray(predicted_ordinal) >= threshold
                tp, fp, fn = int(sum(y & p)), int(sum(~y & p)), int(sum(y & ~p))
                positives, negatives = int(sum(y)), int(sum(~y))
                risk[risk_name] = {
                    "support": positives,
                    "negative_support": negatives,
                    "misses": fn,
                    "recall": tp / positives if positives else None,
                    "false_alarms": fp,
                    "false_alarm_rate": fp / negatives if negatives else None,
                    "precision": tp / (tp + fp) if tp + fp else None,
                    "ranking_average_precision": float(average_precision_score(y, predicted))
                    if positives
                    else None,
                    "brier": None,
                    "ece": None,
                    "reliability": None,
                    "episodes": event_metrics(
                        part["times"], truth_ordinal, predicted_ordinal, threshold
                    ),
                }
            errors = predicted_gases - part["y"][:, -1]
            models[model_name] = {
                "accuracy": sum(a == b for a, b in zip(labels, categories, strict=True))
                / len(labels),
                "confusion_matrix": [
                    [
                        sum(
                            a == i and b == j
                            for a, b in zip(truth_ordinal, predicted_ordinal, strict=True)
                        )
                        for j in range(6)
                    ]
                    for i in range(6)
                ],
                "macro_f1": float(
                    f1_score(
                        labels,
                        categories,
                        average="macro",
                        labels=sorted(set(labels)),
                        zero_division=0,
                    )
                ),
                "risk": risk,
                "pollutant_errors": {
                    g: {
                        "mae": float(np.mean(np.abs(errors[:, i]))),
                        "rmse": float(np.sqrt(np.mean(errors[:, i] ** 2))),
                    }
                    for i, g in enumerate(GASES)
                },
                "naqi_mae": float(np.mean(np.abs(np.asarray(predicted) - truth))),
                "naqi_rmse": float(np.sqrt(np.mean((np.asarray(predicted) - truth) ** 2))),
                "negative_concentration_clips": int(sum((raw < 0).flatten())),
                "predicted_naqi": predicted,
                "predicted_pollutants": predicted_gases.tolist(),
                "predicted_legacy_bands": categories,
            }
        frozen = reference_periods[name]
        validate_pair(frozen, part["times"], truth, labels, part["y"][:, -1].tolist())
        for baseline in ("paired_lightgbm", "persistence"):
            if not np.array_equal(
                np.asarray(frozen["models"][baseline]["predicted_pollutants"]),
                np.asarray(models[baseline]["predicted_pollutants"]),
            ):
                raise ValueError("Unchanged baseline failed reproduction: " + baseline)
        models["v3_fixed_mean"] = frozen["models"]["tcn_fixed_mean"]
        results.append(
            {
                "partition": name,
                "count": len(truth),
                "times": part["times"],
                "actual_naqi": truth,
                "actual_legacy_bands": labels,
                "actual_pollutants": part["y"][:, -1].tolist(),
                "legacy_class_support": {b: labels.count(b) for b in BANDS},
                "models": models,
            }
        )
    result = {
        "manifest": manifest,
        "results": results,
        "support": support,
        "exact_future_target_checks": len(rows),
        "training": histories,
        "training_weight_support": {
            "weighted_origins": int((training_weights > 1).sum()),
            "eligible_origins": len(training_weights),
        },
        "elapsed_seconds": time.monotonic() - started,
        "target_contract": "Hourly canonical breakpoint proxy, not CPCB averaging-compliant station NAQI. Official 301+ Very Poor and 401+ Severe; historical code labels these severe/hazardous respectively.",
        "limitations": "Consumed modeled CAMS/ERA5 archive; no station/prospective evidence, no future weather input, no probabilities, no automatic promotion.",
    }
    write(output_dir / "results.json", result)
    write(
        output_dir / "progress.json",
        {"status": "COMPLETED", "elapsed_seconds": time.monotonic() - started},
    )
    volume.commit()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submit", action="store_true")
    parser.add_argument("--fetch", action="store_true")
    args = parser.parse_args()
    import modal

    if args.fetch:
        manifest = json.loads(MANIFEST.read_text())
        result_path = Path(str(PREFIX) + "_results.json")
        if result_path.exists():
            print("Saved result exists; no repeat fetch.")
            return
        try:
            result = modal.FunctionCall.from_id(manifest["call_id"]).get(timeout=5)
        except (TimeoutError, modal.exception.TimeoutError):
            print("PENDING " + manifest["call_id"])
            return
        write(result_path, result)
        manifest.update(status="COMPLETED", result_sha256=digest(result_path))
        write(MANIFEST, manifest)
        print("COMPLETED " + str(result_path))
        return
    if not args.submit:
        parser.error("Choose --submit or --fetch")
    if MANIFEST.exists():
        raise SystemExit("Manifest already exists; refusing duplicate submission")
    reference_path = ROOT / "eval/raw/pollutant_sequence_v3_results.json"
    reference_manifest = json.loads(
        (ROOT / "eval/raw/pollutant_sequence_v3_manifest.json").read_text()
    )
    if (
        reference_manifest["status"] != "COMPLETED"
        or digest(reference_path) != reference_manifest["result_sha256"]
    ):
        raise ValueError("Frozen v3 reference is incomplete or changed")
    for relative, expected in reference_manifest["source_sha256"].items():
        if (
            relative.startswith("src/baahar/")
            or relative
            in (
                "scripts/build_dataset.py",
                "eval/raw/pollutant_sequence_support_results.json",
                "docs/DEEP_POLLUTANT_STUDY_PROTOCOL.md",
                "docs/POLLUTANT_SEQUENCE_V3_PROTOCOL.md",
            )
        ) and digest(ROOT / relative) != expected:
            raise ValueError("Representation experiment encountered changed v3 source: " + relative)
    old = json.loads((ROOT / "eval/raw/forecast_risk_v3_results.json").read_text())
    files = list((ROOT / "src/baahar").glob("*.py")) + [
        ROOT / "scripts/build_dataset.py",
        Path(__file__),
        reference_path,
        ROOT / "scripts/report_pollutant_sequence_v4.py",
        ROOT / "docs/POLLUTANT_SEQUENCE_V4_PROTOCOL.md",
        ROOT / "docs/DEEP_POLLUTANT_STUDY_PROTOCOL.md",
        ROOT / "docs/POLLUTANT_SEQUENCE_V3_PROTOCOL.md",
        ROOT / "eval/raw/pollutant_sequence_support_results.json",
    ]
    manifest = {
        "status": "PREREGISTERED",
        "created_at": datetime.now(UTC).isoformat(),
        "run_name": "pollutant_sequence_v4",
        "replay": old["dataset"],
        "seeds": [0, 1, 2],
        "reference": {
            "name": "v3_fixed_mean",
            "result_sha256": digest(reference_path),
            "call_id": reference_manifest["call_id"],
            "path": "eval/raw/pollutant_sequence_v3_results.json",
        },
        "single_training_change": "current-referenced residual forecasts with unchanged absolute training target scales; relative to v3",
        "partitions": {
            "train": ["2023-01-01", "2025-04-01"],
            "development": ["2025-04-01", "2025-06-01"],
            "diagnostic_pollution": ["2026-02-01", "2026-05-01"],
            "diagnostic_other_seasons": ["2026-05-01", "2026-10-01"],
        },
        "tree_parameters": old["manifest"]["model_parameters"],
        "protocol": {
            "context_hours": 24,
            "horizons": [1, 2, 3, 4, 5, 6],
            "loss": "Training risk-weighted SmoothL1 on train-standardized targets",
            "checkpoint": "development standardized MAE",
            "epochs": 60,
            "patience": 8,
            "channels": 32,
            "dilations": [1, 2, 4, 8],
            "dropout": 0.1,
            "batch_size": 256,
            "optimizer": "AdamW lr0.001 weight_decay0.0001",
            "gpu": "T4",
            "timeout_seconds": 7200,
        },
        "target_representation": "(future-current_at_t)/absolute_training_ystd; decode current_at_t+output*ystd; no target mean",
        "training_origin_weighting": {
            "poor_or_worse": 2.0,
            "otherwise": 1.0,
            "labels": "training final-sixth-hour canonical rounded category only",
            "normalization": "batch weighted mean",
        },
        "source_sha256": {p.relative_to(ROOT).as_posix(): digest(p) for p in files},
    }
    audit = json.loads((ROOT / "eval/raw/pollutant_sequence_support_results.json").read_text())
    manifest["expected_eligible_rows"] = {
        name: value["eligible_rows"] for name, value in audit["support"].items()
    }
    image = (
        modal.Image.debian_slim(python_version="3.12")
        .pip_install(
            "numpy==2.2.6",
            "scikit-learn==1.6.1",
            "lightgbm==4.6.0",
            "torch==2.6.0",
            "httpx==0.28.1",
            "pydantic==2.11.7",
            "python-dotenv==1.1.1",
        )
        .env({"OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2"})
    )
    for path in files:
        image = image.add_local_file(str(path), "/opt/" + path.relative_to(ROOT).as_posix())
    write(MANIFEST, manifest)
    app = modal.App("baahar-pollutant-sequence-v4", image=image)
    function = app.function(
        gpu="T4",
        cpu=2,
        memory=8192,
        timeout=7200,
        retries=0,
        max_containers=1,
        volumes={"/artifacts": modal.Volume.from_name("baahar-training")},
    )(remote_train)
    with app.run(detach=True):
        call = function.spawn(manifest)
        manifest.update(status="SUBMITTED", call_id=call.object_id, app_id=app.app_id)
        write(MANIFEST, manifest)
        print(
            json.dumps(
                {
                    "call_id": call.object_id,
                    "url": "https://modal.com/apps/vedantmahajan271/main/" + app.app_id,
                }
            )
        )


if __name__ == "__main__":
    main()
