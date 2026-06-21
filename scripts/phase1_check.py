#!/usr/bin/env python3
"""Phase 1 verification: the stripped MedRAX foundation works end-to-end.

Part A — direct tool sanity (no LLM): classifier, DICOM processor, visualizer.
Part B — full Groq-orchestrated agent run on a sample CXR, with the reasoning
         + tool-call trace printed.

Run: python scripts/phase1_check.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from radquant.data import sample  # noqa: E402


def hr(title: str) -> None:
    print(f"\n{'=' * 64}\n  {title}\n{'=' * 64}")


def main() -> None:
    img = str(sample(1)[0])

    # --- Part A: tools directly ------------------------------------------- #
    hr("A. Direct tool sanity (no LLM)")
    from radquant.foundation import (
        ChestXRayClassifierTool,
        DicomProcessorTool,
        ImageVisualizerTool,
    )

    print(f"sample image: {img}")

    clf = ChestXRayClassifierTool(device="cuda")
    preds, meta = clf._run(img)
    assert "error" not in preds, preds
    top = sorted(preds.items(), key=lambda kv: kv[1], reverse=True)[:3]
    print("  classifier top-3:", ", ".join(f"{k}={v:.2f}" for k, v in top))

    viz = ImageVisualizerTool()
    out, _ = viz._run(img)
    assert out.get("image_path") == img, out
    print("  visualizer OK ->", out["image_path"])

    # DICOM: use pydicom's built-in sample (no download — see PLAN.md).
    from pydicom.data import get_testdata_files
    dcm_path = get_testdata_files("CT_small.dcm")[0]
    dproc = DicomProcessorTool(temp_dir="temp")
    dout, dmeta = dproc._run(dcm_path)
    assert "image_path" in dout, dout
    print(f"  DICOM {Path(dcm_path).name} -> {dout['image_path']} "
          f"(Modality={dmeta.get('Modality')})")

    # --- Part B: full agent ----------------------------------------------- #
    hr("B. Groq-orchestrated agent (reasoning trace)")
    from langchain_core.messages import HumanMessage
    from radquant.foundation import build_agent

    agent, tools = build_agent(device="cuda", temp_dir="temp")
    print("tools registered:", list(tools))

    query = (f"Classify this chest X-ray and tell me the three most likely "
             f"findings with their probabilities. Image path: {img}")
    result = agent.workflow.invoke(
        {"messages": [HumanMessage(content=query)]},
        config={"configurable": {"thread_id": "phase1"}},
    )

    print("\n--- message trace ---")
    for m in result["messages"]:
        role = type(m).__name__
        tc = getattr(m, "tool_calls", None)
        if tc:
            for c in tc:
                print(f"[{role}] -> tool_call {c['name']}({c['args']})")
        content = (m.content or "").strip()
        if content:
            print(f"[{role}] {content[:600]}")

    final = result["messages"][-1].content.strip()
    assert final, "agent produced empty final answer"
    print("\n\033[32m✓ Phase 1 check passed — stripped foundation + Groq agent operational.\033[0m\n")


if __name__ == "__main__":
    main()
