# CLAUDE.md — working notes for this repo

Build plan lives in **PLAN.md**. This file records environment facts and the
deviations from PLAN.md that were verified live (the plan was AI-drafted; these
are the corrections).

## Environment (verified 2026-06-20)
- Host: Lightning.ai studio, **NVIDIA L4, 23 GB** → **bf16** path (not 4-bit).
- Python 3.12.11, conda env `cloudspace`.
- **torch 2.8.0+cu128 and torchvision 0.23.0+cu128 are pre-installed.** Do NOT
  add them to `pyproject.toml` — pip would resolve a CPU wheel and break CUDA.

## Credentials
- Provided as Lightning **secrets**, exported into the env: `HF_TOKEN`,
  **`GROQ_TOKEN`** (the plan called it `GROQ_API_KEY`; we accept either).
- Resolve them only via `radquant.config` (`hf_token()`, `groq_key()`).

## Verified external facts
- MedGemma: `google/medgemma-1.5-4b-it`, arch `Gemma3ForConditionalGeneration`,
  needs **transformers ≥ 4.57.1**. License already auto-granted for this token.
- ChestAgentBench dataset canonical id: **`wanglab/chest-agent-bench`**
  (the plan's `wanglab/chestagentbench` only 307-redirects). Files: `figures.zip`,
  `metadata.jsonl`.
- Groq serves `openai/gpt-oss-120b` (+ `llama-3.3-70b-versatile` fallback).
  **gpt-oss-120b is a reasoning model**: with small `max_tokens` it returns empty
  `content` (budget spent on hidden reasoning). Always give ≥256 tokens.

## Storage discipline (user pays for studio storage)
- `pip install --no-cache-dir`; MedRAX cloned `--depth 1` with `.git` removed;
  `figures.zip` deleted after extraction; OpenI sample is opt-in (`--with-openi`).
- Only large unavoidable artifact: MedGemma weights (~8 GB) in the HF cache.

## Phase status
- Phase 0: scaffold + `scripts/setup.py` + `scripts/smoke_test.py`. DONE.
- Phase 1: `radquant.foundation` — stripped MedRAX subset (classifier, DICOM,
  visualizer + LangGraph `Agent`) rewired to Groq `gpt-oss-120b`. Verified by
  `scripts/phase1_check.py` (agent chains tools + returns correct top-3). DONE.
  - Note: foundation is a *vendored derivative* of MedRAX (Apache-2.0) under
    `radquant/foundation/` with `NOTICE.md`, NOT an import of `external/medrax`
    (whose `tools/__init__.py` eagerly imports LLaVA/RoentGen/etc. and would fail).
- Phase 2: `radquant/models/medgemma.py` — VRAM-aware singleton (`get_medgemma`,
  `generate(image|None, prompt)`), `MedGemmaVQATool` LangChain wrapper. Verified:
  `tests/test_medgemma.py` (3 pass), `scripts/bench_medgemma.py`. DONE.
  - Measured on L4 bf16: ~15.6 tok/s decode, peak VRAM **8.7 GB / 24 GB**, 15s load.
  - transformers 5.x: use `dtype=` not `torch_dtype=`.
- Phase 3: `nodes/classify.py` (+singleton), `nodes/triage.py` (ACR/Annarumma/
  Baltruschat tier weights → `urgency_score = sum(w·p)`), `worklist.py` (JSON-
  persisted store), `ui/worklist.py` (Streamlit). Verified: `tests/test_triage.py`
  (5 pass), `scripts/phase3_check.py`. DONE.
  - IMPORTANT honesty note: the done-when "pneumothorax>0.5 → top quartile" is
    asserted on CONTROLLED data in the unit test, NOT on ChestAgentBench figures.
    Those figures are OOD for the DenseNet (CT panels, annotated multi-image
    figures) so it fires broadly; a 0.5 threshold is meaningless on them, and the
    additive sum lets many co-elevated findings outrank one true critical finding.
    The real-data script only asserts pipeline-correctness + sort order, and
    reports the OOD caveat. Do not "fix" by gaming the figure data.
- Phase 4: `prompts/draft_report.py`, `nodes/draft.py` (MedGemma FINDINGS/
  IMPRESSION, regex section parse), `nodes/visualize.py` (Grad-CAM on classifier
  top-1, target layer `features.norm5`), `ui/case_view.py`. Verified:
  `tests/test_draft.py` (6 pass), `scripts/phase4_check.py`. DONE.
  - On OOD figures MedGemma correctly DISMISSES borderline (~0.5) classifier
    findings via a clean report ("lungs are clear") rather than inventing them —
    that counts as "visually dismissed" per the done-when. The grounding check is
    dismissal-aware (blanket-normal phrasing covers unnamed findings).
- Phase 5: `prompts/synonyms.py` (18-pathology synonym map), `nodes/qc.py`
  (omission QC: lexical synonym match → MedGemma LLM-judge fallback; judge is
  injectable for tests), `ui/qc_panel.py` (Streamlit Dismiss/Add panel). Verified:
  `tests/test_qc.py` (6 pass, stub judge), `scripts/phase5_check.py` (real judge;
  flags omitted PTX, clears "no pneumothorax" + costophrenic-blunting synonym).
  - QC threshold is >0.7 (not 0.5). Lexical match short-circuits the LLM so the
    deterministic done-when cases (b)/(c) never depend on the model.
- Phase 6: `prompts/explainer.py`, `nodes/explain.py` (text-only plain-language
  translation + `build_glossary` {term::def} + pure `highlight_html` hover tags),
  `ui/explainer.py`. Verified: `tests/test_explain.py` (6 pass),
  `scripts/phase6_check.py` (modality-agnostic: tested on a CT-head report).
  - GOTCHA: the first explainer prompt made MedGemma ECHO the report verbatim
    (no translation). Fixed by an explicit "do NOT copy the wording, replace each
    term with everyday words" prompt; phase6_check now asserts hard jargon
    (intraparenchymal/vasogenic/...) is ABSENT from the plain version so an echo
    can never pass again.
- Phase 7: `graph.py` (full LangGraph state machine, human-in-the-loop interrupt
  before `review`, `run_to_review`/`resume_review` helpers), unified Streamlit
  app `ui/app.py` (st.navigation: Worklist/Case/Explainer/Settings) with a shared
  design system `ui/theme.py` + `.streamlit/config.toml`. Verified:
  `tests/test_graph.py` (5 pass), `scripts/phase7_check.py` (real graph
  end-to-end), headless app boot (/healthz 200). DONE.

- Phase 8: ChestAgentBench eval (`eval/chestagentbench.py` agent harness +
  `eval/direct.py` direct multi-image VLM), live resumable scoreboard, NVIDIA NIM
  orchestrator backend. Results in `radquant/eval/results.md`. IN PROGRESS.
  - **BIG finding**: the agent (blind Llama orchestrator relaying MedGemma text
    descriptions) scored **36.7%**; letting **MedGemma see all figures + answer
    the MCQ directly** (multi-image, concise CoT) scored **56.5%** (n=200, ±7%) —
    +20 pts, 6× faster, ties GPT-4o (56.4%), near MedRAX SOTA (63.1%). The relay
    was the bottleneck, not the model (MedGemma-4B is best open CXR VLM per ReXVQA).
  - GOTCHA: CoT truncated before "Answer:" → 33% unparsed. Fixed via concise-CoT
    prompt + 512-token budget + hardened `extract_letter`. Always validate on
    n≥150; the n=30 read (63%) was optimistic vs the true ~56.5%.
  - Eval orchestrator key: Lightning secret **`NVIDIA_KEY`** (nvapi-…); resolve
    via `config.nvidia_key()`. NIM has no daily cap (unlike Groq's 1k RPD).

## Naming (locked)
- The project AND platform name is **RadQuant** — nothing else. The Python
  package is `radquant`; runtime env vars are `RADQUANT_QUANT/_DEVICE/_VRAM_MB`.
  (Renamed from the original `radcopilot`/"Medical Radiology Copilot" on user
  request; the word "copilot" must not reappear anywhere.)
