"""Build a RadQuant foundation agent.

This is the reimplementation of MedRAX's `initialize_agent` (`medrax/main.py`):
same tool-registry + Agent pattern, but the GPT-4o backbone is replaced with a
Groq-hosted open-weights LLM (`openai/gpt-oss-120b`) via the OpenAI-compatible
API. See radquant/foundation/NOTICE.md.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver

from radquant import config
from .agent import Agent
from .tools import ChestXRayClassifierTool, DicomProcessorTool, ImageVisualizerTool

DEFAULT_SYSTEM_PROMPT = (
    "You are RadQuant, an assistive AI for chest X-ray interpretation. You have "
    "access to tools: a DICOM processor (converts DICOM to PNG and extracts "
    "metadata), a chest X-ray classifier (returns probabilities for 18 "
    "pathologies), and an image visualizer. When a user gives you an image path, "
    "use the appropriate tools, then summarize the findings in clear clinical "
    "language, citing the classifier probabilities you relied on. If a path is a "
    "DICOM file, convert it first. Always be explicit about uncertainty.\n\n"
    "This is a research / assistive demo and not a medical device. Never present "
    "output as a final clinical diagnosis."
)

def _medgemma_tool(device, temp_dir):
    from radquant.models import MedGemmaVQATool  # lazy: avoids loading transformers early
    return MedGemmaVQATool()


def _localize_tool(device, temp_dir):
    from radquant.models.cv_tools import LocalizeFindingsTool
    return LocalizeFindingsTool()


def _segment_tool(device, temp_dir):
    from radquant.models.cv_tools import SegmentAnatomyTool
    return SegmentAnatomyTool()


# name -> factory(device, temp_dir). Mirrors MedRAX's `all_tools` registry,
# trimmed to the tools RadQuant keeps + the MedGemma VLM and CV tools.
_TOOL_FACTORY = {
    "ChestXRayClassifierTool": lambda device, temp_dir: ChestXRayClassifierTool(device=device),
    "DicomProcessorTool": lambda device, temp_dir: DicomProcessorTool(temp_dir=temp_dir),
    "ImageVisualizerTool": lambda device, temp_dir: ImageVisualizerTool(),
    "MedGemmaVQATool": _medgemma_tool,
    "LocalizeFindingsTool": _localize_tool,
    "SegmentAnatomyTool": _segment_tool,
}

# Default tool set for the interactive agent (no MedGemma VLM; the nodes call it
# directly). The eval explicitly opts MedGemma in so the orchestrator can see.
_DEFAULT_TOOLS = ["ChestXRayClassifierTool", "DicomProcessorTool", "ImageVisualizerTool"]


def build_agent(
    tools_to_use: Optional[List[str]] = None,
    device: str = "cuda",
    temp_dir: str = "temp",
    backend: str = "groq",
    model: Optional[str] = None,
    temperature: float = 0.7,
    top_p: float = 0.95,
    max_tokens: int = 2048,
    system_prompt: Optional[str] = None,
    log_tools: bool = True,
    log_dir: str = "logs",
) -> Tuple[Agent, Dict[str, object]]:
    """Initialize the foundation agent against an OpenAI-compatible orchestrator.

    Args:
        tools_to_use: subset of _TOOL_FACTORY keys; defaults to the interactive set.
        backend: "groq" (gpt-oss-120b) or "nvidia" (NIM Llama-3.3-70B, Phase 8 eval).
        model: override the backend's default model id.
        max_tokens: gpt-oss-120b is a reasoning model — keep this generous or the
            visible answer comes back empty (budget spent on hidden reasoning).

    Returns:
        (agent, tools_dict) — mirrors MedRAX's return contract.
    """
    if backend == "nvidia":
        key, base_url, default_model = (config.nvidia_key(), config.NVIDIA_BASE_URL,
                                        config.NVIDIA_MODEL)
        if not key:
            raise RuntimeError("No NVIDIA key found. Set NVIDIA_KEY — see PLAN.md.")
    elif backend == "groq":
        key, base_url, default_model = (config.groq_key(), config.GROQ_BASE_URL,
                                        config.GROQ_MODEL)
        if not key:
            raise RuntimeError("No Groq key found. Set GROQ_TOKEN (or GROQ_API_KEY).")
    else:
        raise ValueError(f"unknown backend {backend!r} (use 'groq' or 'nvidia')")

    llm = ChatOpenAI(
        model=model or default_model,
        base_url=base_url,
        api_key=key,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        default_headers={"User-Agent": "radquant/0.1"},  # Cloudflare 1010 guard
    )

    names = tools_to_use or _DEFAULT_TOOLS
    tools = [_TOOL_FACTORY[n](device, temp_dir) for n in names if n in _TOOL_FACTORY]

    agent = Agent(
        llm,
        tools=tools,
        checkpointer=MemorySaver(),
        system_prompt=system_prompt or DEFAULT_SYSTEM_PROMPT,
        log_tools=log_tools,
        log_dir=log_dir,
    )
    return agent, {t.name: t for t in tools}
