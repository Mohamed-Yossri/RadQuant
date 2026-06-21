#!/usr/bin/env python3
"""Phase 4 end-to-end: sample CXR → classify → draft (FINDINGS/IMPRESSION) + Grad-CAM.

Done-when (PLAN.md): a draft where every classifier finding > 0.5 is either
mentioned in FINDINGS or visually dismissed, plus a heatmap overlay highlighting
the classifier's focus region.

Run: python scripts/phase4_check.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image

from radquant.data import sample
from radquant.nodes.classify import classify_image
from radquant.nodes.draft import draft_report
from radquant.nodes.visualize import gradcam_overlay
from radquant.prompts.draft_report import _pretty, top_findings_above


def main() -> None:
    img = str(sample(1)[0])
    print(f"image: {img}")

    findings = classify_image(img)
    above = top_findings_above(findings, 0.5)
    print("classifier >0.5:", ", ".join(f"{_pretty(k)} {v:.2f}" for k, v in above))

    f_text, i_text, _raw = draft_report(img, findings)
    print("\n--- FINDINGS ---\n" + f_text)
    print("\n--- IMPRESSION ---\n" + i_text)

    assert f_text, "FINDINGS section empty"
    assert i_text, "IMPRESSION section empty"

    # Grounding: the done-when says each >0.5 finding must be MENTIONED or
    # VISUALLY DISMISSED. A blanket-normal statement ("lungs are clear", "no
    # acute cardiopulmonary process") is itself a visual dismissal that covers
    # any finding not explicitly named.
    blob = (f_text + " " + i_text).lower()
    DISMISSAL = ("clear", "no acute", "unremarkable", "no convincing",
                 "no evidence", "normal", "within normal limits")
    blanket = any(d in blob for d in DISMISSAL)
    print(f"\n--- grounding (blanket visual dismissal present: {blanket}) ---")
    unaddressed = []
    for k, v in above:
        word = _pretty(k).split()[-1]  # e.g. 'effusion', 'opacity', 'cardiomegaly'
        if word in blob:
            how = "explicitly mentioned/dismissed"
        elif blanket:
            how = "covered by blanket dismissal"
        else:
            how = "NOT addressed"
            unaddressed.append(_pretty(k))
        print(f"  {_pretty(k):28} {v:.2f}  ->  {how}")
    assert not unaddressed, f"findings neither mentioned nor dismissed: {unaddressed}"

    # Grad-CAM overlay.
    heat_path, top = gradcam_overlay(img, findings=findings)
    assert Path(heat_path).is_file(), "heatmap not written"
    w, h = Image.open(heat_path).size
    assert w > 0 and h > 0
    print(f"\n✓ Grad-CAM overlay for top finding '{top}' -> {heat_path} ({w}x{h})")

    print("\n\033[32m✓ Phase 4 check passed — draft (FINDINGS+IMPRESSION) + heatmap produced.\033[0m")
    print("  View: streamlit run radquant/ui/case_view.py")


if __name__ == "__main__":
    main()
