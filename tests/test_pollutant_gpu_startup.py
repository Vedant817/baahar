"""Reproduce Modal's isolated module hydration without local GPU packages."""

import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_image_helpers_resolve_before_remote_function_body(tmp_path):
    scripts = tmp_path / "payload" / "scripts"
    source = tmp_path / "payload" / "src"
    scripts.mkdir(parents=True)
    source.mkdir()
    for name in ("probe_pollutant_lag_modal.py", "train_pollutant_sequence_v3_modal.py"):
        (scripts / name).write_bytes((ROOT / "scripts" / name).read_bytes())
    original = (ROOT / "scripts/train_pollutant_linear_v2_gpu_modal.py").read_text()
    adapted = original.replace("/opt/scripts", scripts.as_posix()).replace(
        "/opt/src", source.as_posix()
    )
    entry = tmp_path / "entry.py"
    entry.write_text(adapted, encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import runpy; runpy.run_path("
            + repr(str(entry))
            + ", run_name='hydration_check'); print('HYDRATED')",
        ],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "HYDRATED" in result.stdout


def test_gpu_replacement_preserves_frozen_gate():
    def gate(filename):
        tree = ast.parse((ROOT / "scripts" / filename).read_text())
        return ast.dump(
            next(
                n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "evaluate_gate"
            )
        )

    assert gate("report_pollutant_linear_v2_gpu.py") == gate("report_pollutant_linear.py")
