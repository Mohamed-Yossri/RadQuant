"""RadQuant — unified multi-page Streamlit app (Phase 7).

Run:  streamlit run radquant/ui/app.py
"""

from __future__ import annotations

import streamlit as st

from radquant.ui import theme, worklist, case_view, explainer, settings


def main() -> None:
    st.set_page_config(page_title="RadQuant", page_icon="🫁", layout="wide",
                       initial_sidebar_state="expanded")
    theme.inject_css()

    pages = {
        "worklist": st.Page(worklist.page, title="Worklist", icon=":material/list_alt:",
                            url_path="worklist", default=True),
        "case": st.Page(case_view.page, title="Case", icon=":material/clinical_notes:",
                        url_path="case"),
        "explainer": st.Page(explainer.page, title="Explainer", icon=":material/translate:",
                             url_path="explainer"),
        "settings": st.Page(settings.page, title="Settings", icon=":material/settings:",
                            url_path="settings"),
    }
    # Stash page objects so the worklist's "Open" button can switch programmatically.
    st.session_state["_pages"] = pages

    st.navigation(list(pages.values())).run()


if __name__ == "__main__":
    main()
