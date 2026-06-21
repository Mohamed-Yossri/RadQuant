"""MedGemma 1.5 4B — VRAM-aware singleton loader + clean generate() API.

One model instance is shared process-wide (the weights are ~8 GB; we never want
two copies). Quantization is chosen from the runtime config written by
scripts/setup.py: bf16 on >16 GB GPUs (L4), 4-bit (bitsandbytes) on <=16 GB (T4).

Public API:
    mg = get_medgemma()                       # lazy singleton
    mg.generate(image, prompt)                # image: PIL.Image | None
    generate(image, prompt)                   # module-level shortcut
    MedGemmaVQATool()                         # LangChain tool for the orchestrator
"""

from __future__ import annotations

import threading
import time
from typing import Optional

import torch
from PIL import Image

from radquant import config

_INSTANCE: Optional["MedGemma"] = None
_LOCK = threading.Lock()


class MedGemma:
    """Thin wrapper around the MedGemma processor + model."""

    def __init__(self, quant: Optional[str] = None, device: str = "cuda"):
        from transformers import AutoModelForImageTextToText, AutoProcessor

        self.quant = quant or config.quant()
        self.device = device
        self.repo = config.MEDGEMMA_REPO

        load_kwargs: dict = {}
        if self.quant == "4bit":
            from transformers import BitsAndBytesConfig

            load_kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16,
            )
            load_kwargs["device_map"] = "auto"
        else:  # bf16
            load_kwargs["dtype"] = torch.bfloat16
            load_kwargs["device_map"] = device

        t0 = time.time()
        self.processor = AutoProcessor.from_pretrained(self.repo)
        self.model = AutoModelForImageTextToText.from_pretrained(self.repo, **load_kwargs)
        self.model.eval()
        self.load_seconds = time.time() - t0

    @torch.inference_mode()
    def generate(
        self,
        image: Optional[Image.Image | str],
        prompt: str,
        max_new_tokens: int = 512,
        system: Optional[str] = None,
        do_sample: bool = False,
        temperature: float = 1.0,
    ) -> str:
        """Run MedGemma on an optional image plus a text prompt.

        Args:
            image: a PIL image, a path string, or None for the text-only path.
            prompt: the user instruction.
            max_new_tokens: generation budget.
            system: optional system message.

        Returns:
            The decoded model response (new tokens only), stripped.
        """
        if isinstance(image, str):
            image = Image.open(image)

        content: list[dict] = []
        if image is not None:
            content.append({"type": "image", "image": image.convert("RGB")})
        content.append({"type": "text", "text": prompt})

        messages = []
        if system:
            messages.append({"role": "system", "content": [{"type": "text", "text": system}]})
        messages.append({"role": "user", "content": content})

        inputs = self.processor.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
        ).to(self.model.device)

        in_len = inputs["input_ids"].shape[-1]
        gen = self.model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=do_sample,
            temperature=temperature if do_sample else None,
        )
        return self.processor.decode(gen[0][in_len:], skip_special_tokens=True).strip()

    @torch.inference_mode()
    def generate_multi(
        self,
        images: list,
        prompt: str,
        labels: Optional[list] = None,
        system: Optional[str] = None,
        max_new_tokens: int = 384,
        do_sample: bool = False,
        temperature: float = 0.7,
        pan_and_scan: bool = False,
    ) -> str:
        """Generate over MULTIPLE interleaved images (Gemma3 multi-image).

        Args:
            images: list of PIL images or path strings.
            labels: optional per-image captions (e.g. ["Figure 1", "Figure 2A"]).
            pan_and_scan: tile large/non-square images into crops for higher
                effective resolution (helps multi-panel / annotated figures).
        """
        pil = [(Image.open(i) if isinstance(i, str) else i).convert("RGB") for i in images]
        content: list[dict] = []
        for idx, im in enumerate(pil):
            if labels:
                content.append({"type": "text", "text": f"{labels[idx]}:"})
            content.append({"type": "image", "image": im})
        content.append({"type": "text", "text": prompt})

        messages = []
        if system:
            messages.append({"role": "system", "content": [{"type": "text", "text": system}]})
        messages.append({"role": "user", "content": content})

        pas_kwargs = (
            {"do_pan_and_scan": True, "pan_and_scan_max_num_crops": 2,
             "pan_and_scan_min_crop_size": 256, "pan_and_scan_min_ratio_to_activate": 1.2}
            if pan_and_scan else {}
        )
        inputs = self.processor.apply_chat_template(
            messages, add_generation_prompt=True, tokenize=True,
            return_dict=True, return_tensors="pt", **pas_kwargs,
        ).to(self.model.device)
        in_len = inputs["input_ids"].shape[-1]
        gen = self.model.generate(
            **inputs, max_new_tokens=max_new_tokens,
            do_sample=do_sample, temperature=temperature if do_sample else None,
        )
        return self.processor.decode(gen[0][in_len:], skip_special_tokens=True).strip()


def get_medgemma() -> MedGemma:
    """Return the process-wide MedGemma singleton (loads it on first call)."""
    global _INSTANCE
    if _INSTANCE is None:
        with _LOCK:
            if _INSTANCE is None:
                _INSTANCE = MedGemma()
    return _INSTANCE


def generate(image: Optional[Image.Image | str], prompt: str, **kw) -> str:
    """Module-level shortcut: ``get_medgemma().generate(...)``."""
    return get_medgemma().generate(image, prompt, **kw)
