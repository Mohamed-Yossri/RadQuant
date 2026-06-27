"""Central credential & runtime resolution.

One place that knows the real environment-variable names so the rest of the
codebase never has to. Notably: the Lightning secret for Groq is ``GROQ_TOKEN``
(the PLAN.md draft called it ``GROQ_API_KEY``); we accept either.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL = "openai/gpt-oss-120b"          # primary orchestrator
GROQ_MODEL_FALLBACK = "llama-3.3-70b-versatile"  # higher RPD for bulk eval
# NVIDIA NIM — used as the Phase 8 eval orchestrator (no daily cap, ~40 RPM).
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL = "meta/llama-3.3-70b-instruct"
MEDGEMMA_REPO = "google/medgemma-1.5-4b-it"
XRV_WEIGHTS = "densenet121-res224-all"
CHESTAGENTBENCH_REPO = "wanglab/chest-agent-bench"  # canonical id


def _load_dotenv() -> None:
    """Best-effort load of .env / .env.runtime WITHOUT overriding real env vars.

    Live environment (Lightning secrets) always wins over file contents.
    Handles Windows-style CRLF line endings transparently.
    """
    for name in (".env", ".env.runtime"):
        path = ROOT / name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip().rstrip("\r")  # handle CRLF on Windows
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip('"').strip("'")
            os.environ.setdefault(key, val)


def hf_token() -> str | None:
    _load_dotenv()
    return os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")


def groq_key() -> str | None:
    _load_dotenv()
    return os.environ.get("GROQ_TOKEN") or os.environ.get("GROQ_API_KEY")


def nvidia_key() -> str | None:
    """NVIDIA NIM key. The Lightning secret for this project is named NVIDIA_KEY."""
    _load_dotenv()
    return (os.environ.get("NVIDIA_KEY") or os.environ.get("NVIDIA_API_KEY")
            or os.environ.get("NIM_API_KEY"))


def quant() -> str:
    """'4bit' or 'bf16'. Resolved from .env.runtime (written by setup.py),
    defaulting to bf16 if unset."""
    _load_dotenv()
    return os.environ.get("RADQUANT_QUANT", "bf16")


def device() -> str:
    """Auto-detect the best available compute device.

    Returns 'cuda' if an NVIDIA GPU is available, otherwise 'cpu'.
    Respects RADQUANT_DEVICE env var if explicitly set to override.
    """
    _load_dotenv()
    explicit = os.environ.get("RADQUANT_DEVICE")
    if explicit:
        return explicit

    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
    except ImportError:
        pass
    return "cpu"
