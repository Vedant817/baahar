#!/usr/bin/env python
"""Private scale-to-zero serving for a promoted remote Baahar LoRA adapter.

Deploy explicitly with ``uv run --group modal modal deploy scripts/serve_briefing_modal.py``.
No HTTP endpoint is exposed. Requires a serving.json promotion registry inside
the existing training Volume, written after selection and evaluation. Importing
this script constructs a cloud image only; no weights are downloaded locally.
"""

import json
import re
import sys
from pathlib import Path

import modal

ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "baahar-briefing-private"
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
volume = modal.Volume.from_name("baahar-training", create_if_missing=False)
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("torch==2.9.1", "transformers==4.57.6", "peft==0.18.1", "accelerate==1.15.0")
    .env({"HF_HOME": "/artifacts/hf-cache", "HF_HUB_OFFLINE": "1"})
    .add_local_file(str(ROOT / "src/baahar/briefing_contract.py"), "/opt/briefing_contract.py")
)
app = modal.App(APP_NAME, image=image)


def checked_artifact(root: Path, run_id: str, candidate: str) -> tuple[Path, str, str]:
    """Reject escapes, unknown candidates and missing/mismatched promotion records."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", run_id) or candidate not in CANDIDATES:
        raise ValueError("Invalid serving identity")
    model, revision = CANDIDATES[candidate]
    run_dir = root / "candidates" / run_id
    adapter = run_dir / candidate / "adapter"
    root_resolved = root.resolve()
    for path in (
        run_dir / "serving.json",
        adapter,
        adapter / "adapter_config.json",
        adapter / "adapter_model.safetensors",
    ):
        if not path.resolve().is_relative_to(root_resolved):
            raise ValueError("Artifact escapes the training volume")
    registry = json.loads((run_dir / "serving.json").read_text(encoding="utf-8"))
    required = {
        "run_id": run_id,
        "candidate": candidate,
        "model": model,
        "revision": revision,
        "status": "promoted",
        "contract_version": 1,
    }
    if not isinstance(registry, dict) or any(registry.get(k) != v for k, v in required.items()):
        raise ValueError("Candidate is not registered for serving")
    config = json.loads((adapter / "adapter_config.json").read_text(encoding="utf-8"))
    if config.get("base_model_name_or_path") != model:
        raise ValueError("Adapter base model differs from registry")
    if not (adapter / "adapter_model.safetensors").is_file():
        raise ValueError("Adapter weights are absent")
    return adapter, model, revision


@app.cls(
    gpu="L4",
    volumes={"/artifacts": volume},
    min_containers=0,
    max_containers=1,
    scaledown_window=30,
    timeout=120,
    startup_timeout=180,
    retries=0,
)
class BriefingModel:
    run_id: str = modal.parameter()
    candidate: str = modal.parameter()

    @modal.enter()
    def load(self):
        # Heavy imports execute exclusively inside the GPU container.
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer

        adapter, model, revision = checked_artifact(Path("/artifacts"), self.run_id, self.candidate)
        self.model_id = model
        self.revision = revision
        self.tokenizer = AutoTokenizer.from_pretrained(
            model, revision=revision, local_files_only=True
        )
        base = AutoModelForCausalLM.from_pretrained(
            model,
            revision=revision,
            local_files_only=True,
            torch_dtype=torch.bfloat16,
            device_map="auto",
        )
        self.model = PeftModel.from_pretrained(base, str(adapter), local_files_only=True)
        self.model.eval()

    @modal.method()
    def generate(self, facts: dict) -> dict:
        import time

        import torch

        sys.path.insert(0, "/opt")
        from briefing_contract import evaluate, render_messages

        started = time.perf_counter()
        messages = render_messages(facts)
        ids = self.tokenizer.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_tensors="pt",
        ).to(self.model.device)
        if ids.shape[-1] > 1024:
            raise ValueError("Briefing facts exceed the serving input limit")
        with torch.inference_mode():
            output = self.model.generate(
                ids,
                attention_mask=torch.ones_like(ids),
                do_sample=False,
                max_new_tokens=160,
                pad_token_id=self.tokenizer.eos_token_id,
            )
        generated = output[0, ids.shape[-1] :].tolist()
        eos = self.model.generation_config.eos_token_id
        eos_ids = set(eos if isinstance(eos, list) else [eos])
        terminated = bool(generated and generated[-1] in eos_ids)
        raw = self.tokenizer.decode(generated, skip_special_tokens=True).strip()
        return {
            "raw_text": raw,
            "run_id": self.run_id,
            "candidate": self.candidate,
            "model": self.model_id,
            "revision": self.revision,
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "output_tokens": len(generated),
            "terminated": terminated,
            "contract": evaluate(raw, {"facts": facts}),
        }
