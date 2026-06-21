#!/usr/bin/env python3
"""One-command environment setup for the RadQuant.

Idempotent: safe to re-run; each step skips work already done.

    python scripts/setup.py [--skip-install] [--skip-weights] [--skip-data]
                            [--with-openi] [--force-install]

The only human inputs are credentials (HF_TOKEN + GROQ_TOKEN, normally provided
as Lightning Studio secrets) and a one-time MedGemma license acceptance on HF
(already auto-granted for this token at the time of writing).

Storage-frugal by design: no pip cache, shallow MedRAX clone, the
ChestAgentBench zip is deleted after extraction, and the OpenI sample is
opt-in (the explainer is text-only and does not need it).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import urllib.error
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
EXTERNAL = ROOT / "external"

# Keep these in sync with radquant/config.py (duplicated here so setup.py runs
# with ZERO project imports before `pip install -e .` has happened).
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL = "openai/gpt-oss-120b"
MEDGEMMA_REPO = "google/medgemma-1.5-4b-it"
XRV_WEIGHTS = "densenet121-res224-all"
CHESTAGENTBENCH_REPO = "wanglab/chest-agent-bench"

SUMMARY: dict[str, str] = {}


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def section(title: str) -> None:
    print(f"\n{'=' * 64}\n  {title}\n{'=' * 64}")


def ok(msg: str) -> None:
    print(f"  \033[32m✓\033[0m {msg}")


def warn(msg: str) -> None:
    print(f"  \033[33m!\033[0m {msg}")


def die(msg: str) -> None:
    print(f"  \033[31m✗ {msg}\033[0m")
    sys.exit(1)


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, **kw)


def load_dotenv_into_environ() -> None:
    """Load .env WITHOUT overriding real env vars (Lightning secrets win)."""
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def write_env_example_if_missing() -> None:
    ex = ROOT / ".env.example"
    if ex.exists():
        return
    ex.write_text(
        "HF_TOKEN=\n# Lightning secret is named GROQ_TOKEN (GROQ_API_KEY also accepted)\nGROQ_TOKEN=\n"
    )


# --------------------------------------------------------------------------- #
# steps
# --------------------------------------------------------------------------- #
def step_validate_env() -> tuple[str, str]:
    section("1/10  Validate credentials")
    load_dotenv_into_environ()
    hf = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
    groq = os.environ.get("GROQ_TOKEN") or os.environ.get("GROQ_API_KEY")
    if not hf or not groq:
        write_env_example_if_missing()
        missing = [n for n, v in (("HF_TOKEN", hf), ("GROQ_TOKEN", groq)) if not v]
        die(
            f"Missing credential(s): {', '.join(missing)}.\n"
            "  Provide them as Lightning Studio secrets, or fill out .env "
            "(see .env.example and the 'User actions required' section of PLAN.md)."
        )
    ok(f"HF_TOKEN present (len {len(hf)})")
    ok(f"GROQ token present (len {len(groq)})")
    SUMMARY["credentials"] = "HF_TOKEN + GROQ_TOKEN resolved"
    return hf, groq


def step_detect_gpu() -> str:
    section("2/10  Detect GPU & choose quantization")
    quant, name, vram = "bf16", "unknown", 0
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total",
             "--format=csv,noheader,nounits"],
            text=True,
        ).strip().splitlines()[0]
        name, vram_s = [x.strip() for x in out.split(",")]
        vram = int(float(vram_s))
        quant = "4bit" if vram <= 16000 else "bf16"
        ok(f"GPU: {name} | {vram} MiB total")
        ok(f"Quantization → {quant} "
           f"({'<=16 GB: 4-bit' if quant == '4bit' else '>16 GB: bf16 (faster, no dequant overhead)'})")
    except Exception as e:  # noqa: BLE001
        warn(f"nvidia-smi unavailable ({e}); defaulting to bf16 (CPU/unknown GPU).")

    (ROOT / ".env.runtime").write_text(
        f"RADQUANT_QUANT={quant}\n"
        f"RADQUANT_DEVICE={name}\n"
        f"RADQUANT_VRAM_MB={vram}\n"
    )
    ok("Wrote .env.runtime")
    SUMMARY["gpu"] = f"{name}, {vram} MiB, quant={quant}"
    return quant


def _transformers_ok() -> bool:
    try:
        import transformers  # noqa
        from packaging.version import Version
        return Version(transformers.__version__) >= Version("4.57.1")
    except Exception:  # noqa: BLE001
        return False


def step_install(quant: str, force: bool) -> None:
    section("3/10  Install dependencies (pip install -e .)")
    if not force and _transformers_ok():
        ok("Core deps already satisfied (transformers>=4.57.1); skipping pip. "
           "Use --force-install to reinstall.")
        SUMMARY["install"] = "skipped (already satisfied)"
        return
    target = ".[quant]" if quant == "4bit" else "."
    # --no-cache-dir: do not persist wheels (storage-frugal).
    cp = run([sys.executable, "-m", "pip", "install", "--no-cache-dir", "-e", target],
             cwd=str(ROOT))
    if cp.returncode != 0:
        die("pip install failed. See output above.")
    ok(f"Installed radquant + deps ({target})")
    SUMMARY["install"] = f"pip install -e {target}"


def step_hf_login(hf: str) -> None:
    section("4/10  HuggingFace auth")
    os.environ["HF_TOKEN"] = hf
    try:
        from huggingface_hub import login
        login(token=hf, add_to_git_credential=False)
        ok("huggingface_hub login OK")
    except Exception as e:  # noqa: BLE001
        # transformers/hub also read HF_TOKEN from env, so this is non-fatal.
        warn(f"hub login skipped ({e}); relying on HF_TOKEN env var.")
    SUMMARY["hf_auth"] = "ok"


def step_cache_medgemma(skip: bool) -> None:
    section("5/10  Cache MedGemma 1.5 4B weights")
    if skip:
        warn("skipped (--skip-weights)")
        return
    from huggingface_hub import snapshot_download
    from huggingface_hub.utils import GatedRepoError, HfHubHTTPError
    t0 = time.time()
    try:
        # Download (resumable; skips files already cached). No VRAM used here —
        # the actual model load is exercised by smoke_test.py.
        path = snapshot_download(
            MEDGEMMA_REPO,
            allow_patterns=["*.json", "*.safetensors", "*.model", "*.txt",
                            "tokenizer*", "*.py"],
        )
    except GatedRepoError:
        die(
            "MedGemma weights are gated for this token. Accept the license at\n"
            f"  https://huggingface.co/{MEDGEMMA_REPO}\n"
            "  (log in, click 'Acknowledge license'), then re-run setup."
        )
        return
    except HfHubHTTPError as e:
        if "403" in str(e):
            die(f"403 from HF for {MEDGEMMA_REPO}. Accept the license at "
                f"https://huggingface.co/{MEDGEMMA_REPO} and re-run.")
        raise
    size_gb = sum(f.stat().st_size for f in Path(path).rglob("*") if f.is_file()) / 1e9
    ok(f"Cached ({size_gb:.1f} GB) in {time.time() - t0:.0f}s → {path}")
    SUMMARY["medgemma"] = f"{size_gb:.1f} GB cached"


def step_cache_xrv(skip: bool) -> None:
    section("6/10  Cache TorchXRayVision DenseNet-121 weights")
    if skip:
        warn("skipped (--skip-weights)")
        return
    import torchxrayvision as xrv  # triggers weight download on first load
    t0 = time.time()
    xrv.models.DenseNet(weights=XRV_WEIGHTS)
    ok(f"DenseNet({XRV_WEIGHTS}) ready in {time.time() - t0:.0f}s")
    SUMMARY["xrv"] = XRV_WEIGHTS


def step_clone_medrax() -> None:
    section("7/10  Vendor MedRAX (shallow clone)")
    dest = EXTERNAL / "medrax"
    # We strip .git after cloning, so test for the vendored package instead.
    if (dest / "medrax").exists() or (dest / "setup.py").exists():
        ok(f"Already present at {dest}")
        SUMMARY["medrax"] = "present"
        return
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)  # clean partial clone
    EXTERNAL.mkdir(exist_ok=True)
    cp = run(["git", "clone", "--depth", "1",
              "https://github.com/bowang-lab/MedRAX.git", str(dest)])
    if cp.returncode != 0:
        warn("MedRAX clone failed (network?). Phase 1 needs it; re-run later.")
        SUMMARY["medrax"] = "FAILED"
        return
    # Strip the upstream .git to save storage; we vendor a snapshot, not a remote.
    shutil.rmtree(dest / ".git", ignore_errors=True)
    ok(f"Cloned (shallow, .git removed) → {dest}")
    SUMMARY["medrax"] = "vendored"


def step_download_chestagentbench(skip: bool) -> None:
    section("8/10  Download ChestAgentBench (figures + metadata)")
    if skip:
        warn("skipped (--skip-data)")
        return
    out_dir = DATA / "chestagentbench"
    figures_dir = out_dir / "figures"
    if figures_dir.exists() and any(figures_dir.iterdir()):
        ok(f"Already extracted at {figures_dir}")
        SUMMARY["chestagentbench"] = "present"
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    from huggingface_hub import hf_hub_download
    for fname in ("figures.zip", "metadata.jsonl"):
        p = hf_hub_download(CHESTAGENTBENCH_REPO, fname, repo_type="dataset",
                            local_dir=str(out_dir))
        ok(f"downloaded {fname}")
        if fname.endswith(".zip"):
            with zipfile.ZipFile(p) as zf:
                zf.extractall(out_dir)
            os.remove(p)  # storage-frugal: drop the zip after extraction
            ok("extracted figures.zip and removed the archive")
    n = sum(1 for _ in figures_dir.rglob("*") if _.suffix.lower() in {".png", ".jpg", ".jpeg"})
    ok(f"{n} figure images available")
    SUMMARY["chestagentbench"] = f"{n} images"


def step_openi_sample(enabled: bool) -> None:
    section("9/10  OpenI / Indiana CXR sample (opt-in)")
    if not enabled:
        ok("skipped (default; pass --with-openi to fetch). Explainer is text-only.")
        SUMMARY["openi"] = "skipped"
        return
    out = DATA / "openi_sample"
    if out.exists() and any(out.iterdir()):
        ok(f"Already present at {out}")
        return
    try:
        from datasets import load_dataset
        ds = load_dataset("ayyuce/Indiana_University_Chest_X-ray_Collection",
                          split="train", streaming=True)
        out.mkdir(parents=True, exist_ok=True)
        rows = []
        for i, row in enumerate(ds):
            if i >= 50:
                break
            rows.append({k: v for k, v in row.items()
                         if isinstance(v, (str, int, float))})
        (out / "reports.jsonl").write_text(
            "\n".join(json.dumps(r) for r in rows))
        ok(f"Saved {len(rows)} report rows → {out}")
        SUMMARY["openi"] = f"{len(rows)} rows"
    except Exception as e:  # noqa: BLE001
        warn(f"OpenI fetch failed ({e}); non-fatal, skipping.")
        SUMMARY["openi"] = "failed (non-fatal)"


def step_validate_groq(groq: str) -> None:
    section("10/10  Validate Groq orchestrator endpoint")
    body = json.dumps({
        "model": GROQ_MODEL,
        # gpt-oss-120b is a REASONING model: low max_tokens leaves no visible
        # content (all budget goes to hidden reasoning). Give it room.
        "messages": [{"role": "user", "content": "Reply with the single word: PONG"}],
        "max_tokens": 256,
        "temperature": 0,
    }).encode()
    req = urllib.request.Request(
        f"{GROQ_BASE_URL}/chat/completions", data=body,
        headers={"Authorization": f"Bearer {groq}", "Content-Type": "application/json",
                 # Groq sits behind Cloudflare, which 403s (err 1010) the default
                 # urllib User-Agent. Any explicit UA passes.
                 "User-Agent": "radquant/0.1"},
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        die(f"Groq returned HTTP {e.code}: {e.read().decode()[:200]}")
        return
    dt = time.time() - t0
    content = data["choices"][0]["message"]["content"].strip()
    if not content:
        warn(f"Empty content (model returned only reasoning); endpoint is reachable. {dt:.1f}s")
    else:
        ok(f"Groq '{GROQ_MODEL}' replied {content!r} in {dt:.1f}s")
    SUMMARY["groq"] = f"{GROQ_MODEL}, {dt:.1f}s latency"


# --------------------------------------------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skip-install", action="store_true")
    ap.add_argument("--force-install", action="store_true")
    ap.add_argument("--skip-weights", action="store_true")
    ap.add_argument("--skip-data", action="store_true")
    ap.add_argument("--with-openi", action="store_true")
    args = ap.parse_args()

    print("RadQuant — automated setup")
    hf, groq = step_validate_env()
    quant = step_detect_gpu()
    if not args.skip_install:
        step_install(quant, args.force_install)
    else:
        warn("install skipped (--skip-install)")
    step_hf_login(hf)
    step_cache_medgemma(args.skip_weights)
    step_cache_xrv(args.skip_weights)
    step_clone_medrax()
    step_download_chestagentbench(args.skip_data)
    step_openi_sample(args.with_openi)
    step_validate_groq(groq)

    section("Summary")
    for k, v in SUMMARY.items():
        print(f"  {k:16} {v}")
    print("\n  \033[32m✓ Setup complete.\033[0m "
          "Next: python scripts/smoke_test.py\n")


if __name__ == "__main__":
    main()
