# ChestAgentBench — RadQuant results

**Benchmark:** [ChestAgentBench](https://huggingface.co/datasets/wanglab/chest-agent-bench)
— 2,500 six-choice questions over 675 Eurorad chest-imaging cases, 7 skill
categories. Random chance = 16.7%.

**Our system:** MedGemma 1.5 4B (open weights) on a **single NVIDIA L4 (24 GB)**,
bf16. Orchestration (agent config) via free Groq / NVIDIA NIM open LLMs. **Zero
proprietary-API cost in the medical path.**

> Evaluated on a **random 200-question subset** (seed 0), not the full 2,500, for
> compute reasons. 95% CI ≈ ±7%. Numbers are honest and reproducible via
> `python scripts/run_eval.py --direct --limit 200`.

## Headline

| System | Backbone | Overall | Hardware / cost |
|---|---|---|---|
| MedRAX (paper SOTA) | GPT-4o agent | **63.1%** | GPT-4o API ($$) |
| Llama-3.2-90B-Vision | 90B | 57.9% | ~180 GB VRAM |
| **RadQuant — direct** | **MedGemma 1.5 4B** | **56.5%** | **1× L4, $0 API** |
| GPT-4o | — | 56.4% | GPT-4o API ($$) |
| CheXagent | 8B CXR VLM | 39.5% | — |
| RadQuant — agent | Llama-3.3-70B + tools | 36.7%¹ | free API |

¹ agent config measured on the 30-question calibration set.

**RadQuant-direct (56.5%) matches GPT-4o (56.4%)** on a 4B open model on one L4,
and lands within the 90B model's range — at zero API cost in the medical path.

## Per-category (RadQuant-direct, n=200) vs baselines

| Category | RadQuant-direct | GPT-4o | MedRAX |
|---|---|---|---|
| Detection | 63.5% | 58.7% | 64.1% |
| Classification | 58.7% | 54.6% | 62.9% |
| Localization | 53.2% | 59.0% | 63.6% |
| Comparison | 52.9% | 55.5% | 61.8% |
| Relationship | 50.7% | 59.0% | 63.1% |
| Diagnosis | 57.5% | 52.6% | 62.5% |
| Characterization | 58.2% | 56.1% | 64.0% |

We **beat GPT-4o on detection, classification, diagnosis, characterization** and
trail it on the **multi-image** skills (localization, comparison, relationship) —
expected, since those need cross-figure reasoning a 4B model does less well.

## The key finding: architecture, not model

The original agent design — a **blind text orchestrator** (Llama-3.3-70B) routing
**MedGemma's free-text descriptions** of each figure — scored only **36.7%**. The
orchestrator never saw the image and lost the visual detail needed to separate
the options.

Letting **MedGemma see all the figures and answer the question itself**
(multi-image, options-aware, concise chain-of-thought) lifted accuracy to
**56.5% — a +20-point jump — and ran 6× faster** (8 s/q vs 50 s/q). This matches
the literature: on the ReXVQA CXR-VQA benchmark, MedGemma-4B is the strongest
open VLM. We had been using a strong model through a lossy interface.

A 33% answer-parse-failure rate (CoT truncating before the answer) was fixed with
a concise-CoT prompt + adequate token budget + a hardened letter extractor.

## Honest limitations

- **200-question subset**, not all 2,500 (±7% CI). The agent figure is n=30.
- **Multi-image cap of 6** figures/question (~4% of questions have more) slightly
  handicaps us on comparison/relationship.
- The **TorchXRayVision classifier is out-of-distribution** on Eurorad figures
  (CT panels, annotations); it is not used in the direct path.
- This is **research/assistive only — not a medical device.**

## Reproduce

```bash
python scripts/run_eval.py --direct --limit 200          # direct VLM (this result)
python scripts/run_eval.py --limit 30 --backend nvidia   # agent config
```
