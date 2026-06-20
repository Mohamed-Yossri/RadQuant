# Medical Radiology Copilot

An open-source, locally-deployable AI copilot for radiologists — a
workflow-focused extension of [MedRAX](https://github.com/bowang-lab/MedRAX)
(ICML 2025) for chest X-ray interpretation.

> ⚠️ **Research / assistive demo only. Not for clinical use.**

See [PLAN.md](PLAN.md) for the full build plan and [CLAUDE.md](CLAUDE.md) for
environment notes.

## Quickstart

```bash
# Credentials: provide HF_TOKEN and GROQ_TOKEN (Lightning secrets or a .env file)
python scripts/setup.py        # installs deps, caches weights, fetches data
python scripts/smoke_test.py   # validates the full stack end-to-end
```

Built on MedRAX (Fallahpour et al., ICML 2025, arXiv:2502.02673), Apache-2.0.
