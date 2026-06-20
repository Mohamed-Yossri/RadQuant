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
MEDGEMMA_REPO = "google/medgemma-1.5-4b-it"
XRV_WEIGHTS = "densenet121-res224-all"
CHESTAGENTBENCH_REPO = "wanglab/chest-agent-bench"  # canonical id


def _load_dotenv() -> None:
    """Best-effort load of .env / .env.runtime WITHOUT overriding real env vars.

    Live environment (Lightning secrets) always wins over file contents.
    """
    for name in (".env", ".env.runtime"):
        path = ROOT / name
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
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


def quant() -> str:
    """'4bit' or 'bf16'. Resolved from .env.runtime (written by setup.py),
    defaulting to bf16 if unset."""
    _load_dotenv()
    return os.environ.get("RADCOPILOT_QUANT", "bf16")
