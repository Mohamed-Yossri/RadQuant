"""RadQuant API — FastAPI entrypoint.

Assembles the routers (worklist, cases, qc, explainer, insights), serves the
overlay/upload images, and exposes a health probe. Launch with:

    uvicorn backend.main:app --host 0.0.0.0 --port 8000

The Next.js frontend talks to this via its ``/api/:path*`` rewrite (see
``frontend/next.config.js``); in dev that points at ``http://127.0.0.1:8000``.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make the repo root importable regardless of where uvicorn is launched from.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.deps import get_worklist
from backend.routers import cases, ct, explain, general, insights, qc, worklist
from radquant.config import DATA_DIR

app = FastAPI(
    title="RadQuant API",
    version="0.1.0",
    description="Privacy-first AI workstation for chest X-rays — research demo.",
)

# The frontend is served same-origin via Next rewrites in production, but allow
# any origin in dev (and when reached through a tunnel) so the SPA can call us.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(worklist.router)
app.include_router(cases.router)
app.include_router(qc.router)
app.include_router(explain.router)
app.include_router(insights.router)
app.include_router(general.router)
app.include_router(ct.router)


@app.get("/api/health", tags=["meta"])
async def health():
    return {"status": "ok", "service": "radquant-api"}


# ── Image serving ─────────────────────────────────────────────────────────────
# Overlays (Grad-CAM / segmentation / grounding) land in ``<root>/temp/...`` with
# unique uuid filenames; uploads land in ``data/uploads`` with unique case-id
# filenames. Both are resolved by basename, so the exact sub-path the frontend
# guesses (e.g. /api/images/temp/grounding/x.png) doesn't have to be precise.
_IMAGE_ROOTS = [_ROOT / "temp", DATA_DIR / "uploads", DATA_DIR / "temp"]
_IMAGE_EXTS = {".png", ".jpg", ".jpeg"}


@app.get("/api/images/{rest:path}", tags=["images"])
async def serve_image(rest: str):
    name = Path(rest).name  # strip any directory component (no traversal)
    if not name or Path(name).suffix.lower() not in _IMAGE_EXTS:
        raise HTTPException(404, "Not an image")
    for root in _IMAGE_ROOTS:
        if not root.exists():
            continue
        hit = next((p for p in root.rglob(name) if p.is_file()), None)
        if hit:
            return FileResponse(hit)
    raise HTTPException(404, f"Image {name!r} not found")


@app.get("/api/cases/{case_id}/image", tags=["images"])
async def case_image(case_id: str):
    """Serve a case's *original* X-ray by id.

    Case images come from the ChestAgentBench figures where basenames collide
    (every study has a ``figure_N.jpg``), so we resolve via the stored absolute
    ``image_path`` rather than by filename.
    """
    case = get_worklist().get(case_id)
    if not case:
        raise HTTPException(404, f"Case {case_id!r} not found")
    p = Path(case.image_path)
    if not p.is_file():
        raise HTTPException(404, f"Image for {case_id!r} missing on disk")
    return FileResponse(p)
