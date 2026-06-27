"""Data preprocessing pipeline for RadQuant.

Scans the ChestAgentBench figures directory, validates every image,
extracts metadata (dimensions, size, color mode), optionally generates
224×224 thumbnails for fast classifier input, and writes a manifest JSON
for instant loading at runtime.

Usage (CLI):
    python -m radquant.data.preprocess          # full preprocessing
    python -m radquant.data.preprocess --dry-run # validate only, no writes

Usage (API):
    from radquant.data.preprocess import preprocess
    stats = preprocess(dry_run=False, thumbnails=True)
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from radquant.config import DATA_DIR

logger = logging.getLogger(__name__)

CHESTAGENTBENCH_DIR = DATA_DIR / "chestagentbench"
FIGURES_DIR = CHESTAGENTBENCH_DIR / "figures"
METADATA_JSONL = CHESTAGENTBENCH_DIR / "metadata.jsonl"
MANIFEST_PATH = CHESTAGENTBENCH_DIR / "manifest.json"
THUMBNAIL_DIR = CHESTAGENTBENCH_DIR / "thumbnails"
THUMBNAIL_SIZE = (224, 224)
_IMAGE_EXTS = {".png", ".jpg", ".jpeg"}


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class ImageRecord:
    """Metadata for a single image file."""
    path: str                     # absolute path to image
    relative_path: str            # relative to FIGURES_DIR
    figure_id: str                # parent directory name (e.g. "10009")
    filename: str                 # e.g. "fig1.png"
    width: int = 0
    height: int = 0
    channels: int = 0
    file_size_bytes: int = 0
    format: str = ""              # png / jpg / jpeg
    md5: str = ""                 # content hash for dedup
    thumbnail_path: str = ""      # path to 224×224 thumbnail
    valid: bool = True
    error: str = ""
    # metadata.jsonl cross-reference
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PreprocessStats:
    """Summary statistics from a preprocessing run."""
    total_figure_dirs: int = 0
    total_images: int = 0
    valid_images: int = 0
    invalid_images: int = 0
    thumbnails_generated: int = 0
    thumbnails_skipped: int = 0
    total_size_mb: float = 0.0
    avg_width: float = 0.0
    avg_height: float = 0.0
    format_counts: Dict[str, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0


# ── Metadata loading ────────────────────────────────────────────────────────

def _load_metadata_index() -> Dict[str, Dict]:
    """Load metadata.jsonl and index by figure_id for cross-referencing."""
    index: Dict[str, Dict] = {}
    if not METADATA_JSONL.exists():
        logger.warning("metadata.jsonl not found at %s — skipping cross-reference", METADATA_JSONL)
        return index

    with open(METADATA_JSONL, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                # The figure_id is typically in a field like "figure_id" or "id"
                fid = str(row.get("figure_id", row.get("id", "")))
                if fid:
                    index[fid] = row
            except json.JSONDecodeError:
                logger.warning("metadata.jsonl line %d: invalid JSON", line_no)
    logger.info("Loaded %d metadata records from metadata.jsonl", len(index))
    return index


# ── Image validation ─────────────────────────────────────────────────────────

def _validate_image(path: Path) -> ImageRecord:
    """Validate a single image and extract its metadata."""
    rec = ImageRecord(
        path=str(path),
        relative_path=str(path.relative_to(FIGURES_DIR)),
        figure_id=path.parent.name,
        filename=path.name,
        format=path.suffix.lower().lstrip("."),
        file_size_bytes=path.stat().st_size if path.exists() else 0,
    )

    try:
        # Use PIL for validation — it's already a dependency via Pillow
        from PIL import Image
        with Image.open(path) as img:
            img.verify()  # verify it's a valid image

        # Re-open to get actual dimensions (verify() closes the fp)
        with Image.open(path) as img:
            rec.width, rec.height = img.size
            # Determine channels
            mode_channels = {"L": 1, "LA": 2, "RGB": 3, "RGBA": 4, "P": 1}
            rec.channels = mode_channels.get(img.mode, 3)
            rec.valid = True

    except Exception as e:
        rec.valid = False
        rec.error = str(e)
        return rec

    # Compute MD5 hash for deduplication
    try:
        h = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        rec.md5 = h.hexdigest()
    except Exception:
        pass  # non-critical

    return rec


def _generate_thumbnail(rec: ImageRecord, force: bool = False) -> bool:
    """Generate a 224×224 thumbnail for classifier pre-feeding."""
    if not rec.valid:
        return False

    thumb_dir = THUMBNAIL_DIR / rec.figure_id
    thumb_path = thumb_dir / rec.filename
    rec.thumbnail_path = str(thumb_path)

    if thumb_path.exists() and not force:
        return False  # already exists

    try:
        from PIL import Image
        thumb_dir.mkdir(parents=True, exist_ok=True)
        with Image.open(rec.path) as img:
            # Convert to grayscale for CXR classifier compatibility
            if img.mode != "L":
                img = img.convert("L")
            # Resize with high-quality resampling
            img = img.resize(THUMBNAIL_SIZE, Image.LANCZOS)
            img.save(str(thumb_path), quality=95)
        return True
    except Exception as e:
        logger.warning("Thumbnail failed for %s: %s", rec.path, e)
        return False


# ── Main preprocessing pipeline ─────────────────────────────────────────────

def preprocess(
    dry_run: bool = False,
    thumbnails: bool = True,
    force_thumbnails: bool = False,
    verbose: bool = True,
) -> PreprocessStats:
    """Run the full preprocessing pipeline.

    Args:
        dry_run: If True, only validate — don't write manifest or thumbnails.
        thumbnails: If True, generate 224×224 thumbnails.
        force_thumbnails: If True, regenerate all thumbnails even if they exist.
        verbose: If True, print progress to stdout.

    Returns:
        PreprocessStats with summary of the run.
    """
    t0 = time.time()
    stats = PreprocessStats()

    # Validate source directory
    if not FIGURES_DIR.exists():
        msg = f"Figures directory not found: {FIGURES_DIR}"
        logger.error(msg)
        stats.errors.append(msg)
        if verbose:
            print(f"[ERROR] {msg}")
        return stats

    # Discover all figure directories
    figure_dirs = sorted(
        d for d in FIGURES_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")
    )
    stats.total_figure_dirs = len(figure_dirs)

    if verbose:
        print(f"[DIR] Found {stats.total_figure_dirs} figure directories")
        print(f"[META] Loading metadata.jsonl...")

    # Load metadata for cross-referencing
    meta_index = _load_metadata_index()

    # Scan all images
    records: List[ImageRecord] = []
    total_size = 0
    widths: List[int] = []
    heights: List[int] = []

    if verbose:
        print(f"[SCAN] Scanning and validating images...")

    for i, fig_dir in enumerate(figure_dirs):
        images = sorted(
            p for p in fig_dir.iterdir()
            if p.is_file() and p.suffix.lower() in _IMAGE_EXTS
        )

        for img_path in images:
            rec = _validate_image(img_path)

            # Cross-reference with metadata.jsonl
            if rec.figure_id in meta_index:
                rec.metadata = meta_index[rec.figure_id]

            if rec.valid:
                stats.valid_images += 1
                total_size += rec.file_size_bytes
                widths.append(rec.width)
                heights.append(rec.height)

                # Format counts
                fmt = rec.format
                stats.format_counts[fmt] = stats.format_counts.get(fmt, 0) + 1

                # Generate thumbnail
                if thumbnails and not dry_run:
                    created = _generate_thumbnail(rec, force=force_thumbnails)
                    if created:
                        stats.thumbnails_generated += 1
                    else:
                        stats.thumbnails_skipped += 1
            else:
                stats.invalid_images += 1
                stats.errors.append(f"{rec.relative_path}: {rec.error}")

            records.append(rec)

        # Progress reporting
        if verbose and (i + 1) % 100 == 0:
            print(f"  ... processed {i + 1}/{stats.total_figure_dirs} directories")

    stats.total_images = len(records)
    stats.total_size_mb = round(total_size / (1024 * 1024), 2)
    stats.avg_width = round(sum(widths) / max(len(widths), 1), 1)
    stats.avg_height = round(sum(heights) / max(len(heights), 1), 1)

    # Write manifest
    if not dry_run:
        manifest = {
            "version": "1.0",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "stats": asdict(stats),
            "images": [asdict(r) for r in records if r.valid],
            "invalid": [asdict(r) for r in records if not r.valid],
        }
        # Remove stats.errors from manifest stats to avoid duplication
        MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, default=str))
        if verbose:
            print(f"[OK] Manifest written to {MANIFEST_PATH}")

    stats.elapsed_seconds = round(time.time() - t0, 2)

    if verbose:
        print()
        print("=" * 60)
        print("  RadQuant Data Preprocessing Summary")
        print("=" * 60)
        print(f"  Figure directories : {stats.total_figure_dirs}")
        print(f"  Total images       : {stats.total_images}")
        print(f"  Valid images       : {stats.valid_images}")
        print(f"  Invalid images     : {stats.invalid_images}")
        print(f"  Total size         : {stats.total_size_mb} MB")
        print(f"  Avg dimensions     : {stats.avg_width} x {stats.avg_height}")
        print(f"  Format breakdown   : {stats.format_counts}")
        if thumbnails and not dry_run:
            print(f"  Thumbnails created : {stats.thumbnails_generated}")
            print(f"  Thumbnails skipped : {stats.thumbnails_skipped} (already exist)")
        print(f"  Elapsed            : {stats.elapsed_seconds}s")
        if stats.errors:
            print(f"\n  [WARN] {len(stats.errors)} error(s):")
            for e in stats.errors[:10]:
                print(f"    - {e}")
            if len(stats.errors) > 10:
                print(f"    ... and {len(stats.errors) - 10} more")
        print("=" * 60)

    return stats


# ── Manifest access ──────────────────────────────────────────────────────────

def load_manifest() -> Optional[Dict]:
    """Load the preprocessed manifest, or None if it doesn't exist."""
    if not MANIFEST_PATH.exists():
        return None
    return json.loads(MANIFEST_PATH.read_text())


def manifest_image_paths() -> List[Path]:
    """Return all valid image paths from the manifest (fast, no rglob)."""
    manifest = load_manifest()
    if not manifest:
        return []
    return [Path(img["path"]) for img in manifest.get("images", [])]


# ── CLI entry point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RadQuant data preprocessing")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate only, don't write manifest or thumbnails")
    parser.add_argument("--no-thumbnails", action="store_true",
                        help="Skip thumbnail generation")
    parser.add_argument("--force", action="store_true",
                        help="Regenerate all thumbnails even if they exist")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress progress output")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    result = preprocess(
        dry_run=args.dry_run,
        thumbnails=not args.no_thumbnails,
        force_thumbnails=args.force,
        verbose=not args.quiet,
    )
    sys.exit(0 if result.invalid_images == 0 else 1)
