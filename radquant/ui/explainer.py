"""radquant/ui/explainer.py — Patient explainer Streamlit page."""

import streamlit as st
from radquant.ui.theme import inject_css, DISCLAIMER
from radquant.nodes.explain import explain_node, highlight_html


def render() -> None:
    inject_css()
    st.title("🗣️ Patient Explainer")
    st.markdown(DISCLAIMER, unsafe_allow_html=True)
    st.caption("Paste any radiology report (CT, MRI, US, X-ray) to get a plain-language version.")
    st.warning("⚠️ Draft for radiologist approval before sharing with the patient.")

    report_input = st.text_area("Paste radiology report here:", height=200,
                                placeholder="FINDINGS:\n...\nIMPRESSION:\n...")

    if st.button("🗣️ Generate plain-language version") and report_input.strip():
        with st.spinner("Translating …"):
            state = {"final_report": report_input.strip()}
            result = explain_node(state)

        raw_output = result.get("explainer_output", "")
        glossary = result.get("explainer_glossary", {})

        if not raw_output:
            st.error("Translation failed. Check that MedGemma is loaded.")
            return

        # Split at GLOSSARY:
        plain_part = raw_output.split("GLOSSARY:")[0].strip()
        html_output = highlight_html(plain_part, glossary)

        col_orig, col_plain = st.columns(2)
        with col_orig:
            st.subheader("Original Report")
            st.text(report_input)
        with col_plain:
            st.subheader("Plain Language")
            st.markdown(html_output, unsafe_allow_html=True)

        if glossary:
            st.subheader("📖 Glossary")
            for term, definition in glossary.items():
                st.markdown(f"**{term}**: {definition}")
