"""RadQuant — a privacy-first, locally-deployable AI workstation for chest X-rays.

See PLAN.md for the full architecture. Public submodules:
  - radquant.state   : the CaseState TypedDict shared across LangGraph nodes
  - radquant.config  : credential/runtime resolution (GROQ_TOKEN, quant, etc.)
  - radquant.data    : sample image helpers
"""

__version__ = "0.1.0"
