"""
scripts/setup.py — Idempotent environment setup for RadQuant.

Run once on a fresh Lightning.ai studio:
    python scripts/setup.py

What it does (skips steps already done):
  1. Validates credentials (HF_TOKEN, GROQ_TOKEN)
  2. Detects GPU / sets quantization mode
  3. Installs dependencies  (pip install -e .)
  4. Caches MedGemma weights (~8 GB)
  5. Caches TorchXRayVision DenseNet-121 weights
  6. Downloads ChestAgentBench dataset
  7. Validates Groq endpoint
  8. Prints environment summary
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# ── load .env early ───────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=False)

PASS = "✓"
FAIL = "✗"
WARN = "⚠"


def run(cmd: str, **kwargs) -> int:
    print(f"  $ {cmd}")
    result = subprocess.run(cmd, shell=True, **kwargs)
    return result.returncode


def section(title: str) -> None:
    print(f"\n{'─'*55}")
    print(f"  {title}")
    print(f"{'─'*55}")


# ── 1. Credentials ────────────────────────────────────────────────────────────
section("1. Credentials")

hf_token = os.environ.get("HF_TOKEN", "")
groq_token = os.environ.get("GROQ_TOKEN") or os.environ.get("GROQ_API_KEY", "")

if not hf_token:
    print(f"  {FAIL} HF_TOKEN not set.")
    print("     Copy .env.example → .env and fill in your HuggingFace token.")
    print("     Get one at: https://huggingface.co/settings/tokens")
    sys.exit(1)
print(f"  {PASS} HF_TOKEN set ({hf_token[:6]}…)")

if not groq_token:
    print(f"  {WARN} GROQ_TOKEN not set — Groq orchestrator and eval will not work.")
    print("     Get one at: https://console.groq.com")
else:
    print(f"  {PASS} GROQ_TOKEN set ({groq_token[:6]}…)")

# ── 2. GPU / quantization ─────────────────────────────────────────────────────
section("2. GPU detection")
try:
    import torch
    if torch.cuda.is_available():
        props = torch.cuda.get_device_properties(0)
        vram_gb = props.total_memory / 1e9
        quant = "bf16" if vram_gb >= 20 else "4bit"
        print(f"  {PASS} {props.name}  VRAM={vram_gb:.1f} GB  → quant={quant}")
    else:
        quant = "bf16"
        print(f"  {WARN} No CUDA GPU detected — will run on CPU (very slow)")
except ImportError:
    quant = "bf16"
    print(f"  {WARN} PyTorch not yet installed")

os.environ["RADQUANT_QUANT"] = quant

# ── 3. Install dependencies ───────────────────────────────────────────────────
section("3. Dependencies")
rc = run(f"{sys.executable} -m pip install -e '{ROOT}' --no-cache-dir -q")
if rc != 0:
    print(f"  {FAIL} pip install failed (exit {rc})")
    sys.exit(1)
print(f"  {PASS} Dependencies installed")

# ── 4. MedGemma weights ───────────────────────────────────────────────────────
section("4. MedGemma weights (google/medgemma-1.5-4b-it)")
MODEL_ID = "google/medgemma-1.5-4b-it"
try:
    from huggingface_hub import hf_hub_download, snapshot_download
    from huggingface_hub.utils import HfHubHTTPError
    print("  Checking / downloading weights …")
    t0 = time.time()
    snapshot_download(MODEL_ID, token=hf_token, ignore_patterns=["*.ot", "flax*", "tf_*"])
    elapsed = time.time() - t0
    print(f"  {PASS} MedGemma cached ({elapsed:.0f}s)")
except Exception as exc:
    if "403" in str(exc) or "401" in str(exc):
        print(f"  {FAIL} Access denied — accept the license at:")
        print(f"        https://huggingface.co/google/medgemma-1.5-4b-it")
        sys.exit(1)
    print(f"  {FAIL} MedGemma download failed: {exc}")
    sys.exit(1)

# ── 5. TorchXRayVision ────────────────────────────────────────────────────────
section("5. TorchXRayVision DenseNet-121 weights")
try:
    import torchxrayvision as xrv
    _ = xrv.models.DenseNet(weights="densenet121-res224-all")
    print(f"  {PASS} DenseNet-121 weights cached")
except Exception as exc:
    print(f"  {WARN} TorchXRayVision weight download failed: {exc}")
    print("        Will retry on first classify call.")

# ── 6. ChestAgentBench dataset ────────────────────────────────────────────────
section("6. ChestAgentBench dataset")
bench_dir = ROOT / "data" / "chestagentbench"
figures_dir = bench_dir / "figures"

if figures_dir.exists() and any(figures_dir.iterdir()):
    print(f"  {PASS} ChestAgentBench already present ({sum(1 for _ in figures_dir.iterdir())} files)")
else:
    print("  Downloading ChestAgentBench …")
    bench_dir.mkdir(parents=True, exist_ok=True)
    rc = run(
        f"huggingface-cli download wanglab/chest-agent-bench "
        f"--repo-type dataset --include 'figures.zip' 'metadata.jsonl' "
        f"--local-dir '{bench_dir}' --token {hf_token}",
    )
    if rc != 0:
        print(f"  {WARN} ChestAgentBench download failed — eval will not work")
    else:
        zip_path = bench_dir / "figures.zip"
        if zip_path.exists():
            import zipfile
            print("  Extracting figures.zip …")
            with zipfile.ZipFile(zip_path) as z:
                z.extractall(bench_dir)
            zip_path.unlink()
            print(f"  {PASS} Extracted {sum(1 for _ in figures_dir.glob('*'))} figures")

# ── 7. Groq endpoint ──────────────────────────────────────────────────────────
section("7. Groq endpoint")
if groq_token:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=groq_token, base_url="https://api.groq.com/openai/v1")
        t0 = time.time()
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": "Reply with OK"}],
            max_tokens=5,
        )
        latency_ms = (time.time() - t0) * 1000
        answer = resp.choices[0].message.content or ""
        print(f"  {PASS} Groq reachable — latency {latency_ms:.0f}ms — response: {answer[:20]}")
    except Exception as exc:
        print(f"  {WARN} Groq test failed: {exc}")
else:
    print(f"  {WARN} Skipped (no GROQ_TOKEN)")

# ── 8. Summary ────────────────────────────────────────────────────────────────
section("Summary")
print(f"  GPU quant:        {quant}")
print(f"  MedGemma:         google/medgemma-1.5-4b-it  ✓")
print(f"  ChestAgentBench:  {figures_dir} ({sum(1 for _ in figures_dir.glob('*')) if figures_dir.exists() else 0} images)")
print(f"  Groq:             {'set' if groq_token else 'NOT SET'}")
print()
print(f"  {PASS} Setup complete.")
print()
print("  To launch the app:")
print("    streamlit run radquant/ui/app.py")
print()
print("  To validate:")
print("    python scripts/smoke_test.py")
