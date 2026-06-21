# RadQuant

**RadQuant** is an open-source, locally-deployable AI assistant for radiologists —
a workflow-focused extension of [MedRAX](https://github.com/bowang-lab/MedRAX)
(ICML 2025) for chest X-ray interpretation. It runs the medical reasoning path on
fully open weights (MedGemma 1.5 4B + TorchXRayVision) on a single GPU, using a
free Groq-hosted open LLM only for agent orchestration.

> ⚠️ **Research / assistive demo only. Not for clinical use.** No node finalizes a
> report without radiologist review.

See [PLAN.md](PLAN.md) for the full build plan and [CLAUDE.md](CLAUDE.md) for
environment notes.

## Workflows

- **Triage** — classifier-driven urgency scoring reorders the worklist.
- **Draft report** — MedGemma drafts FINDINGS/IMPRESSION grounded in classifier findings, with a Grad-CAM heatmap.
- **Omission QC** — flags high-confidence findings missing from the edited report.
- **Patient explainer** — plain-language, modality-agnostic translation of any report.

## Pipeline (LangGraph)

```
ingest → classify → triage → visualize → draft → review
review → qc → END        (finalize)
review → draft           (regenerate)
explain                  (side-call from any report)
```

## Quickstart

```bash
# Credentials: provide HF_TOKEN and GROQ_TOKEN (Lightning secrets or a .env file)
python scripts/setup.py            # installs deps, caches weights, fetches data
python scripts/smoke_test.py       # validates the full stack end-to-end
streamlit run radquant/ui/app.py   # launch the RadQuant app
```

Built on MedRAX (Fallahpour et al., ICML 2025, arXiv:2502.02673), Apache-2.0.
