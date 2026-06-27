"""Worklist CRUD router."""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from backend.deps import UPLOAD_DIR, get_worklist, save_worklist
from backend.schemas import CaseOut, FindingItem, StatusUpdate, WorklistOut
from radquant.nodes.triage import tier_of

router = APIRouter(prefix="/api/worklist", tags=["worklist"])


def _case_to_out(case) -> CaseOut:
    top = [
        FindingItem(label=k, probability=round(v, 3), tier=tier_of(k))
        for k, v in case.top(5)
    ]
    return CaseOut(
        case_id=case.case_id,
        image_path=case.image_path,
        urgency_score=round(case.urgency_score, 3),
        status=case.status,
        findings=case.findings,
        top_findings=top,
    )


@router.get("", response_model=WorklistOut)
async def list_worklist(wl=Depends(get_worklist)):
    cases = wl.sorted(descending=True)
    pending = sum(1 for c in cases if c.status == "pending")
    return WorklistOut(
        cases=[_case_to_out(c) for c in cases],
        total=len(cases),
        pending=pending,
    )


@router.post("/upload", response_model=CaseOut)
async def upload_image(
    file: UploadFile = File(...),
    wl=Depends(get_worklist),
):
    """Upload a CXR image (PNG/JPG/DCM), classify it, and add to worklist."""
    suffix = Path(file.filename or "img.png").suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".dcm", ".dicom"}:
        raise HTTPException(400, "Unsupported file type. Use PNG, JPG, or DCM.")

    case_id = f"case-{uuid.uuid4().hex[:8]}"
    dest = UPLOAD_DIR / f"{case_id}{suffix}"
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Run DICOM conversion if needed
    image_path = str(dest)
    if suffix in {".dcm", ".dicom"}:
        from radquant.foundation import DicomProcessorTool
        out, _ = DicomProcessorTool(temp_dir=str(UPLOAD_DIR))._run(image_path)
        image_path = out.get("image_path", image_path)

    # Classify
    from radquant.nodes.classify import classify_image
    findings = classify_image(image_path)

    case = wl.add_from_findings(case_id, image_path, findings)
    save_worklist()
    return _case_to_out(case)


@router.post("/seed-demo", response_model=WorklistOut)
async def seed_demo(n: int = 8, wl=Depends(get_worklist)):
    """Seed the worklist from the bundled real frontal chest X-rays.

    Uses ``data.demo_cxr`` (actual CXRs the classifier was trained on), NOT
    ``data.sample`` (ChestAgentBench figures — CT/MRI/histology — which are
    out-of-distribution for the CXR classifier and only meant for the VQA eval).
    """
    from radquant.data import demo_cxr
    from radquant.nodes.classify import classify_image

    paths = demo_cxr(n)
    for i, p in enumerate(paths):
        findings = classify_image(str(p))
        wl.add_from_findings(f"demo-{i:02d}", str(p), findings)
    save_worklist()
    cases = wl.sorted(descending=True)
    pending = sum(1 for c in cases if c.status == "pending")
    return WorklistOut(
        cases=[_case_to_out(c) for c in cases],
        total=len(cases),
        pending=pending,
    )


@router.delete("/clear")
async def clear_worklist(wl=Depends(get_worklist)):
    from radquant.worklist import Worklist
    global _worklist  # noqa: PLW0603
    from backend import deps
    deps._worklist = Worklist()
    save_worklist()
    return {"cleared": True}


@router.get("/{case_id}", response_model=CaseOut)
async def get_case(case_id: str, wl=Depends(get_worklist)):
    case = wl.get(case_id)
    if not case:
        raise HTTPException(404, f"Case {case_id!r} not found")
    return _case_to_out(case)


@router.patch("/{case_id}/status", response_model=CaseOut)
async def update_status(
    case_id: str,
    body: StatusUpdate,
    wl=Depends(get_worklist),
):
    case = wl.get(case_id)
    if not case:
        raise HTTPException(404, f"Case {case_id!r} not found")
    wl.set_status(case_id, body.status)
    save_worklist()
    return _case_to_out(wl.get(case_id))


@router.delete("/{case_id}")
async def delete_case(case_id: str, wl=Depends(get_worklist)):
    if not wl.get(case_id):
        raise HTTPException(404, f"Case {case_id!r} not found")
    wl._cases.pop(case_id)
    save_worklist()
    return {"deleted": case_id}
