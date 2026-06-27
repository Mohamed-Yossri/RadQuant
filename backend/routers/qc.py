"""QC router."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.deps import get_worklist
from backend.schemas import QCIn, QCOut, OmissionItem

router = APIRouter(prefix="/api/cases", tags=["qc"])


@router.post("/{case_id}/qc", response_model=QCOut)
async def run_qc(case_id: str, body: QCIn, wl=Depends(get_worklist)):
    import asyncio
    from radquant.nodes.qc import find_omissions
    from radquant.worklist import Worklist

    case = wl.get(case_id)
    findings = case.findings if case else {}

    loop = asyncio.get_event_loop()
    omissions = await loop.run_in_executor(
        None, find_omissions, body.report, findings
    )
    return QCOut(
        omissions=[OmissionItem(**o) for o in omissions]
    )
