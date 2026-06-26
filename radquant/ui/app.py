"""RadQuant — unified multi-page Streamlit app (Phase 7).

Run:  streamlit run radquant/ui/app.py
"""

from __future__ import annotations

import streamlit as st

from radquant.ui import theme, worklist, case_view, explainer, settings, insights_graph


def main() -> None:
    st.set_page_config(page_title="RadQuant", page_icon="🫁", layout="wide",
                       initial_sidebar_state="expanded")
    theme.inject_css()

    pages = {
        "worklist": st.Page(worklist.page, title="Worklist", icon=":material/list_alt:",
                            url_path="worklist", default=True),
        "case": st.Page(case_view.page, title="Case", icon=":material/clinical_notes:",
                        url_path="case"),
        "insights": st.Page(insights_graph.page, title="Insights Graph",
                            icon=":material/hub:", url_path="insights"),
        "explainer": st.Page(explainer.page, title="Explainer", icon=":material/translate:",
                             url_path="explainer"),
        "settings": st.Page(settings.page, title="Settings", icon=":material/settings:",
                            url_path="settings"),
    }
    # Stash page objects so the worklist's "Open" button can switch programmatically.
    st.session_state["_pages"] = pages

    nav = st.navigation(list(pages.values()))

    with st.sidebar:
        st.markdown(
            """<div style="padding:6px 8px 14px;">
                 <div style="font-family:'Space Grotesk',sans-serif;font-size:1.45rem;
                      font-weight:700;letter-spacing:-.02em;line-height:1;">
                   🫁 Rad<span style="background:linear-gradient(135deg,#2DD4BF,#38BDF8);
                      -webkit-background-clip:text;background-clip:text;color:transparent;">Quant</span>
                 </div>
                 <div style="color:#8A99AD;font-size:.72rem;margin-top:4px;">
                   Local · open-weights · private</div>
               </div>""",
            unsafe_allow_html=True,
        )
        st.markdown(
            """<div style="position:fixed;bottom:14px;left:14px;color:#5d6b80;
                 font-size:.68rem;line-height:1.4;">
                 MedGemma 1.5 4B · TorchXRayVision<br>Research demo — not for clinical use
               </div>""",
            unsafe_allow_html=True,
        )

    nav.run()


if __name__ == "__main__":
    main()
