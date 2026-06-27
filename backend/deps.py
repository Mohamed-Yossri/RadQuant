"""Shared FastAPI dependencies — process-wide singletons.

All heavy objects (classifier, worklist) are initialised once at startup and
injected via FastAPI's dependency system. This mirrors the singleton pattern
already used in radquant.nodes.classify and radquant.models.medgemma.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make the repo root importable regardless of where uvicorn is launched from.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from radquant.worklist import Worklist
from radquant.config import DATA_DIR

# ── Worklist singleton ───────────────────────────────────────────────────────

_worklist: Worklist | None = None


def get_worklist() -> Worklist:
    """FastAPI dependency: return the process-wide Worklist."""
    global _worklist
    if _worklist is None:
        _worklist = Worklist.load()
    return _worklist


def save_worklist() -> None:
    """Persist the in-memory worklist to disk."""
    if _worklist is not None:
        _worklist.save()


# ── Upload directory ─────────────────────────────────────────────────────────

UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

TEMP_DIR = DATA_DIR / "temp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)
