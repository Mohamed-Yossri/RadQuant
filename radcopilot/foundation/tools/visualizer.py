"""Image visualizer tool.

Derived from MedRAX `medrax/tools/utils.py` (Apache-2.0). matplotlib is imported
lazily (inside the display helper) so the tool can be constructed in headless /
Streamlit contexts without pulling in a GUI backend. See NOTICE.md.
"""

from typing import Optional, Type, Dict, Tuple
from pathlib import Path
from pydantic import BaseModel, Field

from langchain_core.callbacks import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain_core.tools import BaseTool


class ImageVisualizerInput(BaseModel):
    """Input schema for the Image Visualizer Tool. Only supports JPG or PNG images."""

    image_path: str = Field(
        ..., description="Path to the image file to display, only supports JPG or PNG images"
    )
    title: Optional[str] = Field(None, description="Optional title to display above the image")
    description: Optional[str] = Field(
        None, description="Optional description to display below the image"
    )
    figsize: Optional[tuple] = Field(
        (10, 10), description="Optional figure size as (width, height) in inches"
    )
    cmap: Optional[str] = Field(
        "rgb", description="Optional colormap to use for displaying the image"
    )


class ImageVisualizerTool(BaseTool):
    """Tool for displaying medical images to users with annotations."""

    name: str = "image_visualizer"
    description: str = (
        "Displays images to users with optional titles and descriptions. "
        "Input: Path to image file and optional display parameters. "
        "Output: Dict with image path and metadata."
    )
    args_schema: Type[BaseModel] = ImageVisualizerInput

    def _display_image(
        self,
        image_path: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        figsize: tuple = (10, 10),
        cmap: str = "rgb",
    ) -> None:
        """Display an image with optional annotations (matplotlib, lazy-imported)."""
        import matplotlib.pyplot as plt
        import skimage.io

        plt.figure(figsize=figsize)
        img = skimage.io.imread(image_path)
        if len(img.shape) > 2 and cmap != "rgb":
            img = img[..., 0]

        plt.imshow(img, cmap=None if cmap == "rgb" else cmap)
        plt.axis("off")
        if title:
            plt.title(title, pad=15, fontsize=12)
        if description:
            plt.figtext(
                0.5, 0.01, description, wrap=True, horizontalalignment="center", fontsize=10
            )
        plt.subplots_adjust(top=0.95, bottom=0.05, left=0.05, right=0.95)
        plt.show()

    def _run(
        self,
        image_path: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        figsize: tuple = (10, 10),
        cmap: str = "rgb",
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> Tuple[Dict[str, str], Dict]:
        """Verify an image path and return it as metadata.

        The actual on-screen display is disabled by default (RadQuant renders
        images in the Streamlit UI, not via matplotlib); call ``_display_image``
        explicitly if a matplotlib render is wanted.
        """
        try:
            if not Path(image_path).is_file():
                raise FileNotFoundError(f"Image file not found: {image_path}")

            output = {"image_path": image_path}
            metadata = {
                "image_path": image_path,
                "title": bool(title),
                "description": bool(description),
                "figsize": figsize,
                "cmap": cmap,
                "analysis_status": "completed",
            }
            return output, metadata

        except Exception as e:
            return (
                {"error": str(e)},
                {
                    "image_path": image_path,
                    "visualization_status": "failed",
                    "note": "An error occurred during image visualization",
                },
            )

    async def _arun(
        self,
        image_path: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        figsize: tuple = (10, 10),
        cmap: str = "rgb",
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> Tuple[Dict[str, str], Dict]:
        """Async version of _run."""
        return self._run(image_path, title, description, figsize, cmap)
