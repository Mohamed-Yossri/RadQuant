"""General Medical router — modality-agnostic analysis via MedGemma only.

No CXR specialist tools run here (they would misfire on non-chest images); this
is purely MedGemma: detect the modality, write a domain-appropriate description,
and answer free-text questions. When the image is a chest X-ray we say so, and
the frontend offers a button to open it in the full CXR workstation instead.
"""
from __future__ import annotations

import asyncio
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.deps import UPLOAD_DIR
from backend.schemas import GeneralAnalyzeOut, GeneralVQAIn, GeneralVQAOut

router = APIRouter(prefix="/api/general", tags=["general"])


@router.post("/analyze", response_model=GeneralAnalyzeOut)
async def analyze(file: UploadFile = File(...)):
    """Upload any medical image → modality + structured description."""
    suffix = Path(file.filename or "img.png").suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".dcm", ".dicom"}:
        raise HTTPException(400, "Unsupported file type. Use PNG, JPG, or DICOM.")

    image_id = f"gen-{uuid.uuid4().hex[:10]}{suffix}"
    dest = UPLOAD_DIR / image_id
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    image_path = str(dest)

    if suffix in {".dcm", ".dicom"}:
        from radquant.foundation import DicomProcessorTool
        out, _ = DicomProcessorTool(temp_dir=str(UPLOAD_DIR))._run(image_path)
        image_path = out.get("image_path", image_path)
        image_id = Path(image_path).name

    loop = asyncio.get_event_loop()
    det = await loop.run_in_executor(None, _detect, image_path)
    desc = await loop.run_in_executor(None, _describe, image_path, det["modality"])

    return GeneralAnalyzeOut(
        image_id=image_id,
        image_url=f"/api/images/uploads/{image_id}",
        modality=det["modality"],
        region=det["region"],
        is_cxr=det["is_cxr"],
        description=desc,
    )


@router.post("/vqa", response_model=GeneralVQAOut)
async def vqa(body: GeneralVQAIn):
    """Free-text question answering over a previously analyzed image."""
    path = UPLOAD_DIR / body.image_id
    if not path.is_file():
        raise HTTPException(404, "Image not found — analyze it first.")
    loop = asyncio.get_event_loop()
    answer = await loop.run_in_executor(None, _vqa, str(path), body.question)
    return GeneralVQAOut(answer=answer)


# Lazy imports so the heavy model only loads when these endpoints are hit.
def _detect(p: str):
    from radquant.nodes.general import detect_modality
    return detect_modality(p)


def _describe(p: str, m: str):
    from radquant.nodes.general import describe
    return describe(p, m)


def _vqa(p: str, q: str):
    from radquant.nodes.general import vqa
    return vqa(p, q)
