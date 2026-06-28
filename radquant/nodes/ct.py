"""CT reading pipeline — TotalSegmentator organ segmentation + volumes + slices.

TotalSegmentator (nnU-Net, Apache-2.0) segments 100+ anatomical structures in a
CT volume and reports each one's volume. We run it as an **isolated subprocess**
(`TotalSegmentator` CLI) so nnU-Net's multiprocessing never touches the API
process, then render per-slice overlay images in-process and hand a
representative slice + the volume table to MedGemma for a structured report.

CT-only. Input is a NIfTI volume (``.nii.gz``). The brain (MedGemma) is shared
with the rest of the app; only this anatomical specialist is CT-specific.
"""
from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

CT_DIR = Path("temp") / "ct"

# Approximate adult reference volume ranges (ml). Deliberately rough — surfaced
# in the UI as "approx. adult reference", not a calibrated normal range. Used to
# flag gross enlargement/atrophy (e.g. hepatomegaly, splenomegaly) which is the
# decision-relevant signal a volume measurement can add.
_REF_VOL = {
    "liver": (1200, 1900),
    "spleen": (100, 300),
    "kidney_left": (110, 210),
    "kidney_right": (110, 210),
    "pancreas": (50, 120),
    "gallbladder": (15, 70),
    "thyroid_gland": (8, 25),
    "brain": (1100, 1500),
    "urinary_bladder": (50, 500),
}


def _flag_volume(name: str, ml: float):
    rng = _REF_VOL.get(name)
    if not rng:
        return None, None, None
    lo, hi = rng
    flag = "low" if ml < lo else "high" if ml > hi else "normal"
    return flag, float(lo), float(hi)


def _window(img: np.ndarray, level: float = 40, width: float = 400) -> np.ndarray:
    lo, hi = level - width / 2, level + width / 2
    return np.clip((img - lo) / (hi - lo), 0, 1)


def run_totalseg(input_path: str, out_dir: Path, fast: bool = True) -> Path:
    """Run TotalSegmentator as a subprocess; return the multilabel seg path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    seg_file = out_dir / "seg.nii.gz"
    cmd = ["TotalSegmentator", "-i", str(input_path), "-o", str(seg_file),
           "--ml", "--statistics", "-d", "gpu", "-q"]
    if fast:
        cmd.append("--fast")
    subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=900)
    return seg_file


def analyze_ct(input_path: str, study_id: Optional[str] = None,
               fast: bool = True) -> Dict:
    """Segment a CT, render slices, and compute organ volumes.

    Returns ``{study_id, n_slices, slices:[{orig,overlay}], volumes:[{name,ml}],
    middle_overlay_path}``. Slice PNGs are study-prefixed and written under
    ``temp/ct/`` (served by the image route).
    """
    import nibabel as nib
    import matplotlib

    study_id = study_id or f"ct-{uuid.uuid4().hex[:8]}"
    work = CT_DIR / study_id
    seg_file = run_totalseg(input_path, work, fast=fast)

    # volumes (mm^3 -> ml)
    stats_path = next((p for p in (work / "statistics.json", seg_file.parent / "statistics.json")
                       if p.exists()), None)
    stats = json.loads(stats_path.read_text()) if stats_path else {}
    volumes = []
    for k, v in stats.items():
        if not (isinstance(v, dict) and v.get("volume", 0) > 0):
            continue
        ml = round(v["volume"] / 1000, 1)
        flag, lo, hi = _flag_volume(k, ml)
        volumes.append({"name": k, "ml": ml, "flag": flag, "ref_low": lo, "ref_high": hi})
    volumes.sort(key=lambda d: -d["ml"])

    # render slices (original grayscale + colored overlay), study-prefixed
    ct = nib.load(input_path).get_fdata()
    seg = nib.load(seg_file).get_fdata().astype(int)
    Z = ct.shape[2]
    cmap = matplotlib.colormaps["tab20"]
    slices: List[Dict[str, str]] = []
    from PIL import Image
    middle_overlay = None
    for z in range(Z):
        g = (_window(ct[:, :, z]) * 255).astype(np.uint8)
        Image.fromarray(np.rot90(np.stack([g, g, g], -1))).save(work / f"orig_{z}.png")
        rgb = np.stack([g, g, g], -1)
        sm = seg[:, :, z]
        for lbl in np.unique(sm):
            if lbl == 0:
                continue
            col = (np.array(cmap(int(lbl) % 20)[:3]) * 255).astype(np.uint8)
            m = sm == lbl
            rgb[m] = (0.45 * col + 0.55 * rgb[m]).astype(np.uint8)
        ov = work / f"over_{z}.png"
        Image.fromarray(np.rot90(rgb)).save(ov)
        if z == Z // 2:
            middle_overlay = str(ov)
        slices.append({
            "orig": f"/api/ct/slice/{study_id}/orig_{z}.png",
            "overlay": f"/api/ct/slice/{study_id}/over_{z}.png",
        })

    return {
        "study_id": study_id,
        "n_slices": Z,
        "slices": slices,
        "volumes": volumes,
        "middle_overlay_path": middle_overlay,
    }


def draft_ct_report(middle_overlay_path: str, volumes: List[Dict]) -> str:
    """MedGemma structured CT read, grounded in the measured organ volumes."""
    from radquant.models.medgemma import generate

    txt = ", ".join(f"{v['name'].replace('_', ' ')} {v['ml']:.0f} ml" for v in volumes[:10])
    abn = [
        f"{v['name'].replace('_', ' ')} {v['ml']:.0f} ml ({v['flag']} vs ref "
        f"{v['ref_low']:.0f}-{v['ref_high']:.0f} ml)"
        for v in volumes if v.get("flag") in ("high", "low")
    ]
    abn_txt = ("\nStructures outside the approximate adult reference range: "
               + "; ".join(abn) + ".") if abn else ""
    prompt = (
        "This is an axial CT slice with automatic organ segmentation overlaid. "
        f"Automatically measured organ volumes (TotalSegmentator): {txt}.{abn_txt}\n"
        "Provide a brief structured CT read. Comment on any structure flagged "
        "outside its reference range.\nFINDINGS: ...\nIMPRESSION: ...\n"
        "Describe only what is supported; do not invent. Begin with 'FINDINGS:'."
    )
    return generate(middle_overlay_path, prompt, max_new_tokens=300).strip()
