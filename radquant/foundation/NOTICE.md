# Attribution

The modules in `radquant/foundation/` are derived from **MedRAX**
(Fallahpour et al., "MedRAX: Medical Reasoning Agent for Chest X-ray," ICML 2025,
arXiv:2502.02673), https://github.com/bowang-lab/MedRAX, licensed under
**Apache License 2.0**.

We vendor a *stripped subset* of MedRAX:

| RadQuant file | Derived from (MedRAX) | Changes |
|---|---|---|
| `tools/classification.py` | `medrax/tools/classification.py` | verbatim, header added |
| `tools/dicom.py` | `medrax/tools/dicom.py` | verbatim, header added |
| `tools/visualizer.py` | `medrax/tools/utils.py` | lazy matplotlib import |
| `agent.py` | `medrax/agent/agent.py` | verbatim, header added |
| `build.py` | `medrax/main.py` `initialize_agent` | rewritten for Groq `gpt-oss-120b` |

Removed entirely (not part of RadQuant): `LlavaMedTool`, `XRayVQATool`
(CheXagent), `XRayPhraseGroundingTool` (Maira-2), `ChestXRayReportGeneratorTool`
(SwinV2), `ChestXRayGeneratorTool` (RoentGen), `ChestXRaySegmentationTool`.
Their roles are taken over by MedGemma 1.5 4B (see PLAN.md).
