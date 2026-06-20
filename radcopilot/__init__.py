"""Medical Radiology Copilot — a workflow-focused extension of MedRAX.

See PLAN.md for the full architecture. Public submodules:
  - radcopilot.state   : the CaseState TypedDict shared across LangGraph nodes
  - radcopilot.config  : credential/runtime resolution (GROQ_TOKEN, quant, etc.)
  - radcopilot.data    : sample image helpers
"""

__version__ = "0.1.0"
