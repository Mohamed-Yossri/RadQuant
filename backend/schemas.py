"""Pydantic schemas for all API request/response models."""
from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel


# ── Worklist ────────────────────────────────────────────────────────────────

class FindingItem(BaseModel):
    label: str
    probability: float
    tier: str


class CaseOut(BaseModel):
    case_id: str
    image_path: str
    urgency_score: float
    status: str                       # pending | in_review | finalized
    findings: Dict[str, float]
    top_findings: List[FindingItem]


class WorklistOut(BaseModel):
    cases: List[CaseOut]
    total: int
    pending: int


class StatusUpdate(BaseModel):
    status: str


# ── Draft / Report ───────────────────────────────────────────────────────────

class DraftOut(BaseModel):
    findings: str
    impression: str
    raw: str


class FinalizeIn(BaseModel):
    findings: str
    impression: str


class ReportOut(BaseModel):
    final_report: str
    case_id: str


# ── QC ───────────────────────────────────────────────────────────────────────

class QCIn(BaseModel):
    report: str


class OmissionItem(BaseModel):
    finding: str
    confidence: float
    suggestion: str
    method: str


class QCOut(BaseModel):
    omissions: List[OmissionItem]


# ── Explainer ────────────────────────────────────────────────────────────────

class ExplainIn(BaseModel):
    report: str


class GlossaryItem(BaseModel):
    term: str
    definition: str


class ExplainOut(BaseModel):
    plain: str
    glossary: List[GlossaryItem]
    highlighted_html: str


# ── Vision overlays ──────────────────────────────────────────────────────────

class GradCAMOut(BaseModel):
    overlay_url: str
    top_finding: str


class LocalizationFinding(BaseModel):
    label: str
    label_pretty: str
    box: List[float]                  # [y0, x0, y1, x1] normalised
    confidence: float
    zone: str


class LocalizeOut(BaseModel):
    overlay_url: str
    findings: List[LocalizationFinding]


class SegmentOut(BaseModel):
    overlay_url: str
    structures: List[str]
    cardiothoracic_ratio: Optional[float]
    ctr_flag: str


# ── Chat / Assistant ─────────────────────────────────────────────────────────

class ChatIn(BaseModel):
    question: str
    thread_id: Optional[str] = None


# ── Insights graph ───────────────────────────────────────────────────────────

class GraphNodeOut(BaseModel):
    id: str
    label: str
    kind: str                          # "case" | "hub"
    size: float
    tier: Optional[str] = None
    urgency_score: Optional[float] = None


class GraphEdgeOut(BaseModel):
    source: str
    target: str
    weight: float


class InsightsGraphOut(BaseModel):
    nodes: List[GraphNodeOut]
    edges: List[GraphEdgeOut]
    alerts: List[str]
    hub_sizes: Dict[str, int]


# ── General Medical mode ─────────────────────────────────────────────────────

class GeneralAnalyzeOut(BaseModel):
    image_id: str
    image_url: str
    modality: str
    region: str
    is_cxr: bool
    description: str
    pixel_spacing_mm: Optional[float] = None   # mm per pixel from DICOM, if available


class GeneralVQAIn(BaseModel):
    image_id: str
    question: str


class GeneralVQAOut(BaseModel):
    answer: str


class GeneralSegmentIn(BaseModel):
    image_id: str
    box: List[float]                   # [x0, y0, x1, y1] in image pixels


class GeneralSegmentOut(BaseModel):
    overlay_url: str
    area_px: int
    area_pct: float
    width_px: int
    height_px: int
    longest_diameter_px: float
    short_axis_px: float
    image_w: int
    image_h: int


# ── CT Reader (TotalSegmentator) ──────────────────────────────────────────────

class CtVolume(BaseModel):
    name: str
    ml: float
    flag: Optional[str] = None          # "low" | "normal" | "high" | None
    ref_low: Optional[float] = None
    ref_high: Optional[float] = None


class CtSlice(BaseModel):
    orig: str
    overlay: str


class CtAnalyzeOut(BaseModel):
    study_id: str
    n_slices: int
    slices: List[CtSlice]
    volumes: List[CtVolume]
    report: str
