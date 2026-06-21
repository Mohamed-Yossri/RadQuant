"""Explainer page — any report → plain-language patient draft (modality-agnostic).

Run standalone:  streamlit run radquant/ui/explainer.py
"""

from __future__ import annotations

import streamlit as st

from radquant.nodes.explain import explain_report, build_glossary, highlight_html
from radquant.ui import theme

EXAMPLE = (
    "EXAMINATION: CT abdomen/pelvis with contrast.\n"
    "FINDINGS: A 3.5 cm hypodense lesion in the right hepatic lobe, indeterminate. "
    "Mild splenomegaly. No retroperitoneal lymphadenopathy. Cholelithiasis without "
    "cholecystitis.\nIMPRESSION: Indeterminate hepatic lesion; recommend MRI for "
    "further characterization."
)


def page() -> None:
    theme.app_header("EXPLAINER")
    theme.disclaimer("Draft for radiologist approval before sharing with a patient. "
                     "Works on any modality (CT, MRI, ultrasound, X-ray).")

    report = st.text_area("Paste a radiology report (any modality)", value=EXAMPLE,
                          height=200)
    if not st.button("Explain", type="primary"):
        return

    with st.spinner("Translating and building glossary..."):
        plain = explain_report(report)
        glossary = build_glossary(report)

    left, right = st.columns(2)
    with left:
        st.markdown("**Original** · hover the underlined terms")
        st.markdown(f'<div class="rq-card">{highlight_html(report, glossary)}</div>',
                    unsafe_allow_html=True)
    with right:
        st.markdown("**Plain-language draft**")
        st.markdown(f'<div class="rq-card">{plain}</div>', unsafe_allow_html=True)

    if glossary:
        with st.expander(f"Glossary · {len(glossary)} terms"):
            for term, definition in glossary.items():
                st.markdown(f"- **{term}** — {definition}")


def render() -> None:  # standalone entry
    st.set_page_config(page_title="RadQuant — Explainer", page_icon="🫁", layout="wide")
    theme.inject_css()
    page()


if __name__ == "__main__":
    render()
