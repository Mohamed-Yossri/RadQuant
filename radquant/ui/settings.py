"""Settings page — runtime info, model ids, and the node/graph map.

Read-only in v1: surfaces what the system is actually running.
"""

from __future__ import annotations

import streamlit as st

from radquant import config
from radquant.ui import theme


def page() -> None:
    theme.app_header("SETTINGS")

    st.subheader("Runtime")
    c1, c2, c3 = st.columns(3)
    c1.metric("Quantization", config.quant())
    try:
        import torch
        dev = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"
        vram = (f"{torch.cuda.get_device_properties(0).total_memory/1e9:.0f} GB"
                if torch.cuda.is_available() else "—")
    except Exception:  # noqa: BLE001
        dev, vram = "unknown", "—"
    c2.metric("Device", dev)
    c3.metric("VRAM", vram)

    st.subheader("Models & endpoints")
    st.markdown(f"""
    | Role | Model |
    |---|---|
    | Medical VLM (draft, QC judge, explainer) | `{config.MEDGEMMA_REPO}` |
    | Classifier (18 pathologies) | TorchXRayVision `{config.XRV_WEIGHTS}` |
    | Orchestrator | Groq `{config.GROQ_MODEL}` |
    | Orchestrator fallback | Groq `{config.GROQ_MODEL_FALLBACK}` |
    """)

    creds = []
    creds.append(("HF_TOKEN", "✅ set" if config.hf_token() else "❌ missing"))
    creds.append(("GROQ token", "✅ set" if config.groq_key() else "❌ missing"))
    st.subheader("Credentials")
    for name, status in creds:
        st.write(f"- **{name}**: {status}")

    st.subheader("Pipeline (LangGraph)")
    st.code("ingest → classify → triage → visualize → draft → review\n"
            "review → qc → END        (finalize)\n"
            "review → draft           (regenerate)\n"
            "explain                  (side-call from any report)", language="text")

    theme.disclaimer("Research / assistive demo — not a medical device. "
                     "No node finalizes a report without radiologist review.")


def render() -> None:  # standalone entry
    st.set_page_config(page_title="RadQuant — Settings", page_icon="🫁", layout="wide")
    theme.inject_css()
    page()


if __name__ == "__main__":
    render()
