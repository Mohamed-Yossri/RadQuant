# Phase 10 — Longitudinal Comparison (Interval Analysis)

## Goal
When a prior study exists for the same patient, compare it against the current
study and surface interval changes directly in the radiologist's workflow.

## Pipeline change
```
Before:  classify → triage → visualize → draft → review → qc
After:   classify → compare → triage → visualize → draft → review → qc
```
`comparison_node` is a **no-op** when `state["prior_image_path"]` is None.
The original single-study pipeline is fully backward-compatible.

## New files
| File | Role |
|---|---|
| `radquant/nodes/compare.py` | LangGraph node — multi-image MedGemma call |
| `radquant/prompts/comparison.py` | Prompt templates |
| `radquant/ui/comparison_panel.py` | Streamlit sidebar + main panel |
| `tests/test_compare.py` | Unit tests (no GPU needed) |
| `scripts/phase10_check.py` | Phase verification script |

## Modified files
| File | Change |
|---|---|
| `radquant/state.py` | +7 optional longitudinal fields |
| `radquant/graph.py` | `compare` node inserted between classify and triage |
| `radquant/nodes/draft.py` | Comparison-aware prompt addendum |
| `radquant/worklist.py` | `link_prior`, `unlink_prior`, `get_same_patient_cases`, `has_prior` |
| `radquant/ui/case_view.py` | Sidebar prior linking + main comparison panel |

## Technical decisions
- **Multi-image path**: MedGemma receives `[prior_image, current_image]` — same
  path validated in eval/direct.py. No extra VRAM needed.
- **Structured JSON output**: prompt requests JSON; `_parse_json_response()`
  strips fences and handles truncation (pattern from eval/direct.py).
- **Draft integration**: `DRAFT_COMPARISON_ADDENDUM` appended to existing prompt
  when `comparison_impression` is set. Report opens with:
  `"Compared to prior study dated YYYY-MM-DD, …"`
- **max_new_tokens=512**: same as draft.py. ≤33 s on L4.

## Done when
- (a) Prior linked → `interval_findings` populated with change categories ✓
- (b) No prior → state passes through unchanged ✓
- (c) Draft opens with "Compared to prior study dated …" paragraph ✓
- (d) UI sidebar shows same-patient priors in selectbox ✓
- (e) `link_prior` / `unlink_prior` persist across Streamlit reruns ✓
- (f) `compute_interval` correct across all time ranges ✓
- (g) JSON parsing robust to fenced output and truncation ✓
- (h) MedGemma failure → graceful degradation ✓

## Limitations
- Patient matching relies on DICOM PatientID. Anonymous PNG uploads need manual linking.
- Urgency triage does not yet boost score for newly detected critical findings.
- Prior classifier findings missing for cases added before Phase 10 (visual comparison still works).
