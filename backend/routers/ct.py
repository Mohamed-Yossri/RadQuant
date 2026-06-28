"""CT Reader router — TotalSegmentator organ segmentation + volumes + report.

CT-specific: it runs the anatomical specialist (TotalSegmentator) that the chest
workstation and General Medical page do NOT, because cross-sectional CT needs a
3D-aware model. The brain (MedGemma) writes the report from the measured volumes.
"""
from __future__ import annotations

import asyncio
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from backend.deps import UPLOAD_DIR
from backend.schemas import CtAnalyzeOut

router = APIRouter(prefix="/api/ct", tags=["ct"])

_CT_DIR = Path("temp") / "ct"


@router.get("/slice/{study_id}/{fname}")
async def ct_slice(study_id: str, fname: str):
    """Serve a rendered CT slice (study-scoped, no path traversal)."""
    if "/" in study_id or "/" in fname or ".." in study_id or ".." in fname:
        raise HTTPException(400, "bad path")
    p = _CT_DIR / study_id / fname
    if not p.is_file() or p.suffix.lower() != ".png":
        raise HTTPException(404, "slice not found")
    return FileResponse(p)


@router.post("/analyze", response_model=CtAnalyzeOut)
async def analyze(file: UploadFile = File(...)):
    """Upload a CT volume → organ segmentation, volumes, report.

    Accepts a NIfTI file (``.nii``/``.nii.gz``), a DICOM series as a ``.zip`` of
    slices straight off a scanner/PACS (e.g. ``ct-lung-screening-nlst-series.zip``),
    or a single multi-frame (enhanced) ``.dcm``. A single *single-frame* ``.dcm``
    is just one slice — not a volume — and is rejected with guidance to zip the
    whole series.
    """
    name = (file.filename or "ct.nii.gz").lower()
    if name.endswith(".nii.gz") or name.endswith(".nii"):
        ext = ".nii.gz" if name.endswith(".nii.gz") else ".nii"
    elif name.endswith(".zip"):
        ext = ".zip"
    elif name.endswith(".dcm"):
        ext = ".dcm"
    else:
        raise HTTPException(
            400, "Upload a NIfTI volume (.nii/.nii.gz), a DICOM series (.zip of .dcm "
            "slices), or a multi-frame .dcm.")

    study_id = f"ct-{uuid.uuid4().hex[:8]}"
    dest = UPLOAD_DIR / f"{study_id}{ext}"
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    return await _run(str(dest), study_id)


@router.post("/sample", response_model=CtAnalyzeOut)
async def analyze_sample():
    """Run the bundled sample CT so the Reader is one-click testable."""
    from radquant.config import DATA_DIR  # noqa: F401  (kept for parity)

    sample = Path("data") / "sample_ct" / "example_ct.nii.gz"
    if not sample.is_file():
        raise HTTPException(404, "Sample CT not found on the server.")
    return await _run(str(sample), f"ct-sample-{uuid.uuid4().hex[:6]}")


async def _run(path: str, study_id: str) -> CtAnalyzeOut:
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, _analyze, path, study_id)
        report = await loop.run_in_executor(
            None, _report, result["middle_overlay_path"], result["volumes"])
    except ValueError as e:                       # bad/unsuitable input → actionable 400
        raise HTTPException(400, str(e))
    except Exception as e:  # noqa: BLE001        # genuine server-side failure
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"CT analysis failed: {e}")

    return CtAnalyzeOut(
        study_id=result["study_id"],
        n_slices=result["n_slices"],
        slices=result["slices"],
        volumes=result["volumes"],
        report=report,
    )


def _analyze(path: str, study_id: str):
    from radquant.nodes.ct import analyze_ct
    return analyze_ct(path, study_id=study_id)


def _report(middle_overlay_path: str, volumes):
    from radquant.nodes.ct import draft_ct_report
    if not middle_overlay_path:
        return "(no representative slice available)"
    return draft_ct_report(middle_overlay_path, volumes)
