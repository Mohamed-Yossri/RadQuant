"""Explainer router."""
from __future__ import annotations

import asyncio
from fastapi import APIRouter
from backend.schemas import ExplainIn, ExplainOut, GlossaryItem

router = APIRouter(prefix="/api", tags=["explainer"])


@router.post("/explain", response_model=ExplainOut)
async def explain(body: ExplainIn):
    loop = asyncio.get_event_loop()
    plain, glossary = await loop.run_in_executor(
        None, _run_explain, body.report
    )
    from radquant.nodes.explain import highlight_html
    highlighted = highlight_html(body.report, glossary)
    return ExplainOut(
        plain=plain,
        glossary=[GlossaryItem(term=t, definition=d) for t, d in glossary.items()],
        highlighted_html=highlighted,
    )


def _run_explain(report: str):
    from radquant.nodes.explain import explain_with_glossary
    return explain_with_glossary(report)
