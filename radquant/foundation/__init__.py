"""radquant.foundation — the stripped MedRAX scaffold RadQuant builds on.

Keeps three tools (classifier, DICOM processor, image visualizer) and the
LangGraph Agent loop, rewired to a Groq-hosted open LLM. See NOTICE.md for
attribution and PLAN.md Phase 1.
"""

from .agent import Agent, AgentState
from .build import build_agent, DEFAULT_SYSTEM_PROMPT
from .tools import (
    ChestXRayClassifierTool,
    DicomProcessorTool,
    ImageVisualizerTool,
)

__all__ = [
    "Agent",
    "AgentState",
    "build_agent",
    "DEFAULT_SYSTEM_PROMPT",
    "ChestXRayClassifierTool",
    "DicomProcessorTool",
    "ImageVisualizerTool",
]
