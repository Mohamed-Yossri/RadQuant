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
- Resolve them only via `radcopilot.config` (`hf_token()`, `groq_key()`).

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
- Phase 0: scaffold + `scripts/setup.py` + `scripts/smoke_test.py`. DONE/in-progress.
