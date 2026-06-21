#!/usr/bin/env python3
"""End-to-end smoke test: image -> classifier -> MedGemma (image & text) -> Groq.

Each step prints OK or fails fast. Run after `python scripts/setup.py`.
This is deliberately self-contained (no Phase 2+ modules yet); it validates that
every layer of the stack actually works on this GPU.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from radquant import config  # noqa: E402
from radquant.data import sample  # noqa: E402


def step(name: str):
    print(f"\n--- {name} ---")


def fail(msg: str):
    print(f"\033[31m✗ {msg}\033[0m")
    sys.exit(1)


def good(msg: str):
    print(f"\033[32m✓ {msg}\033[0m")


def main() -> None:
    # 1. Sample image -------------------------------------------------------- #
    step("1. Sample image")
    img_path = sample(1)[0]
    good(f"sample(1) -> {img_path}")

    # 2. TorchXRayVision classifier ----------------------------------------- #
    step("2. TorchXRayVision classifier")
    import numpy as np
    import torch
    import torchxrayvision as xrv
    import skimage.io
    from PIL import Image

    img = np.array(Image.open(img_path).convert("L"), dtype=np.float32)
    img = xrv.datasets.normalize(img, 255)
    img = img[None, ...]  # add channel dim
    transform = xrv.datasets.XRayCenterCrop()
    img = transform(img)
    model = xrv.models.DenseNet(weights=config.XRV_WEIGHTS)
    with torch.no_grad():
        out = model(torch.from_numpy(img)[None, ...])
    preds = dict(zip(model.pathologies, out[0].tolist()))
    top = sorted(((v, k) for k, v in preds.items() if k), reverse=True)[:3]
    good("classifier ran; top findings: " +
         ", ".join(f"{k}={v:.2f}" for v, k in top))

    # 3. MedGemma multimodal (image + text) --------------------------------- #
    step("3. MedGemma image+text")
    import torch
    from transformers import AutoModelForImageTextToText, AutoProcessor

    dtype = torch.bfloat16 if config.quant() == "bf16" else torch.float16
    t0 = time.time()
    processor = AutoProcessor.from_pretrained(config.MEDGEMMA_REPO)
    mg = AutoModelForImageTextToText.from_pretrained(
        config.MEDGEMMA_REPO, dtype=dtype, device_map="cuda",  # transformers 5.x: `dtype`
    )
    print(f"   MedGemma loaded in {time.time() - t0:.0f}s "
          f"(peak VRAM {torch.cuda.max_memory_allocated() / 1e9:.1f} GB)")

    pil = Image.open(img_path).convert("RGB")
    messages = [{"role": "user", "content": [
        {"type": "image", "image": pil},
        {"type": "text", "text": "Describe what you see in this chest X-ray in one sentence."},
    ]}]
    inputs = processor.apply_chat_template(
        messages, add_generation_prompt=True, tokenize=True,
        return_dict=True, return_tensors="pt",
    ).to(mg.device)
    in_len = inputs["input_ids"].shape[-1]
    with torch.inference_mode():
        gen = mg.generate(**inputs, max_new_tokens=80, do_sample=False)
    text = processor.decode(gen[0][in_len:], skip_special_tokens=True).strip()
    if not text:
        fail("MedGemma multimodal returned empty output")
    good(f"image+text -> {text[:160]}")

    # 4. MedGemma text-only (explainer path) -------------------------------- #
    step("4. MedGemma text-only")
    report = ("FINDINGS: Mild cardiomegaly. Small right pleural effusion. "
              "No pneumothorax. IMPRESSION: Findings suggest mild heart failure.")
    messages = [{"role": "user", "content": [
        {"type": "text", "text": "Translate this radiology report to plain English "
                                 f"for a patient:\n{report}"},
    ]}]
    inputs = processor.apply_chat_template(
        messages, add_generation_prompt=True, tokenize=True,
        return_dict=True, return_tensors="pt",
    ).to(mg.device)
    in_len = inputs["input_ids"].shape[-1]
    with torch.inference_mode():
        gen = mg.generate(**inputs, max_new_tokens=120, do_sample=False)
    text = processor.decode(gen[0][in_len:], skip_special_tokens=True).strip()
    if not text:
        fail("MedGemma text-only returned empty output")
    good(f"text-only -> {text[:160]}")

    # 5. Groq orchestrator -------------------------------------------------- #
    step("5. Groq orchestrator")
    key = config.groq_key()
    body = json.dumps({
        "model": config.GROQ_MODEL,
        "messages": [{"role": "user",
                      "content": "In one short sentence, what is triage in radiology?"}],
        "max_tokens": 256, "temperature": 0,
    }).encode()
    req = urllib.request.Request(
        f"{config.GROQ_BASE_URL}/chat/completions", data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "User-Agent": "radquant/0.1"},  # Cloudflare 403s default urllib UA
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)
    reply = data["choices"][0]["message"]["content"].strip()
    if not reply:
        fail("Groq returned empty content (raise max_tokens?)")
    good(f"groq -> {reply[:160]}")

    print("\n\033[32m✓ Smoke test passed — full stack is operational.\033[0m\n")


if __name__ == "__main__":
    main()
