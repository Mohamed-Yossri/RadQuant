"""Phase 2 unit test: MedGemma multimodal + text-only inference, VRAM bound.

Loads the ~8 GB model once (singleton). Run: pytest tests/test_medgemma.py -s
Skips automatically if no CUDA GPU is present.
"""

import pytest

torch = pytest.importorskip("torch")
if not torch.cuda.is_available():
    pytest.skip("CUDA GPU required for MedGemma", allow_module_level=True)

from radquant.data import sample
from radquant.models import get_medgemma

GPU_VRAM_GB = torch.cuda.get_device_properties(0).total_memory / 1e9


@pytest.fixture(scope="module")
def mg():
    return get_medgemma()


def test_multimodal(mg):
    """Image + text yields a non-trivial description."""
    img_path = str(sample(1)[0])
    out = mg.generate(img_path, "Describe this chest X-ray in one sentence.",
                      max_new_tokens=80)
    assert isinstance(out, str) and len(out.split()) >= 3, out
    print("\n[multimodal]", out[:160])


def test_text_only(mg):
    """Text-only path (the explainer) yields plain-language output."""
    report = ("FINDINGS: Mild cardiomegaly. Small right pleural effusion. "
              "IMPRESSION: Mild heart failure.")
    out = mg.generate(None, f"Translate this radiology report for a patient:\n{report}",
                      max_new_tokens=120)
    assert isinstance(out, str) and len(out.split()) >= 5, out
    print("\n[text-only]", out[:160])


def test_peak_vram_under_limit(mg):
    """Peak allocation must stay comfortably under the GPU's capacity."""
    peak_gb = torch.cuda.max_memory_allocated() / 1e9
    print(f"\n[vram] peak={peak_gb:.1f} GB / {GPU_VRAM_GB:.0f} GB")
    assert peak_gb < GPU_VRAM_GB * 0.9, f"peak {peak_gb:.1f} GB too close to limit"
