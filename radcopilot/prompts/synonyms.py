"""Pathology synonym map for omission QC (Phase 5).

Maps each TorchXRayVision pathology key to phrasings a radiologist might use, so
the QC node does not flag a finding as "omitted" just because the report worded
it differently (e.g. effusion -> "blunting of the costophrenic angle").

Keys are the exact xrv default_pathologies strings.
"""

from __future__ import annotations

from typing import Dict, List

SYNONYMS: Dict[str, List[str]] = {
    "Pneumothorax": ["pneumothorax", "collapsed lung", "pleural air", "ptx"],
    "Pneumonia": ["pneumonia", "pneumonic", "airspace infection", "infectious consolidation"],
    "Effusion": ["effusion", "pleural fluid", "fluid in the pleural space",
                 "blunting of the costophrenic angle", "costophrenic angle blunting",
                 "blunted costophrenic", "blunting of the right costophrenic angle",
                 "blunting of the left costophrenic angle"],
    "Consolidation": ["consolidation", "airspace opacity", "airspace disease", "consolidative"],
    "Edema": ["edema", "oedema", "pulmonary congestion", "vascular congestion",
              "interstitial fluid", "pulmonary edema"],
    "Lung Lesion": ["lung lesion", "pulmonary lesion", "focal lesion"],
    "Mass": ["mass", "neoplasm", "tumor", "tumour"],
    "Cardiomegaly": ["cardiomegaly", "enlarged heart", "enlarged cardiac silhouette",
                     "increased cardiac size", "cardiac enlargement", "enlarged cardiac"],
    "Nodule": ["nodule", "nodular opacity", "pulmonary nodule", "nodular"],
    "Infiltration": ["infiltrate", "infiltration", "interstitial markings",
                     "interstitial opacities"],
    "Lung Opacity": ["opacity", "opacification", "hazy opacity", "increased opacity"],
    "Fracture": ["fracture", "rib fracture", "osseous injury", "broken rib", "fractured"],
    "Enlarged Cardiomediastinum": ["enlarged cardiomediastinum", "widened mediastinum",
                                   "mediastinal widening", "mediastinal enlargement"],
    "Pleural_Thickening": ["pleural thickening", "thickened pleura", "pleural scarring"],
    "Atelectasis": ["atelectasis", "atelectatic", "volume loss", "subsegmental atelectasis"],
    "Emphysema": ["emphysema", "hyperinflation", "hyperinflated", "bullae", "bullous"],
    "Fibrosis": ["fibrosis", "fibrotic", "scarring", "reticular opacities"],
    "Hernia": ["hernia", "hiatal hernia", "diaphragmatic hernia"],
}


def synonyms_for(pathology: str) -> List[str]:
    """Synonyms for a pathology (falls back to its lowercased name)."""
    return SYNONYMS.get(pathology, [pathology.replace("_", " ").lower()])
