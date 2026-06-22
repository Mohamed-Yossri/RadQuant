"""Interactive 'ask RadQuant about this case' assistant.

A tool-using agent: the orchestrator LLM (NVIDIA NIM / Groq — which does real
function calling) reasons over a radiologist's questions and calls RadQuant's
tools to *see* the image:

  - medgemma            : look at the X-ray and answer a visual question
  - chest_xray_classifier : 18-pathology probabilities
  - localize_findings   : bounding-box localization (auditor)
  - segment_anatomy     : lung/heart segmentation + cardiothoracic ratio

The orchestrator is text-only, so it cannot see the image directly — it must use
these tools. The case image path is pinned into the system prompt.
"""

from __future__ import annotations

from typing import List, Tuple

from radquant.foundation import build_agent

ASSISTANT_TOOLS = ["MedGemmaVQATool", "ChestXRayClassifierTool",
                   "LocalizeFindingsTool", "SegmentAnatomyTool"]


def _system_prompt(image_path: str) -> str:
    return (
        "You are RadQuant, an assistive AI helping a radiologist review a single "
        f"chest X-ray located at this exact path: {image_path}\n\n"
        "You CANNOT see the image yourself. To answer any visual question you MUST "
        "call a tool, always passing image_path='" + image_path + "':\n"
        "- medgemma: open-ended visual questions / descriptions of the X-ray.\n"
        "- chest_xray_classifier: probabilities for 18 pathologies.\n"
        "- localize_findings: WHERE a finding is (bounding-box zones).\n"
        "- segment_anatomy: lung/heart anatomy + approximate cardiothoracic ratio.\n\n"
        "Prefer localize_findings for 'where' questions and segment_anatomy for "
        "size/anatomy questions. After gathering tool evidence, answer concisely and "
        "cite what the tools found. This is a research/assistive demo, not a "
        "diagnosis; recommend radiologist confirmation for anything actionable."
    )


def build_assistant(image_path: str, backend: str = "nvidia"):
    """Build a per-case tool-using assistant agent (+ its tools dict)."""
    return build_agent(
        tools_to_use=ASSISTANT_TOOLS,
        backend=backend,
        system_prompt=_system_prompt(image_path),
        temperature=0.3,
        max_tokens=1024,
        log_tools=False,
    )


def ask(agent, question: str, thread_id: str) -> Tuple[str, List[str]]:
    """Ask the assistant a question; returns (answer, tools_used)."""
    from langchain_core.messages import HumanMessage

    result = agent.workflow.invoke(
        {"messages": [HumanMessage(content=question)]},
        config={"configurable": {"thread_id": thread_id}, "recursion_limit": 12},
    )
    tools_used: List[str] = []
    for m in result["messages"]:
        for tc in getattr(m, "tool_calls", None) or []:
            tools_used.append(tc["name"])
    answer = result["messages"][-1].content or ""
    return answer.strip(), tools_used
