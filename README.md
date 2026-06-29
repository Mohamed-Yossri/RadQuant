# Uncertainty-Aware Selective Prediction

## إيه اللي بيضيفه

**Monte Carlo Dropout** على الـ DenseNet classifier — بدل ما يعمل forward pass واحد، بيعمل **10 passes** مع Dropout مفعّل ويحسب الـ variance.

النتيجة:
- **Certain findings** — المودل واثق فيهم ← بيروحوا للـ draft مباشرة
- **Uncertain findings** — variance عالي ← بيتعرضوا للراديولوجيست مع علامة تحذير
- **Coverage metric** — % الـ findings اللي المودل واثق فيها

ده بيجسّد النتيجة العلمية في `eval/results.md`:
> τ=0.75 → 66.7% accuracy على 70% coverage — بيتفوق على MedRAX/GPT-4o (63.1% all-case)

---

## الخطوات

### خطوة 1 — نسخ الملف

```bash
cp radquant/nodes/uncertainty.py  <repo>/radquant/nodes/uncertainty.py
```

---

### خطوة 2 — تعديل `radquant/graph.py`

**2a.** بعد السطر:
```python
from radquant.nodes.qc import qc
```
ضيف:
```python
from radquant.nodes.uncertainty import uncertainty
```

**2b.** في `build_graph()`، غيّر الـ nodes list من:
```python
("ingest", ingest), ("classify", classify), ("triage", triage),
```
لـ:
```python
("ingest", ingest), ("uncertainty", uncertainty), ("triage", triage),
```

**2c.** غيّر الـ edges من:
```python
g.add_edge("ingest", "classify")
g.add_edge("classify", "triage")
```
لـ:
```python
g.add_edge("ingest", "uncertainty")
g.add_edge("uncertainty", "triage")
```

---

### خطوة 3 — تعديل `radquant/ui/case_view.py`

**3a.** بعد:
```python
from radquant.ui.qc_panel import render_omissions_panel
```
ضيف:
```python
from radquant.nodes.uncertainty import run_selective_prediction, render_uncertainty_panel
```

**3b.** دور على السطر ده في زرار Draft + Grad-CAM:
```python
findings = case.findings or classify_image(case.image_path)
```
استبدله بـ:
```python
unc_result = run_selective_prediction(case.image_path)
findings           = unc_result["findings"]
certain_findings   = unc_result["certain_findings"]
uncertain_findings = unc_result["uncertain_findings"]
cov_scores         = unc_result["uncertainty_scores"]
coverage           = unc_result["coverage"]
```

**3c.** في نفس الـ block، بعد:
```python
st.session_state[key].update({"findings": findings, "f": f_text, ...})
```
ضيف:
```python
st.session_state[key].update({
    "certain": certain_findings,
    "uncertain": uncertain_findings,
    "cov": cov_scores,
    "coverage": coverage,
})
```

**3d.** بعد الـ `right` column (بعد `i_val` text area)، ضيف:
```python
if art and art.get("certain") is not None:
    with st.expander("🎯 Uncertainty — Selective Prediction", expanded=True):
        render_uncertainty_panel(
            art["certain"],
            art["uncertain"],
            art["cov"],
            art["coverage"],
        )
```

---

### خطوة 4 — تحقق

```bash
python -c "from radquant.nodes.uncertainty import uncertainty; print('OK')"
```

---

### خطوة 5 — commit

```bash
git add radquant/nodes/uncertainty.py radquant/graph.py radquant/ui/case_view.py
git commit -m "feat(nodes): MC Dropout uncertainty-aware selective prediction

Replaces single-pass classify with K=10 Monte Carlo Dropout passes.
Findings are split into certain (CoV < 0.15) and uncertain (CoV >= 0.15).

Pipeline: ingest → uncertainty → triage → visualize → draft → review → qc

- certain_findings  → passed to draft node (model is confident)
- uncertain_findings → shown to radiologist as deferred findings
- coverage metric   → mirrors τ=0.75 regime in eval/results.md
                       (target: 70% coverage, 66.7% accuracy)

New:      radquant/nodes/uncertainty.py
Modified: radquant/graph.py (import + node wiring)
Modified: radquant/ui/case_view.py (run_selective_prediction + panel)"

git push
```
