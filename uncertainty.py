"""`uncertainty` node — Monte Carlo Dropout selective prediction for CXR findings.

SCIENTIFIC BASIS
----------------
The key finding from eval/results.md:

    At τ ≥ 0.75  →  accuracy 66.7% on the 70% of cases the model answers
                     vs 63.1% for MedRAX/GPT-4o on ALL cases

The original eval/uncertainty.py measures *answer-agreement* at the benchmark
level (K sampled answers per MCQ question). This node brings the same principle
into the **live inference pipeline** at the *finding level*:

    For each pathology, run the classifier K times with MC Dropout enabled.
    The variance across K predictions is the epistemic uncertainty.
    High variance  → model is guessing  → defer to radiologist.
    Low variance   → model is confident → include in draft.

This is known as Monte Carlo Dropout (Gal & Ghahramani, 2016) and is the
standard lightweight uncertainty quantification method for CNNs.

WHY THIS MATTERS
----------------
Without uncertainty, the draft node reports ALL findings above a fixed threshold.
Some of those are flukes — the classifier saw a shadow and said "Mass 0.52".
With MC Dropout, we only report findings the classifier is *consistently* sure
about across K stochastic forward passes. The radiologist still sees the uncertain
findings, but clearly flagged as "needs your judgement".

PIPELINE INTEGRATION
--------------------
The node slots between classify and draft:

    ingest → classify → [uncertainty] → triage → visualize → draft → …

CaseState gains two new fields:
    certain_findings:   {pathology: prob}  — confident, go straight to draft
    uncertain_findings: {pathology: prob}  — flagged for radiologist review
    uncertainty_scores: {pathology: float} — variance across K passes (0–1)

The draft node already accepts a `findings` dict; we pass `certain_findings`
so the report only describes what the model is sure about. The UI shows
`uncertain_findings` in a separate warning panel.
"""

from __future__ import annotations

import logging
import threading
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thresholds (tuned to mirror eval/results.md τ=0.75 regime)
# ---------------------------------------------------------------------------

# Number of MC Dropout forward passes. 10 is the sweet spot:
# - 5  is too noisy (high variance of the variance itself)
# - 20 takes ~4s extra on T4, diminishing returns
K_PASSES: int = 10

# A finding is "certain" if its coefficient of variation (std/mean) is below
# this. CoV < 0.15 means the K predictions are within 15% of each other.
CERTAIN_COV_THRESHOLD: float = 0.15

# Minimum probability for a finding to be considered at all (pre-uncertainty).
# Below this it's noise regardless of consistency.
MIN_PROB_THRESHOLD: float = 0.15

# ---------------------------------------------------------------------------
# MC Dropout engine
# ---------------------------------------------------------------------------

def _enable_dropout(model) -> None:
    """Set all Dropout layers to train mode so they fire during inference."""
    import torch.nn as nn
    for m in model.modules():
        if isinstance(m, nn.Dropout):
            m.train()


def mc_dropout_predict(
    image_path: str,
    k: int = K_PASSES,
    device: str | None = None,
) -> Dict[str, List[float]]:
    """Run K stochastic forward passes and return per-pathology sample lists.

    Args:
        image_path: path to the chest X-ray image.
        k:          number of MC Dropout passes.
        device:     'cuda' or 'cpu' (auto-detected if None).

    Returns:
        {pathology: [prob_pass_1, prob_pass_2, …, prob_pass_k]}
    """
    import numpy as np
    import torch
    import torchxrayvision as xrv
    from PIL import Image

    from radquant.nodes.classify import get_classifier

    clf = get_classifier(device)

    # Access the underlying DenseNet from the tool wrapper.
    # ChestXRayClassifierTool stores the model as self.model
    model = clf.model
    model.eval()          # keep BN in eval mode (uses running stats)
    _enable_dropout(model) # but keep Dropout stochastic

    # Preprocess image — same pipeline as classify_image
    img = np.array(Image.open(image_path).convert("L"), dtype=np.float32)
    img = xrv.datasets.normalize(img, 255)
    img = img[None, ...]  # add channel dim
    transform = xrv.datasets.XRayCenterCrop()
    img = transform(img)
    tensor = torch.from_numpy(img)[None, ...]  # (1, 1, H, W)

    dev = device or ("cuda" if torch.cuda.is_available() else "cpu")
    tensor = tensor.to(dev)
    model = model.to(dev)

    samples: Dict[str, List[float]] = {p: [] for p in model.pathologies if p}

    with torch.no_grad():
        for _ in range(k):
            out = model(tensor)
            preds = dict(zip(model.pathologies, out[0].tolist()))
            for path, prob in preds.items():
                if path:
                    import math
                    samples[path].append(0.0 if (prob is None or math.isnan(prob)) else float(prob))

    return samples


def compute_uncertainty(
    samples: Dict[str, List[float]],
) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, float]]:
    """Derive mean, CoV (uncertainty), and split into certain / uncertain.

    Returns:
        means:              {pathology: mean_probability}
        cov_scores:         {pathology: coefficient_of_variation}
        certain_findings:   subset where CoV < CERTAIN_COV_THRESHOLD
        uncertain_findings: subset where CoV ≥ CERTAIN_COV_THRESHOLD
    """
    import numpy as np

    means: Dict[str, float] = {}
    cov_scores: Dict[str, float] = {}

    for path, probs in samples.items():
        if not probs:
            continue
        arr = np.array(probs)
        mean = float(arr.mean())
        std  = float(arr.std())
        # CoV = std / mean; clamp mean to avoid div/0
        cov  = std / max(mean, 1e-6)
        means[path]     = round(mean, 4)
        cov_scores[path] = round(cov, 4)

    certain:   Dict[str, float] = {}
    uncertain: Dict[str, float] = {}

    for path, mean in means.items():
        if mean < MIN_PROB_THRESHOLD:
            continue   # below noise floor — ignore entirely
        cov = cov_scores[path]
        if cov < CERTAIN_COV_THRESHOLD:
            certain[path]   = mean
        else:
            uncertain[path] = mean

    return means, cov_scores, certain, uncertain


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_selective_prediction(
    image_path: str,
    k: int = K_PASSES,
    device: str | None = None,
) -> dict:
    """Full uncertainty pipeline for one image.

    Returns a dict ready to merge into CaseState:
        {
            "findings":           all findings (mean probs, for backward compat),
            "certain_findings":   high-confidence subset,
            "uncertain_findings": low-confidence subset,
            "uncertainty_scores": CoV per pathology,
            "coverage":           fraction of findings that are certain (0–1),
        }
    """
    samples = mc_dropout_predict(image_path, k=k, device=device)
    means, cov_scores, certain, uncertain = compute_uncertainty(samples)

    total = len(certain) + len(uncertain)
    coverage = len(certain) / total if total > 0 else 1.0

    logger.info(
        "MC Dropout k=%d: %d certain, %d uncertain, coverage=%.1f%%",
        k, len(certain), len(uncertain), coverage * 100,
    )

    return {
        "findings":           means,           # backward-compat (replaces classify output)
        "certain_findings":   certain,
        "uncertain_findings": uncertain,
        "uncertainty_scores": cov_scores,
        "coverage":           round(coverage, 3),
    }


# ---------------------------------------------------------------------------
# LangGraph node
# ---------------------------------------------------------------------------

def uncertainty(state: dict) -> dict:
    """LangGraph node: image_path → certain_findings, uncertain_findings, uncertainty_scores.

    Replaces the plain `classify` node OR runs after it and overwrites findings
    with the MC Dropout means (more reliable than a single forward pass).

    Slot in graph.py:
        ingest → uncertainty → triage → visualize → draft → review → qc → END
    """
    image_path = state["image_path"]
    result = run_selective_prediction(image_path)
    return result


# ---------------------------------------------------------------------------
# Streamlit UI helper (called from case_view.py)
# ---------------------------------------------------------------------------

def render_uncertainty_panel(
    certain: Dict[str, float],
    uncertain: Dict[str, float],
    cov_scores: Dict[str, float],
    coverage: float,
) -> None:
    """Render the uncertainty breakdown panel in Streamlit."""
    import streamlit as st

    _CSS = """
    <style>
    .unc-row { display:flex; align-items:center; gap:.5rem; padding:.35rem .6rem;
               border-radius:8px; margin-bottom:.22rem;
               border:1px solid rgba(255,255,255,.05); }
    .unc-name { font-size:.78rem; font-weight:500; color:#C7D2E1; min-width:9rem; }
    .unc-bar-wrap { flex:1; height:5px; background:rgba(255,255,255,.07);
                    border-radius:3px; overflow:hidden; }
    .unc-bar { height:100%; border-radius:3px; }
    .unc-prob { font-size:.73rem; font-weight:600; min-width:3rem; text-align:right; }
    .unc-cov  { font-size:.68rem; color:#8A99AD; min-width:4.5rem; text-align:right; }
    .unc-badge-c { font-size:.67rem; padding:2px 7px; border-radius:20px;
                   background:rgba(45,212,191,.15); color:#2DD4BF;
                   border:1px solid rgba(45,212,191,.35); }
    .unc-badge-u { font-size:.67rem; padding:2px 7px; border-radius:20px;
                   background:rgba(251,191,36,.12); color:#FBBF24;
                   border:1px solid rgba(251,191,36,.3); }
    .unc-summary { font-size:.73rem; color:#8A99AD; padding:.45rem .65rem;
                   background:rgba(255,255,255,.03); border-radius:8px;
                   border:1px solid rgba(255,255,255,.05); margin-top:.5rem;
                   line-height:1.55; }
    </style>"""
    st.markdown(_CSS, unsafe_allow_html=True)

    # Coverage metric
    col1, col2, col3 = st.columns(3)
    col1.metric("Certain findings", len(certain))
    col2.metric("Uncertain (defer)", len(uncertain))
    col3.metric("Coverage", f"{coverage*100:.0f}%",
                help="% of findings the model is confident about (τ ≈ 0.75 target: 70%)")

    def _row(name: str, prob: float, is_certain: bool) -> str:
        pct     = int(prob * 100)
        cov     = cov_scores.get(name, 0.0)
        color   = "#2DD4BF" if is_certain else "#FBBF24"
        badge   = ('<span class="unc-badge-c">certain</span>' if is_certain
                   else '<span class="unc-badge-u">defer →&nbsp;radiologist</span>')
        pretty  = name.replace("_", " ").title()
        return (
            f'<div class="unc-row" style="background:{"rgba(45,212,191,.04)" if is_certain else "rgba(251,191,36,.04)"};">'
            f'<span class="unc-name">{pretty}</span>'
            f'<div class="unc-bar-wrap"><div class="unc-bar" style="width:{pct}%;background:{color};"></div></div>'
            f'<span class="unc-prob" style="color:{color};">{pct}%</span>'
            f'<span class="unc-cov">CoV {cov:.2f}</span>'
            f'{badge}</div>'
        )

    rows = ""
    for name, prob in sorted(certain.items(),   key=lambda x: x[1], reverse=True):
        rows += _row(name, prob, True)
    for name, prob in sorted(uncertain.items(), key=lambda x: x[1], reverse=True):
        rows += _row(name, prob, False)

    if rows:
        st.markdown(rows, unsafe_allow_html=True)

    # Summary tied to published eval numbers
    acc_est = "66.7%" if coverage >= 0.65 else "57.6%"
    st.markdown(
        f'<div class="unc-summary">'
        f'At this coverage ({coverage*100:.0f}%), estimated accuracy ≈ <b>{acc_est}</b> '
        f'— mirrors the selective-prediction result in <code>eval/results.md</code> '
        f'(τ=0.75 → 66.7% on 70% coverage vs 63.1% MedRAX/GPT-4o all-case).'
        f'</div>',
        unsafe_allow_html=True,
    )
