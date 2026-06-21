"""LangChain tool wrapper so the Groq orchestrator can call MedGemma.

MedGemma 1.5 4B is the medical VLM that replaces MedRAX's LLaVA-Med/CheXagent
VQA path: give it an image path + a question, or just text, and it answers.
"""

from typing import Optional, Tuple, Type

from pydantic import BaseModel, Field
from langchain_core.callbacks import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain_core.tools import BaseTool


class MedGemmaInput(BaseModel):
    """Input for the MedGemma medical VLM."""

    prompt: str = Field(..., description="The question or instruction for the model.")
    image_path: Optional[str] = Field(
        None,
        description="Optional path to a chest X-ray (JPG/PNG). Omit for text-only "
        "tasks such as report translation or summarization.",
    )
    max_new_tokens: int = Field(512, description="Generation length budget.")


class MedGemmaVQATool(BaseTool):
    """MedGemma 1.5 4B: visual question answering + medical text generation."""

    name: str = "medgemma"
    description: str = (
        "A medical vision-language model (MedGemma 1.5 4B). Use it to describe a "
        "chest X-ray, answer visual questions, draft report text, or translate a "
        "report into plain language. Provide a 'prompt'; optionally a path to an "
        "image via 'image_path'. Output is the model's generated text."
    )
    args_schema: Type[BaseModel] = MedGemmaInput
    # Hard ceiling on generation length, regardless of what the caller requests.
    # Keeps agentic loops (e.g. the eval) fast; None = no cap.
    max_tokens_cap: Optional[int] = None

    def _run(
        self,
        prompt: str,
        image_path: Optional[str] = None,
        max_new_tokens: int = 512,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> Tuple[dict, dict]:
        from radquant.models.medgemma import generate

        if self.max_tokens_cap:
            max_new_tokens = min(max_new_tokens, self.max_tokens_cap)
        try:
            text = generate(image_path, prompt, max_new_tokens=max_new_tokens)
            return {"response": text}, {
                "image_used": bool(image_path),
                "analysis_status": "completed",
            }
        except Exception as e:  # noqa: BLE001
            return {"error": str(e)}, {"analysis_status": "failed"}

    async def _arun(
        self,
        prompt: str,
        image_path: Optional[str] = None,
        max_new_tokens: int = 512,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> Tuple[dict, dict]:
        return self._run(prompt, image_path, max_new_tokens)
