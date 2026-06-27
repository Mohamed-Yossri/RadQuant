"""
radquant/models/medgemma.py — VRAM-aware MedGemma 1.5 4B singleton.

Verified on L4 (24 GB, bf16): ~8.7 GB VRAM, ~15.6 tok/s, 15 s load.
On T4 (16 GB) uses 4-bit quantization via bitsandbytes.

Key: transformers 5.x uses dtype= not torch_dtype= (CLAUDE.md).
"""

from __future__ import annotations

import logging
import threading
from typing import Union

logger = logging.getLogger(__name__)

MODEL_ID = "google/medgemma-1.5-4b-it"
_lock = threading.Lock()
_instance: "MedGemmaModel | None" = None


class MedGemmaModel:
    """Thread-safe singleton wrapping MedGemma 1.5 4B."""

    def __init__(self) -> None:
        import torch
        from transformers import AutoProcessor, AutoModelForImageTextToText
        from radquant.config import hf_token, quant_mode

        mode = quant_mode()
        logger.info("MedGemma: loading %s in %s mode …", MODEL_ID, mode)

        token = hf_token()

        if mode == "4bit":
            from transformers import BitsAndBytesConfig
            bnb_cfg = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16)
            self._model = AutoModelForImageTextToText.from_pretrained(
                MODEL_ID,
                quantization_config=bnb_cfg,
                device_map="auto",
                token=token,
            )
        else:
            self._model = AutoModelForImageTextToText.from_pretrained(
                MODEL_ID,
                dtype=torch.bfloat16,
                device_map="auto",
                token=token,
            )

        self._processor = AutoProcessor.from_pretrained(MODEL_ID, token=token)
        self._device = next(self._model.parameters()).device
        logger.info("MedGemma: loaded on %s", self._device)

    @classmethod
    def get_instance(cls) -> "MedGemmaModel":
        global _instance
        if _instance is None:
            with _lock:
                if _instance is None:
                    _instance = cls()
        return _instance

    def generate(
        self,
        prompt: str,
        images: list | None = None,
        system: str | None = None,
        max_new_tokens: int = 512,
    ) -> str:
        """
        Generate text from MedGemma.

        Parameters
        ----------
        prompt      : user-turn text
        images      : list of PIL Images (0 = text-only, 1+ = multimodal)
        system      : optional system prompt
        max_new_tokens : token budget
        """
        import torch

        messages = []
        if system:
            messages.append({"role": "system", "content": system})

        # Build content list for the user turn
        content = []
        if images:
            for img in images:
                content.append({"type": "image", "image": img})
        content.append({"type": "text", "text": prompt})
        messages.append({"role": "user", "content": content})

        inputs = self._processor.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
            return_tensors="pt",
            return_dict=True,
        ).to(self._device)

        with torch.inference_mode():
            output_ids = self._model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
            )

        # Decode only the newly generated tokens
        input_len = inputs["input_ids"].shape[-1]
        generated = output_ids[0][input_len:]
        return self._processor.decode(generated, skip_special_tokens=True).strip()
