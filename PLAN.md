# RadQuant — Build Plan

## Project overview

An open-source, locally-deployable AI assistant for radiologists, built as a modernized, workflow-focused extension of **MedRAX** (ICML 2025). The system assists with chest X-ray (CXR) interpretation across four core workflows:

1. **Case triage** — urgency-based worklist reordering driven by classifier output
2. **Draft report generation** — MedGemma drafts Findings/Impression grounded in classifier findings
3. **Omission QC** — a safety net that flags high-confidence classifier findings absent from the draft report
4. **Patient-friendly explainer** — modality-agnostic plain-language translation of any radiology report (works on CT, MRI, US, etc. via text alone)

The system runs on a single GPU (T4 16 GB or L4 24 GB), uses fully open-weights models for the medical reasoning path, and relies on a free-tier Groq-hosted LLM only for agent orchestration.

## User actions required

The only manual steps required from the human. **Everything else is automated by `scripts/setup.py`** (see Phase 0).

1. **One-time HuggingFace license acceptance for MedGemma.** Visit https://huggingface.co/google/medgemma-1.5-4b-it while logged in and click "Acknowledge license." Approval is automatic and takes ~30 seconds.
2. **Provide two credentials in `.env`.** Generate an HF token at https://huggingface.co/settings/tokens (read scope) and a Groq API key at https://console.groq.com. Place both in a `.env` file at repo root using the `.env.example` template that the setup script generates.
3. **Choose GPU class on Lightning.ai.** Pick T4 or L4 when creating the studio. The setup script will detect which is available and configure quantization accordingly.

Everything else — dataset downloads, model weight caching, environment validation, sample image selection — is handled automatically. The human is not asked to choose datasets, pick sample images, or run download commands.

## Core thesis

MedRAX demonstrated that LangGraph-based tool orchestration with a GPT-4o backbone outperforms standalone CXR models on complex queries. This project advances that result in three directions:

1. **Stack modernization** — replace MedRAX's multi-model VLM stack (LLaVA-Med + CheXagent + Maira-2 + SwinV2 + GPT-4o backbone) with **MedGemma 1.5 4B + Groq-hosted open LLM orchestrator**, enabling fully local inference on consumer-grade GPUs and removing proprietary API dependencies from the medical path.
2. **Workflow specialization** — extend MedRAX's single-image research interface into a teleradiology-style worklist UX with triage, draft editing, and human-in-the-loop QC.
3. **Reproducible evaluation** — benchmark against ChestAgentBench (the benchmark released with the MedRAX paper) using the same evaluation harness, enabling direct comparison with the published baseline.

## Architecture

The system is a **LangGraph state machine**. Nodes operate on a shared `CaseState` dict:

```python
class CaseState(TypedDict):
    case_id: str
    image_path: str           # DICOM or PNG
    image_array: np.ndarray   # Preprocessed image tensor
    dicom_metadata: dict
    findings: dict            # {pathology_name: probability}
    urgency_score: float
    heatmap_path: str
    draft_findings: str
    draft_impression: str
    omissions: list[dict]     # [{finding, confidence, suggestion}]
    radiologist_edits: dict
    final_report: str
    explainer_output: str
```

**Nodes:**

| Node | Role | Tech |
|------|------|------|
| `ingest` | Load DICOM/PNG, extract metadata, apply windowing | pydicom, Pillow |
| `classify` | 18 pathology probabilities | TorchXRayVision DenseNet-121 |
| `triage` | Weighted urgency score | Python only |
| `visualize` | Grad-CAM heatmap overlay | pytorch-grad-cam |
| `draft` | Generate Findings + Impression | MedGemma 1.5 4B |
| `qc` | Detect classifier findings missing from draft | MedGemma 1.5 4B (LLM-as-judge) |
| `review` | Radiologist edits via UI; optional regenerate loop | Streamlit |
| `explain` | Plain-language translation of report | MedGemma 1.5 4B (text-only path) |

**Orchestration:** Conditional edges and meta-reasoning ("which node should run next given user action X?") handled by Groq-hosted `openai/gpt-oss-120b` via OpenAI-compatible API. MedRAX already supports this swap via `OPENAI_BASE_URL`.

## Foundation: MedRAX

This project **builds on MedRAX** (Apache 2.0, https://github.com/bowang-lab/MedRAX). What we keep from MedRAX vs. what we replace:

**Keep:**
- LangGraph orchestration scaffold (`medrax/` package structure)
- DICOM processing utilities (`DicomProcessorTool`)
- TorchXRayVision classifier wrapper (`ChestXRayClassifierTool`)
- Image visualization helpers (`ImageVisualizerTool`)
- Tool-agnostic agent initialization pattern (`initialize_agent` in `main.py`)
- Gradio bones as a reference (we replace with Streamlit, but the patterns transfer)

**Replace / Remove:**
- GPT-4o backbone → Groq `openai/gpt-oss-120b` via OpenAI-compatible endpoint
- LLaVA-Med, CheXagent, Maira-2, SwinV2, RoentGen → MedGemma 1.5 4B (one model handles VQA, report generation, explanation, and grounding via prompting)
- MedSAM/PSPNet segmentation → skip for v1
- Gradio UI → Streamlit (better for worklist/multi-pane layouts)

**Add (net-new contribution):**
- Urgency-scoring + worklist data model
- Omission QC node and prompt
- Radiologist-edit feedback loop
- Patient-friendly explainer mode
- ChestAgentBench evaluation report against the published MedRAX/GPT-4o baseline

## Tech stack

| Layer | Choice |
|------|--------|
| Compute | Lightning.ai studio, single T4 16 GB or L4 24 GB |
| Python | 3.10+ |
| Orchestration | LangChain + LangGraph |
| Medical VLM | `google/medgemma-1.5-4b-it` via `transformers`, 4-bit quantization on T4 / bf16 on L4 |
| CXR classifier | `torchxrayvision` (DenseNet-121, pretrained, ~18 pathologies) |
| Heatmap | `pytorch-grad-cam` |
| DICOM | `pydicom`, `SimpleITK` |
| UI | `streamlit` |
| Orchestrator LLM | Groq `openai/gpt-oss-120b` via OpenAI-compatible API |
| Eval harness | MedRAX `quickstart.py` adapted for new stack |

## Data sources (all auto-fetched by `scripts/setup.py`)

The setup script handles all data acquisition. The choice of dataset for any given task should optimize for: (1) public + no manual gating, (2) bandwidth-efficient, (3) reusable across phases when possible.

| Use | Source | Auto-fetch method | Notes |
|---|---|---|---|
| Primary dev + Phase 8 eval | wanglab/chest-agent-bench (ChestAgentBench) | `huggingface-cli download wanglab/chestagentbench --repo-type dataset --include "figures.zip" --local-dir data/chestagentbench` then unzip in-script | Public with HF token, no manual approval. Reused for both dev images and Phase 8 evaluation. |
| Image-report pairs for explainer testing | OpenI / Indiana CXR Collection | HuggingFace `datasets` library, streaming mode | Public, no auth needed. Pull only as many image-report pairs as needed (default 50). |
| DICOM ingestion testing | pydicom built-in samples | `from pydicom.data import get_testdata_files` | Built into pydicom, no download. |
| Additional DICOM if needed | TCIA sample (5–10 files only) | `tcia-utils` Python package, or skip if pydicom samples suffice | Only fetch if pydicom samples are insufficient for the ingestion test cases. |

**Forbidden datasets (do not auto-fetch):** MIMIC-CXR (4.7TB + PhysioNet credentialing), CheXpert (440GB + registration), full NIH ChestX-ray14 (45GB). If a use case seems to require one of these, document why and ask first.

**Auto-selection rule for sample images:** When a phase needs N sample images for testing, the setup script provides a helper `radquant.data.sample(n, pathology=None, modality="cxr")` that returns N images from the ChestAgentBench figures (default), filtered by pathology if specified. Test code should call this helper rather than hardcoding file paths.

## Constraints (hard rules)

- **Bandwidth-efficient first.** Never pull full MIMIC-CXR (4.7TB, requires PhysioNet credentialing), full CheXpert (440GB), or full NIH ChestX-ray14 (45GB). Use the **ChestAgentBench figures bundle** as the primary data source — needed for Phase 8 evaluation anyway, doubles as development data. Fallbacks if more variety is needed: **OpenI / Indiana CXR Collection** (~7,470 image-report pairs, no registration). For DICOM-format ingestion testing: pydicom built-in sample data (`from pydicom.data import get_testdata_files`) plus 5–10 files from TCIA. Never download a full TCIA collection.
- **VRAM-aware.** Before loading any model, check available VRAM. Use 4-bit (bitsandbytes) on T4. Prefer bf16 on L4 (4-bit can actually be slower on T4 due to dequantization overhead).
- **No proprietary medical APIs.** Everything in the medical reasoning path must be open-weights and self-hostable. Groq is OK for the orchestrator because it's a swappable role using open models (gpt-oss-120b is open weights — Groq is just hosting).
- **Radiologist-in-the-loop.** No node may finalize a report unilaterally. The `review` node is always the terminal step before output.
- **No clinical claims.** All UI surfaces must carry a "research/assistive demo, not for clinical use" disclaimer.

---

## Phase 0 — Environment and automated setup

**Goal:** A single command (`python scripts/setup.py`) brings a fresh Lightning.ai studio to a fully-ready state: dependencies installed, all model weights cached, all datasets downloaded, environment validated. The human's only inputs are `.env` (two API keys) and a one-time MedGemma license acceptance on HuggingFace.

**Tasks:**

1. **Repo scaffold.** Create the project structure:
   ```
   radquant/
     external/medrax/         # MedRAX vendored (git clone target)
     radquant/
       nodes/                 # LangGraph nodes (one file per node)
       prompts/               # MedGemma prompt templates
       models/                # Model loaders, wrappers
       data/                  # Data helpers, sample() function
       ui/                    # Streamlit pages
       eval/                  # ChestAgentBench harness
       state.py               # CaseState TypedDict
       graph.py               # LangGraph wiring
     scripts/
       setup.py               # ALL automated setup (see below)
       smoke_test.py          # End-to-end validation
     data/                    # Downloaded datasets, .gitignored
     tests/
     PLAN.md
     CLAUDE.md
     .env.example
     .env                     # gitignored, user-provided
     pyproject.toml
   ```

2. **Write `scripts/setup.py`** as an idempotent script (safe to re-run; skips work already done). It must:

   a. **Validate `.env`** exists with `HF_TOKEN` and `GROQ_API_KEY`. If missing, generate `.env.example` and exit with a clear error pointing the user at the "User actions required" section of PLAN.md.

   b. **Detect GPU class.** Read `nvidia-smi` output. If VRAM ≤ 16 GB → set `RADQUANT_QUANT=4bit`. If 16–32 GB → `RADQUANT_QUANT=bf16`. Write to `.env.runtime`.

   c. **Install dependencies** via `pip install -e .` from a `pyproject.toml` with pinned versions (see Tech stack table). Required: `transformers`, `torch`, `accelerate`, `bitsandbytes`, `langgraph`, `langchain`, `langchain-openai`, `torchxrayvision`, `pytorch-grad-cam`, `pydicom`, `SimpleITK`, `Pillow`, `numpy`, `pandas`, `streamlit`, `python-dotenv`, `huggingface-hub`.

   d. **HuggingFace login.** Use `HfApi().set_access_token(HF_TOKEN)` or `huggingface-cli login --token $HF_TOKEN`.

   e. **Cache MedGemma weights.** Run `AutoModelForImageTextToText.from_pretrained("google/medgemma-1.5-4b-it")` to trigger download. If a 403 returns, print a clear message asking the user to accept the license at the HF URL, then exit non-zero. Otherwise confirm weights are cached and log size + load time.

   f. **Cache TorchXRayVision weights.** Load `xrv.models.DenseNet(weights="densenet121-res224-all")` to trigger the auto-download. Confirm.

   g. **Clone MedRAX.** `git clone https://github.com/bowang-lab/MedRAX.git external/medrax/` if not already present.

   h. **Download ChestAgentBench.** `huggingface-cli download wanglab/chestagentbench --repo-type dataset --include "figures.zip" --local-dir data/chestagentbench` and unzip. Skip if already present and unzipped.

   i. **Pull OpenI sample.** Use HuggingFace `datasets` library to stream and persist 50 image-report pairs from OpenI to `data/openi_sample/`. Skip if already present.

   j. **Validate Groq endpoint.** Make one test call to `openai/gpt-oss-120b` via the OpenAI-compatible API. Confirm response.

   k. **Print a summary.** GPU class detected, quantization chosen, MedGemma load time, VRAM at idle, data paths, Groq latency. End with "✓ Setup complete."

3. **Write `scripts/smoke_test.py`** that exercises the full stack: load a sample image via `radquant.data.sample(1)`, run it through classifier → MedGemma multimodal → MedGemma text-only → Groq orchestrator. Each step prints OK or fails fast.

**Done when:** A fresh Lightning.ai studio can run `git clone ... && cd radquant && python scripts/setup.py && python scripts/smoke_test.py` and both succeed end-to-end. The human's only manual involvement was filling out `.env` and clicking accept on the MedGemma HF page.

---

## Phase 1 — Strip MedRAX to its essentials

**Goal:** A minimal MedRAX-derived scaffold with only the tools we keep, importable as `radquant.foundation`.

**Tasks:**
1. From MedRAX, identify and extract the modules for: `DicomProcessorTool`, `ChestXRayClassifierTool` (TorchXRayVision wrapper), `ImageVisualizerTool`, and the `initialize_agent` pattern.
2. Comment out / delete all references to: `LlavaMedTool`, `XRayVQATool` (CheXagent), `XRayPhraseGroundingTool` (Maira-2), `ChestXRayReportGeneratorTool` (SwinV2), `ChestXRayGeneratorTool` (RoentGen), `ChestXRaySegmentationTool`.
3. Reimplement `initialize_agent` to use the Groq LLM via `ChatOpenAI(base_url=..., model="openai/gpt-oss-120b")`.
4. Verify the stripped scaffold runs: classifier returns probabilities on a sample image, DICOM processor reads a sample DICOM, visualizer outputs an overlay.

**Done when:** A test script can pass a sample CXR into the stripped MedRAX agent and get back classifier probabilities, with the agent's reasoning trace shown.

---

## Phase 2 — MedGemma integration

**Goal:** MedGemma 1.5 4B is loaded as a singleton, exposed via a clean Python API for image+text and text-only inference, and wrapped as a LangGraph-callable tool.

**Tasks:**
1. Implement `radquant/models/medgemma.py`:
   - Singleton loader with VRAM-aware quantization (auto-detect T4 → 4-bit, L4 → bf16).
   - `generate(image: PIL.Image | None, prompt: str, max_new_tokens: int = 512) -> str` interface.
   - Supports both multimodal (image + text) and text-only paths.
2. Write a small benchmark script that times 5 inferences and reports tokens/sec and peak VRAM. Sanity-check against published numbers.
3. Wrap as a LangChain `Tool` so the orchestrator can call it.
4. Test prompts:
   - Image + "Describe what you see in this chest X-ray." → coherent finding-style output
   - Text-only + "Translate this report to plain English: [paste]" → plain-language version

**Done when:** A unit test passes both multimodal and text-only inference, peak VRAM stays under the GPU limit, and tokens/sec is logged.

---

## Phase 3 — Triage and worklist

**Goal:** A classifier-driven urgency scoring system and an in-memory worklist data model.

**Tasks:**
1. Implement `radquant/nodes/classify.py`: runs TorchXRayVision on the image, returns `{pathology: probability}` for all 18 classes.
2. Implement `radquant/nodes/triage.py`:
   - Define pathology weights in a config file, anchored on the **ACR Actionable Reporting Work Group's three-tier critical findings framework** and the **Annarumma/Baltruschat published urgency ordering** for CXR worklist prioritization (European Radiology, simulation paper).
   - Tier mapping for the 18 TorchXRayVision classes:

     | Tier | Time sensitivity | Pathologies | Weight |
     |---|---|---|---|
     | Critical (T1) | Immediate communication | pneumothorax, pneumonia | 1.0 |
     | Urgent (T2) | Within hours | pleural effusion, consolidation, edema, lung lesion, mass | 0.6 |
     | Important (T3) | Same-day to days | cardiomegaly, nodule, infiltration, lung opacity, fracture, enlarged cardiomediastinum, pleural thickening | 0.4 |
     | Chronic / incidental | Follow-up | atelectasis, emphysema, fibrosis, hernia | 0.2 |

   - `urgency_score = sum(weight[p] * prob[p] for p in pathologies)`
   - **Caveat to document in code comments and demo:** weights are literature-anchored defaults, not site-validated. Real deployment would calibrate against local data and a radiologist's review. This is acknowledged limitation, not hidden.
   - References: ACR Actionable Reporting Work Group (https://www.acr.org/Clinical-Resources/Practice-Parameters-and-Technical-Standards); Annarumma et al., "Automated triaging of adult chest radiographs with deep artificial neural networks," Radiology 2019; Baltruschat et al., "Smart chest X-ray worklist prioritization using artificial intelligence: a clinical workflow simulation," European Radiology 2021.
3. Implement `radquant/worklist.py`: a simple in-memory store of cases keyed by `case_id`, sortable by `urgency_score`. Persist to a JSON file for session continuity.
4. Streamlit page `ui/worklist.py`: table view, sorted by urgency descending, columns for case_id, top findings, urgency score, status.

**Done when:** Calling `radquant.data.sample(20)` and pushing each through the classify → triage pipeline produces a sorted worklist where any case with pneumothorax probability > 0.5 surfaces in the top quartile.

---

## Phase 4 — Draft report generation

**Goal:** Given an image and classifier findings, MedGemma produces a structured Findings + Impression draft.

**Tasks:**
1. Design the prompt template in `radquant/prompts/draft_report.py`. The prompt must:
   - Take the image
   - Take a structured summary of the top classifier findings (e.g., "Classifier detected: right pleural effusion (0.82), cardiomegaly (0.65)")
   - Ask MedGemma to produce two sections: `FINDINGS:` (descriptive observations) and `IMPRESSION:` (interpretive summary)
   - Instruct: "If a classifier finding is not visually supported, you may dismiss it. Do not invent findings the classifier did not detect and you cannot see."
2. Implement `radquant/nodes/draft.py`: calls MedGemma with the prompt, parses the two sections out of the output, populates `state["draft_findings"]` and `state["draft_impression"]`.
3. Implement `radquant/nodes/visualize.py`: Grad-CAM on the classifier's top-1 finding, overlay heatmap on the original image, save to disk, store path in state.
4. Streamlit page `ui/case_view.py`: image with toggle for heatmap overlay, side-by-side editable text areas for Findings and Impression.

**Done when:** Loading a sample CXR produces a draft report where every classifier finding > 0.5 is either mentioned in the Findings section or visually dismissed, and the heatmap overlay highlights the region the classifier focused on.

---

## Phase 5 — Omission QC node

**Goal:** After the radiologist edits, a final pass that flags classifier findings with no corresponding mention in the report.

**Tasks:**
1. Implement `radquant/nodes/qc.py`:
   - Take `state["final_report"]` (radiologist-edited) and `state["findings"]`.
   - For each finding with probability > 0.7, ask MedGemma (text-only): "Does this report mention any of: [synonyms list for the pathology]? Reply YES or NO with one sentence of justification."
   - If NO, add to `state["omissions"]` with the finding name, confidence, and suggested phrasing.
2. Build a synonym map (e.g., "pleural effusion" → ["effusion", "fluid in the pleural space", "blunting of the costophrenic angle"]) in `radquant/prompts/synonyms.py`. This avoids false-positive omissions when the radiologist used a different phrasing.
3. Streamlit widget: shows a soft warning panel listing omissions, with "Dismiss" and "Add to report" buttons per omission.

**Done when:** Test cases pass:
- (a) Classifier flags pneumothorax 0.8, report doesn't mention it → omission flagged ✓
- (b) Classifier flags pneumothorax 0.8, report says "no pneumothorax" → no omission flagged (the report addresses it) ✓
- (c) Classifier flags effusion 0.8, report says "blunting of the right costophrenic angle" → no omission flagged (synonym recognized) ✓

---

## Phase 6 — Patient-friendly explainer

**Goal:** A modality-agnostic mode that takes any radiology report and produces a plain-language patient-facing version.

**Tasks:**
1. Implement `radquant/nodes/explain.py`: takes report text, calls MedGemma text-only with a prompt asking for plain-language translation while preserving clinical accuracy and severity.
2. Implement term-highlighting: a post-processing pass that identifies medical jargon in the original report and inserts hover-explanations from MedGemma in the patient version.
3. Streamlit page `ui/explainer.py`: paste-in or upload report text → side-by-side original + patient version with highlighted terms.
4. **Important constraint:** This mode is for *radiologist-approved* report translation, not direct-to-patient generation. The UI must make this clear (e.g., "Draft for radiologist approval before sharing").

**Done when:** Pasting a real radiology report (CT, MRI, or X-ray — modality-agnostic) produces a plain-language version where every jargon term is hover-explained and severity is preserved.

---

## Phase 7 — Graph wiring and UI integration

**Goal:** All nodes wired into the LangGraph state machine, accessible through a unified Streamlit interface.

**Tasks:**
1. Implement `radquant/graph.py`: defines the full graph with conditional edges:
   - `ingest → classify → triage → visualize → draft → review`
   - `review → qc → END` (default)
   - `review → draft` (if radiologist clicked "Regenerate")
   - `explain` available as a side-call from any state with a report
2. Streamlit multi-page app:
   - Worklist (default landing)
   - Case view (per-case workflow)
   - Explainer (standalone mode)
   - Settings (GPU mode, prompt versions)
3. Persistent state across Streamlit reruns via `st.session_state`.

**Done when:** A user can land on the worklist, click a high-urgency case, see the draft report and heatmap, edit it, get an omission warning, dismiss or address it, mark the case as finalized, and then switch modes to use the explainer on any report.

---

## Phase 8 — Evaluation against ChestAgentBench

This is a **core deliverable**, not optional. Without it the project is a demo; with it the project is a benchmark-reportable result.

**Goal:** Produce a results table comparing this system against the published MedRAX/GPT-4o baseline on ChestAgentBench's 2,500 queries across 7 categories.

**Tasks:**
1. Download ChestAgentBench: `huggingface-cli download wanglab/chestagentbench --repo-type dataset --local-dir data/chestagentbench`. Unzip `figures.zip`.
2. Adapt MedRAX's `quickstart.py` to call our agent instead of GPT-4o. The adaptation should be minimal — the eval interface is `agent(query, image) → answer`.
3. Run the full benchmark. With 30 RPM on Groq, 2,500 queries will take ~85 minutes at full throttle; budget accordingly and respect daily limits (gpt-oss-120b: 1K RPD — may need to split across 3 days, or switch to llama-3.3-70b-versatile for higher RPD).
4. Compute scores per category: Detection, Classification, Localization, Comparison, Relationship, Diagnosis, Characterization.
5. Generate `eval/results.md` with:
   - Our scores per category
   - Published MedRAX/GPT-4o baseline scores (from the arXiv paper, https://arxiv.org/abs/2502.02673)
   - Delta and interpretation
   - Hardware/cost comparison (our T4/L4 + free Groq vs. their GPT-4o API costs)
6. **Honest reporting.** If we underperform on a category, say so and explain why. Trading some accuracy for fully-local open-weights deployment is itself a legitimate result.

**Done when:** `eval/results.md` exists with full per-category numbers and a clear comparison table.

---

## Phase 9 — Documentation and demo materials

**Goal:** A polished README, architecture diagram, demo video, and slide deck.

**Tasks:**
1. `README.md`: project summary, architecture diagram (the LangGraph node diagram), quickstart, citation to MedRAX, license, "research use only" disclaimer.
2. Record a 3–5 minute demo video walking through: worklist → high-urgency case → draft → heatmap → omission catch → finalize → explainer mode.
3. Slide deck materials: problem framing, architecture, technical contributions vs. MedRAX, benchmark results, future work.

**Done when:** README and demo materials exist; an outside engineer could clone the repo and run the system in under 30 minutes following the README.

---

## Future work (not in scope for v1)

These are documented as roadmap, not deliverables for this build:

- **CT support via MONAI.** Pick one specific 3D task — lung nodule detection (LIDC-IDRI pretrained bundle) or organ segmentation — and integrate as a second mode with a slice-scrolling viewer. Estimated 1–2 weeks of dedicated work because 3D volume handling, multi-plane reconstructions (axial/coronal/sagittal), windowing/leveling presets (lung/bone/soft-tissue), and slice aggregation logic are all non-trivial. Would justify the claim "we handle 2D radiography deeply and 3D extensibility is demonstrated."
- **MRI support.** Similar 3D challenges as CT, plus multi-sequence complexity (T1/T2/FLAIR each show different tissue). Best paired with MONAI MRI bundles.
- **Ultrasound, mammography, fluoroscopy, PET, nuclear.** Each is a specialized domain with limited open-weights model support. Likely require domain-specific models per modality; treat as separate sub-projects.
- **Multi-image studies.** Real CXR studies typically include PA and lateral views together. Extending the classifier and MedGemma to consume both views jointly is a research direction.
- **Real radiologist user study.** Recruit 1–3 radiologists, have them use the tool on 30+ anonymized public cases, collect agreement/edit/dismissal rates. Even N=1 with qualitative feedback materially strengthens the project.
- **Pathology-weight calibration.** The urgency weights in Phase 3 are placeholders. A proper version would calibrate weights against actual clinical urgency data (e.g., ESI triage levels mapped to imaging findings).
- **Multi-language support.** Arabic explainer mode for MEA-region deployment. Groq hosts `canopylabs/orpheus-arabic-saudi` which could front the explainer node in Arabic.
- **Audio dictation.** Whisper-large-v3 (also on Groq) could replace text editing with voice editing of the draft report — closer to existing radiology dictation workflows.
- **PACS integration.** A real deployment path requires DICOM C-STORE / DICOMweb integration so the tool can pull from and push back to a hospital PACS, rather than file uploads.

## References

- **MedRAX paper:** Fallahpour et al., "MedRAX: Medical Reasoning Agent for Chest X-ray," ICML 2025. arXiv:2502.02673
- **MedRAX repo:** https://github.com/bowang-lab/MedRAX (Apache 2.0)
- **MedGemma 1.5 4B:** https://huggingface.co/google/medgemma-1.5-4b-it
- **MedGemma 1.5 technical blog:** https://research.google/blog/next-generation-medical-image-interpretation-with-medgemma-15-and-medical-speech-to-text-with-medasr/
- **TorchXRayVision:** Cohen et al., MIDL 2022. https://github.com/mlmed/torchxrayvision
- **ChestAgentBench:** https://huggingface.co/datasets/wanglab/chest-agent-bench
- **LangGraph docs:** https://langchain-ai.github.io/langgraph/
- **pytorch-grad-cam:** https://github.com/jacobgil/pytorch-grad-cam

## Attribution

This project builds directly on MedRAX (Fallahpour et al., ICML 2025) and must cite it prominently. The orchestration scaffold, several tool wrappers, and the evaluation methodology are derived from their work. Our contributions are documented in the "Core thesis" section.
