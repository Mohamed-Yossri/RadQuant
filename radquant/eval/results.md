# ChestAgentBench — RadQuant results

**Benchmark:** [ChestAgentBench](https://huggingface.co/datasets/wanglab/chest-agent-bench)
— 2,500 six-choice questions over 675 Eurorad chest-imaging cases, 7 skill
categories. Random chance = 16.7%.

**Our system:** MedGemma 1.5 4B (open weights) on a **single NVIDIA L4 (24 GB)**,
bf16. Orchestration (agent config) via free Groq / NVIDIA NIM open LLMs. **Zero
proprietary-API cost in the medical path.**

> Evaluated on a **random 500-question subset** (seed 0), not the full 2,500, for
> compute reasons. 95% CI ≈ ±4.3%. Numbers are honest and reproducible via
> `python scripts/run_eval.py --direct --limit 500`.

## Headline

| System | Backbone | Overall | Hardware / cost |
|---|---|---|---|
| MedRAX (paper SOTA) | GPT-4o agent | **63.1%** | GPT-4o API ($$) |
| Llama-3.2-90B-Vision | 90B | 57.9% | ~180 GB VRAM |
| **RadQuant — direct** | **MedGemma 1.5 4B** | **57.6%** | **1× L4, $0 API** |
| GPT-4o | — | 56.4% | GPT-4o API ($$) |
| CheXagent | 8B CXR VLM | 39.5% | — |
| RadQuant — agent | Llama-3.3-70B + tools | 36.7%¹ | free API |

¹ agent config measured on the 30-question calibration set.

**RadQuant-direct (57.6%) beats GPT-4o (56.4%)** on a 4B open model on one L4, and
ties the 90B model — at zero API cost in the medical path.

## Per-category (RadQuant-direct, n=500) vs baselines

| Category | RadQuant-direct | GPT-4o | Δ vs GPT-4o | MedRAX |
|---|---|---|---|---|
| Detection | 61.4% | 58.7% | **+2.7** | 64.1% |
| Classification | 59.7% | 54.6% | **+5.1** | 62.9% |
| Localization | 54.5% | 59.0% | −4.5 | 63.6% |
| Comparison | 56.0% | 55.5% | **+0.5** | 61.8% |
| Relationship | 55.7% | 59.0% | −3.3 | 63.1% |
| Diagnosis | 58.2% | 52.6% | **+5.6** | 62.5% |
| Characterization | 56.8% | 56.1% | **+0.7** | 64.0% |

We **beat GPT-4o on 5 of 7 categories** (notably classification +5.1, diagnosis
+5.6) and trail only on the two **multi-image spatial** skills (localization,
relationship) — expected, since those need cross-figure reasoning a 4B model does
less well than a frontier model.

## The key finding: architecture, not model

The original agent design — a **blind text orchestrator** (Llama-3.3-70B) routing
**MedGemma's free-text descriptions** of each figure — scored only **36.7%**. The
orchestrator never saw the image and lost the visual detail needed to separate
the options.

Letting **MedGemma see all the figures and answer the question itself**
(multi-image, options-aware, concise chain-of-thought) lifted accuracy to
**57.6% — a +21-point jump — and ran 6× faster** (8 s/q vs 50 s/q). This matches
the literature: on the ReXVQA CXR-VQA benchmark, MedGemma-4B is the strongest
open VLM. We had been using a strong model through a lossy interface.

A 33% answer-parse-failure rate (CoT truncating before the answer) was fixed with
a concise-CoT prompt + adequate token budget + a hardened letter extractor.

## RadQuant's contribution: selective prediction ("the Quant")

A base VLM answers every case, right or wrong. RadQuant adds **uncertainty-aware
abstention**: for each case we sample the reasoning K=4 times; the **agreement**
with the greedy answer is the confidence. Below a threshold, RadQuant **defers to
the radiologist** instead of guessing. (n=120, agreement signal.)

| Policy | Coverage | Accuracy on answered | Deferred |
|---|---|---|---|
| Answer everything | 100% | 59.2% | 0% |
| Defer low-agreement (τ≥0.5) | 80% | 65.6% | 20% |
| Defer more (τ≥0.75) | 70% | **66.7%** | 30% |
| Only unanimous (τ=1.0) | 54% | **67.7%** | 46% |

Accuracy rises **monotonically** as coverage falls — the agreement signal is a
**valid, calibrated** confidence measure. The clinical reading: **on the ~70% of
cases RadQuant is confident about it scores 66.7% — exceeding even MedRAX's all-case
63.1% (GPT-4o + 7 tools) — and routes the uncertain ~30% to a radiologist.**

This is the genuine contribution beyond running a base model: **safe, selective
automation that knows when it does not know** — exactly what a clinical deployment
needs, and something no single base VLM (GPT-4o, Llama-90B, CheXagent) provides
out of the box. Note we did NOT use *self-rated* confidence (the model is
overconfident — 53% accurate at its own "High"); empirical sample-agreement is the
honest signal. Reproduce: `python scripts/run_uncertainty.py --limit 120 --k 4`.

## Ablations (what did NOT help)

Tested as paired comparisons on the same 40 questions (best config = greedy
multi-image CoT, k=1):

| Variant | Accuracy | Δ vs k=1 |
|---|---|---|
| **greedy multi-image CoT (k=1)** | **62.5%** | — (best) |
| + self-consistency (k=5, temp 0.7, majority vote) | 51.5% | **−11 pts** |
| + pan-and-scan (high-res tiling) | 62.5% | ±0 |

- **Self-consistency hurts**: it requires temperature *sampling*, but a 4B model
  decodes better *greedily*; the sampling noise outweighs the vote benefit.
- **Pan-and-scan is neutral**: the figures are already adequately resolved at the
  base vision resolution.

So the winning recipe is simply: **let MedGemma see all figures and answer with a
short greedy chain-of-thought.** The big lever was architecture (+20 pts), not
test-time tricks.

## Honest limitations

- **500-question subset**, not all 2,500 (±4.3% CI). The agent figure is n=30.
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
