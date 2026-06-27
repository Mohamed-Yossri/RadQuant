"""
radquant/config.py — credential and runtime resolution.

All credential access in the codebase goes through this module.
Reads from the live environment first, then from a .env file.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from repo root (no-op if file absent — env vars already set)
load_dotenv(Path(__file__).parent.parent / ".env", override=False)


def hf_token() -> str:
    v = os.environ.get("HF_TOKEN", "")
    if not v:
        raise EnvironmentError("HF_TOKEN not set. See .env.example")
    return v


def groq_key() -> str:
    # accept both names (Lightning secret is GROQ_TOKEN; plan used GROQ_API_KEY)
    v = os.environ.get("GROQ_TOKEN") or os.environ.get("GROQ_API_KEY", "")
    if not v:
        raise EnvironmentError("GROQ_TOKEN not set. See .env.example")
    return v


def nvidia_key() -> str:
    v = os.environ.get("NVIDIA_KEY", "")
    if not v:
        raise EnvironmentError("NVIDIA_KEY not set. Needed for eval only.")
    return v


def quant_mode() -> str:
    """Return 'bf16' or '4bit' based on env or auto-detection."""
    v = os.environ.get("RADQUANT_QUANT", "").lower()
    if v in ("bf16", "4bit"):
        return v
    # auto-detect
    try:
        import torch
        if torch.cuda.is_available():
            vram_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
            return "bf16" if vram_gb >= 20 else "4bit"
    except Exception:
        pass
    return "bf16"


def device() -> str:
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"
