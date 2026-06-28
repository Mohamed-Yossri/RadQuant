"""CT reading pipeline — TotalSegmentator organ segmentation + volumes + slices.

TotalSegmentator (nnU-Net, Apache-2.0) segments 100+ anatomical structures in a
CT volume and reports each one's volume. We run it as an **isolated subprocess**
(`TotalSegmentator` CLI) so nnU-Net's multiprocessing never touches the API
process, then render per-slice overlay images in-process and hand a
representative slice + the volume table to MedGemma for a structured report.

CT-only. Input is a CT volume given as either a NIfTI file (``.nii.gz``) or a
DICOM series — a folder, or a ``.zip`` of ``.dcm`` slices straight off a
scanner/PACS (e.g. ``ct-lung-screening-nlst-series.zip``). DICOM is converted to
NIfTI in-process first, then the pipeline is identical. The brain (MedGemma) is
shared with the rest of the app; only this anatomical specialist is CT-specific.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import uuid
import zipfile
from collections import defaultdict
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


def _hu(ds, arr: np.ndarray) -> np.ndarray:
    """Apply RescaleSlope/Intercept → Hounsfield Units."""
    slope = float(getattr(ds, "RescaleSlope", 1) or 1)
    inter = float(getattr(ds, "RescaleIntercept", 0) or 0)
    return arr.astype(np.float32) * slope + inter


def _multiframe_to_nifti(ds, out_path: Path) -> Path:
    """Enhanced (multi-frame) DICOM — the whole volume lives in one .dcm file.

    pixel_array is (frames, rows, cols). Per-frame geometry lives in the
    PerFrameFunctionalGroupsSequence; fall back to shared groups / top-level tags.
    """
    import nibabel as nib

    frames = ds.pixel_array  # (F, R, C)
    if frames.ndim != 3:
        raise ValueError("Multi-frame DICOM did not decode to a 3D array.")
    F = frames.shape[0]

    def _shared(seq_name, tag, default=None):
        sh = getattr(ds, "SharedFunctionalGroupsSequence", None)
        if sh:
            grp = getattr(sh[0], seq_name, None)
            if grp:
                return getattr(grp[0], tag, default)
        return default

    pix = _shared("PixelMeasuresSequence", "PixelSpacing", getattr(ds, "PixelSpacing", [1.0, 1.0]))
    drow, dcol = float(pix[0]), float(pix[1])
    iop = list(_shared("PlaneOrientationSequence", "ImageOrientationPatient",
                       getattr(ds, "ImageOrientationPatient", [1, 0, 0, 0, 1, 0])))
    iop = np.array(iop, float)
    col_dir, row_dir = iop[0:3], iop[3:6]
    normal = np.cross(col_dir, row_dir)

    # per-frame positions (sorted along the normal)
    pfg = getattr(ds, "PerFrameFunctionalGroupsSequence", None)
    positions = []
    for i in range(F):
        ipp = None
        if pfg and i < len(pfg):
            pp = getattr(pfg[i], "PlanePositionSequence", None)
            if pp:
                ipp = getattr(pp[0], "ImagePositionPatient", None)
        positions.append(np.array(ipp, float) if ipp is not None else np.array([0, 0, float(i)]))
    order = sorted(range(F), key=lambda i: float(np.dot(positions[i], normal)))
    frames = frames[order]
    positions = [positions[i] for i in order]

    if F > 1:
        span = np.dot(positions[-1] - positions[0], normal)
        slice_sp = abs(span) / (F - 1) or float(_shared("PixelMeasuresSequence", "SliceThickness",
                                                        getattr(ds, "SliceThickness", 1)) or 1)
    else:
        slice_sp = float(getattr(ds, "SliceThickness", 1) or 1)

    vol = np.moveaxis(_hu(ds, frames), 0, -1)  # (R, C, F)
    affine = np.eye(4)
    affine[:3, 0] = row_dir * drow
    affine[:3, 1] = col_dir * dcol
    affine[:3, 2] = normal * slice_sp
    affine[:3, 3] = positions[0]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    nib.save(nib.Nifti1Image(vol.astype(np.int16), affine), str(out_path))
    return out_path


def dicom_to_nifti(src: str, out_path: Path) -> Path:
    """Convert a DICOM CT to one NIfTI volume.

    Accepts a ``.zip`` of slices, a folder of slices, or a single multi-frame
    (enhanced) ``.dcm``. We build the volume ourselves (pydicom) rather than
    handing the input to TotalSegmentator, so the segmentation mask and our
    rendered slices share the exact same voxel grid. Handles what a naive loader
    gets wrong: **Hounsfield calibration** (RescaleSlope/Intercept), **slice
    ordering** by projecting ImagePositionPatient onto the slice normal (not
    filename), a **geometrically correct affine** so organ volumes in ml are
    right, **mixed series / localizers** (keeps the largest consistent series),
    and **per-slice read failures** (skipped, not fatal). If a zip holds several
    series, the largest wins.
    """
    import pydicom
    import nibabel as nib

    src_p = Path(src)
    root = src_p
    if src_p.suffix.lower() == ".zip":
        root = Path(tempfile.mkdtemp(prefix="ct_dcm_"))
        with zipfile.ZipFile(src_p) as zf:
            zf.extractall(root)

    # A single file: could be a multi-frame (enhanced) CT = a whole volume.
    if root.is_file():
        ds = pydicom.dcmread(str(root), force=True)
        nframes = int(getattr(ds, "NumberOfFrames", 1) or 1)
        if nframes > 1:
            return _multiframe_to_nifti(ds, out_path)
        raise ValueError(
            "That's a single DICOM slice (.dcm) — one slice is not a 3-D CT volume. "
            "Upload the whole series as a .zip of its .dcm files (or a multi-frame .dcm).")

    # A folder / extracted zip: collect image slices, grouped by series.
    candidates = []
    for p in root.rglob("*"):
        if not p.is_file() or p.name.upper() == "DICOMDIR":
            continue
        try:
            # fast header scan (no pixel decode); PixelData is intentionally not
            # loaded here, so we gate on geometry tags an image slice must have.
            ds = pydicom.dcmread(str(p), force=True, stop_before_pixels=True)
        except Exception:
            continue
        if int(getattr(ds, "Rows", 0)) < 1:        # not an image (DICOMDIR, report, junk)
            continue
        candidates.append((p, ds))

    if not candidates:
        raise ValueError(
            "No DICOM image slices found in the upload. "
            "Make sure the .zip contains the CT series' .dcm files.")

    # group by (series UID, image shape) so localizers/scouts don't pollute the stack
    groups: Dict[tuple, list] = defaultdict(list)
    for p, ds in candidates:
        key = (str(getattr(ds, "SeriesInstanceUID", "x")),
               int(getattr(ds, "Rows", 0)), int(getattr(ds, "Columns", 0)))
        groups[key].append((p, ds))
    series = max(groups.values(), key=len)
    if len(series) < 3:
        raise ValueError(
            f"Largest consistent DICOM series has only {len(series)} slice(s); a CT "
            "volume needs many. Upload the full axial series as a .zip.")

    # orientation — assume axial if the tag is absent (common in anonymised exports)
    iop_raw = getattr(series[0][1], "ImageOrientationPatient", None)
    iop = np.array(iop_raw if iop_raw is not None else [1, 0, 0, 0, 1, 0], dtype=float)
    col_dir, row_dir = iop[0:3], iop[3:6]            # X (cols), Y (rows)
    normal = np.cross(col_dir, row_dir)

    # Order slices. Prefer true geometry (ImagePositionPatient projected on the
    # normal); fall back to InstanceNumber / SliceLocation if positions were
    # stripped — so we still build a correctly-ordered stack.
    have_ipp = getattr(series[0][1], "ImagePositionPatient", None) is not None

    def _sort_key(pd):
        ds = pd[1]
        if getattr(ds, "ImagePositionPatient", None) is not None:
            return float(np.dot(np.array(ds.ImagePositionPatient, float), normal))
        if getattr(ds, "InstanceNumber", None) is not None:
            return float(ds.InstanceNumber)
        return float(getattr(ds, "SliceLocation", 0) or 0)

    series.sort(key=_sort_key)

    # read pixels now (full read), skipping any individually unreadable slice.
    # Capture the first decode error so a codec/encoding problem is reported, not hidden.
    slabs, kept, first_err = [], [], None
    for p, _ in series:
        try:
            ds = pydicom.dcmread(str(p), force=True)
            slabs.append(_hu(ds, ds.pixel_array))
            kept.append(ds)
        except Exception as e:  # noqa: BLE001
            if first_err is None:
                first_err = f"{type(e).__name__}: {e}"
            continue
    if len(kept) < 3:
        raise ValueError(
            "Could not decode the DICOM pixel data — only "
            f"{len(kept)} slice(s) read. First error was [{first_err}]. "
            "If these are compressed slices, a codec plugin may be missing.")

    # guard against slices that disagree on shape despite the same series UID
    shapes = {s.shape for s in slabs}
    if len(shapes) > 1:
        from collections import Counter
        dom = Counter(s.shape for s in slabs).most_common(1)[0][0]
        slabs, kept = zip(*[(s, k) for s, k in zip(slabs, kept) if s.shape == dom])
        slabs, kept = list(slabs), list(kept)

    vol = np.stack(slabs, axis=-1)                    # [rows, cols, slices]
    ds0 = kept[0]
    ps = getattr(ds0, "PixelSpacing", None) or [1.0, 1.0]
    drow, dcol = float(ps[0]), float(ps[1])

    # slice spacing: from real positions if present, else SpacingBetweenSlices /
    # SliceThickness. origin: first slice's position if present, else 0.
    if have_ipp and getattr(kept[-1], "ImagePositionPatient", None) is not None:
        ipp0 = np.array(ds0.ImagePositionPatient, float)
        span = np.dot(np.array(kept[-1].ImagePositionPatient, float) - ipp0, normal)
        slice_sp = abs(span) / (len(kept) - 1)
    else:
        ipp0 = np.array(getattr(ds0, "ImagePositionPatient", [0.0, 0.0, 0.0]), float)
        slice_sp = 0.0
    if not slice_sp:
        slice_sp = float(getattr(ds0, "SpacingBetweenSlices", 0) or
                         getattr(ds0, "SliceThickness", 0) or 1.0)

    affine = np.eye(4)
    affine[:3, 0] = row_dir * drow
    affine[:3, 1] = col_dir * dcol
    affine[:3, 2] = normal * slice_sp
    affine[:3, 3] = ipp0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    nib.save(nib.Nifti1Image(vol.astype(np.int16), affine), str(out_path))
    return out_path


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

    # DICOM (zip / folder / single multi-frame .dcm) → NIfTI first; .nii passes through.
    ip = Path(input_path)
    if ip.suffix.lower() in (".zip", ".dcm") or ip.is_dir():
        input_path = str(dicom_to_nifti(input_path, work / "volume.nii.gz"))

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
