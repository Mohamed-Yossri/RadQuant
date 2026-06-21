"""Chest X-ray pathology classifier (TorchXRayVision DenseNet-121).

Derived verbatim from MedRAX `medrax/tools/classification.py` (Apache-2.0).
See radquant/foundation/NOTICE.md for attribution.
"""

from typing import Dict, Optional, Tuple, Type
from pydantic import BaseModel, Field

import skimage.io
import torch
import torchvision
import torchxrayvision as xrv

from langchain_core.callbacks import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain_core.tools import BaseTool


class ChestXRayInput(BaseModel):
    """Input for chest X-ray analysis tools. Only supports JPG or PNG images."""

    image_path: str = Field(
        ..., description="Path to the radiology image file, only supports JPG or PNG images"
    )


class ChestXRayClassifierTool(BaseTool):
    """Tool that classifies chest X-ray images for multiple pathologies.

    This tool uses a pre-trained DenseNet model to analyze chest X-ray images and
    predict the likelihood of various pathologies. The model can classify the following 18 conditions:

    Atelectasis, Cardiomegaly, Consolidation, Edema, Effusion, Emphysema,
    Enlarged Cardiomediastinum, Fibrosis, Fracture, Hernia, Infiltration,
    Lung Lesion, Lung Opacity, Mass, Nodule, Pleural Thickening, Pneumonia, Pneumothorax

    The output values represent the probability (from 0 to 1) of each condition being present in the image.
    A higher value indicates a higher likelihood of the condition being present.
    """

    name: str = "chest_xray_classifier"
    description: str = (
        "A tool that analyzes chest X-ray images and classifies them for 18 different pathologies. "
        "Input should be the path to a chest X-ray image file. "
        "Output is a dictionary of pathologies and their predicted probabilities (0 to 1). "
        "Pathologies include: Atelectasis, Cardiomegaly, Consolidation, Edema, Effusion, Emphysema, "
        "Enlarged Cardiomediastinum, Fibrosis, Fracture, Hernia, Infiltration, Lung Lesion, "
        "Lung Opacity, Mass, Nodule, Pleural Thickening, Pneumonia, and Pneumothorax. "
        "Higher values indicate a higher likelihood of the condition being present."
    )
    args_schema: Type[BaseModel] = ChestXRayInput
    model: xrv.models.DenseNet = None
    device: Optional[str] = "cuda"
    transform: torchvision.transforms.Compose = None

    def __init__(self, model_name: str = "densenet121-res224-all", device: Optional[str] = "cuda"):
        super().__init__()
        self.model = xrv.models.DenseNet(weights=model_name)
        self.model.eval()
        self.device = torch.device(device) if device else "cuda"
        self.model = self.model.to(self.device)
        self.transform = torchvision.transforms.Compose([xrv.datasets.XRayCenterCrop()])

    def _process_image(self, image_path: str) -> torch.Tensor:
        """Load, normalize and transform a CXR into a model-ready tensor."""
        img = skimage.io.imread(image_path)
        img = xrv.datasets.normalize(img, 255)

        if len(img.shape) > 2:
            img = img[:, :, 0]

        img = img[None, :, :]
        img = self.transform(img)
        img = torch.from_numpy(img).unsqueeze(0)
        img = img.to(self.device)
        return img

    def _run(
        self,
        image_path: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> Tuple[Dict[str, float], Dict]:
        """Classify the chest X-ray image for multiple pathologies."""
        try:
            img = self._process_image(image_path)

            with torch.inference_mode():
                preds = self.model(img).cpu()[0]

            output = dict(zip(xrv.datasets.default_pathologies, preds.numpy()))
            metadata = {
                "image_path": image_path,
                "analysis_status": "completed",
                "note": "Probabilities range from 0 to 1, with higher values indicating higher likelihood of the condition.",
            }
            return output, metadata
        except Exception as e:
            return {"error": str(e)}, {
                "image_path": image_path,
                "analysis_status": "failed",
            }

    async def _arun(
        self,
        image_path: str,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> Tuple[Dict[str, float], Dict]:
        """Async wrapper around the synchronous classifier."""
        return self._run(image_path)
