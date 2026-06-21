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

# name -> factory(device, temp_dir). Mirrors MedRAX's `all_tools` registry,
# trimmed to the three tools RadQuant keeps.
_TOOL_FACTORY = {
    "ChestXRayClassifierTool": lambda device, temp_dir: ChestXRayClassifierTool(device=device),
    "DicomProcessorTool": lambda device, temp_dir: DicomProcessorTool(temp_dir=temp_dir),
    "ImageVisualizerTool": lambda device, temp_dir: ImageVisualizerTool(),
}


def build_agent(
    tools_to_use: Optional[List[str]] = None,
    device: str = "cuda",
    temp_dir: str = "temp",
    model: Optional[str] = None,
    temperature: float = 0.7,
    top_p: float = 0.95,
    max_tokens: int = 2048,
    system_prompt: Optional[str] = None,
    log_dir: str = "logs",
) -> Tuple[Agent, Dict[str, object]]:
    """Initialize the foundation agent against the Groq orchestrator.

    Args:
        tools_to_use: subset of _TOOL_FACTORY keys; defaults to all three.
        device: torch device for the classifier ("cuda" or "cpu").
        temp_dir: scratch dir for DICOM->PNG conversions.
        model: Groq model id; defaults to config.GROQ_MODEL (gpt-oss-120b).
        max_tokens: gpt-oss-120b is a reasoning model — keep this generous or the
            visible answer comes back empty (budget spent on hidden reasoning).

    Returns:
        (agent, tools_dict) — mirrors MedRAX's return contract.
    """
    key = config.groq_key()
    if not key:
        raise RuntimeError(
            "No Groq key found. Set GROQ_TOKEN (or GROQ_API_KEY) — see PLAN.md."
        )

    llm = ChatOpenAI(
        model=model or config.GROQ_MODEL,
        base_url=config.GROQ_BASE_URL,
        api_key=key,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        default_headers={"User-Agent": "radquant/0.1"},  # Cloudflare 1010 guard
    )

    names = tools_to_use or list(_TOOL_FACTORY)
    tools = [_TOOL_FACTORY[n](device, temp_dir) for n in names if n in _TOOL_FACTORY]

    agent = Agent(
        llm,
        tools=tools,
        checkpointer=MemorySaver(),
        system_prompt=system_prompt or DEFAULT_SYSTEM_PROMPT,
        log_tools=True,
        log_dir=log_dir,
    )
    return agent, {t.name: t for t in tools}
