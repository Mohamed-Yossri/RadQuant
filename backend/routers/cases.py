"""Cases router — vision overlays, draft generation, finalize."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from backend.deps import TEMP_DIR, get_worklist, save_worklist
from backend.schemas import (
    ChatIn,
    DraftOut,
    FinalizeIn,
    GradCAMOut,
    LocalizationFinding,
    LocalizeOut,
    ReportOut,
    SegmentOut,
)

router = APIRouter(prefix="/api/cases", tags=["cases"])


async def _gpu_task(fn, *args, what: str):
    """Run a GPU vision job in a thread; turn OOM into an actionable 503 and log faults.

    Several stages (Grad-CAM, localization, segmentation) load their own model on
    demand. On a busy 24 GB card the *first* such load can run the GPU out of
    memory — which otherwise surfaces as a useless generic 500. Here we free the
    cache and tell the user exactly what happened, and log the real traceback so
    any genuine fault is diagnosable.
    """
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, fn, *args)
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        msg = str(e)
        oom_types = tuple(t for t in (getattr(__import__("torch").cuda, "OutOfMemoryError", None),) if t)
        is_oom = isinstance(e, oom_types) or "out of memory" in msg.lower() or "CUDA error" in msg
        if is_oom:
            try:
                import torch
                torch.cuda.empty_cache()
            except Exception:
                pass
            raise HTTPException(
                503, f"{what} needs more GPU memory than is free right now — a large model "
                "was loading. Wait a moment and click again (it's cached after the first load).")
        raise HTTPException(500, f"{what} failed: {msg}")


def _require_case(case_id: str, wl):
    case = wl.get(case_id)
    if not case:
        raise HTTPException(404, f"Case {case_id!r} not found")
    return case


# ── Draft (SSE streaming) ────────────────────────────────────────────────────

async def _stream_draft(image_path: str, findings: dict) -> AsyncGenerator[str, None]:
    """Stream draft generation progress as SSE events."""
    def _sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"

    yield _sse("progress", {"step": "classifying", "message": "Running classifier…"})
    await asyncio.sleep(0)   # yield to event loop

    yield _sse("progress", {"step": "drafting", "message": "MedGemma drafting report…"})
    await asyncio.sleep(0)

    # Run in thread pool so we don't block the event loop
    loop = asyncio.get_event_loop()
    f_text, i_text, raw = await loop.run_in_executor(
        None, _run_draft, image_path, findings
    )

    yield _sse("progress", {"step": "done", "message": "Draft ready."})
    yield _sse("draft", {"findings": f_text, "impression": i_text, "raw": raw})


def _run_draft(image_path: str, findings: dict):
    from radquant.nodes.draft import draft_report
    return draft_report(image_path, findings)


@router.get("/{case_id}/draft")
async def stream_draft(case_id: str, wl=Depends(get_worklist)):
    """SSE endpoint: streams progress then the completed draft.

    Served over GET because the browser ``EventSource`` API (used by the
    frontend) only issues GET requests.
    """
    case = _require_case(case_id, wl)
    findings = case.findings
    if not findings:
        from radquant.nodes.classify import classify_image
        findings = classify_image(case.image_path)
        wl.add_from_findings(case_id, case.image_path, findings, status=case.status)
        save_worklist()

    return StreamingResponse(
        _stream_draft(case.image_path, findings),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Grad-CAM ─────────────────────────────────────────────────────────────────

@router.post("/{case_id}/gradcam", response_model=GradCAMOut)
async def gradcam(case_id: str, wl=Depends(get_worklist)):
    case = _require_case(case_id, wl)
    overlay_path, top = await _gpu_task(
        _run_gradcam, case.image_path, case.findings, what="Grad-CAM"
    )
    rel = Path(overlay_path).name
    return GradCAMOut(overlay_url=f"/api/images/temp/{rel}", top_finding=top)


def _run_gradcam(image_path: str, findings: dict):
    from radquant.nodes.visualize import gradcam_overlay
    return gradcam_overlay(image_path, findings=findings)


# ── Localization ──────────────────────────────────────────────────────────────

@router.post("/{case_id}/localize", response_model=LocalizeOut)
async def localize(case_id: str, wl=Depends(get_worklist)):
    case = _require_case(case_id, wl)
    findings, overlay_path = await _gpu_task(
        _run_localize, case.image_path, what="Localization"
    )

    from radquant.models.auditor import PRETTY
    from radquant.models.cv_tools import _region

    lf = [
        LocalizationFinding(
            label=f["label"],
            label_pretty=PRETTY.get(f["label"], f["label"]),
            box=f["box"],
            confidence=round(f["confidence"], 3),
            zone=_region(f["box"]),
        )
        for f in findings
    ]
    rel = Path(overlay_path).name if overlay_path else ""
    return LocalizeOut(
        overlay_url=f"/api/images/temp/grounding/{rel}" if rel else "",
        findings=lf,
    )


def _run_localize(image_path: str):
    from radquant.models.auditor import get_auditor, render_overlay
    findings = get_auditor().detect(image_path)
    overlay = render_overlay(image_path, findings) if findings else None
    return findings, overlay


# ── Segmentation ──────────────────────────────────────────────────────────────

@router.post("/{case_id}/segment", response_model=SegmentOut)
async def segment(case_id: str, wl=Depends(get_worklist)):
    case = _require_case(case_id, wl)
    return await _gpu_task(_run_segment, case.image_path, what="Segmentation")


def _run_segment(image_path: str) -> SegmentOut:
    import numpy as np
    from radquant.models.segmenter import get_segmenter, segment_overlay

    overlay_path, present = segment_overlay(image_path)
    _disp, masks = get_segmenter().segment(image_path)

    def width(m) -> int:
        cols = np.where(m.any(axis=0))[0]
        return int(cols.max() - cols.min()) if len(cols) else 0

    thorax = masks.get("Left Lung", np.zeros((1, 1))) | masks.get("Right Lung", np.zeros((1, 1)))
    hw = width(masks.get("Heart", np.zeros((1, 1))))
    tw = width(thorax)
    ctr = hw / tw if tw else 0.0
    flag = "enlarged (cardiomegaly)" if ctr > 0.5 else "normal"

    rel = Path(overlay_path).name
    return SegmentOut(
        overlay_url=f"/api/images/temp/{rel}",
        structures=present,
        cardiothoracic_ratio=round(ctr, 3) if hw else None,
        ctr_flag=flag,
    )


# ── Finalize ──────────────────────────────────────────────────────────────────

@router.post("/{case_id}/finalize", response_model=ReportOut)
async def finalize(case_id: str, body: FinalizeIn, wl=Depends(get_worklist)):
    case = _require_case(case_id, wl)
    report = f"FINDINGS: {body.findings}\n\nIMPRESSION: {body.impression}".strip()
    wl.set_status(case_id, "finalized")
    save_worklist()
    return ReportOut(final_report=report, case_id=case_id)


# ── Chat assistant (SSE streaming) ────────────────────────────────────────────

@router.post("/{case_id}/chat")
async def chat(case_id: str, body: ChatIn, wl=Depends(get_worklist)):
    """SSE: stream the tool-using assistant response."""
    q = body.question
    case = _require_case(case_id, wl)

    async def _generate():
        import json
        yield f"event: thinking\ndata: {json.dumps({'message': 'RadQuant is reasoning…'})}\n\n"
        await asyncio.sleep(0)

        loop = asyncio.get_event_loop()
        answer, tools_used = await loop.run_in_executor(
            None, _run_chat, case.image_path, q, case_id
        )
        yield f"event: answer\ndata: {json.dumps({'answer': answer, 'tools': tools_used})}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _run_chat(image_path: str, question: str, case_id: str):
    from radquant.assistant import build_assistant, ask
    agent, _ = build_assistant(image_path)
    return ask(agent, question, thread_id=case_id)
