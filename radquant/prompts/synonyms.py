"""radquant/prompts/synonyms.py — 18-pathology synonym map for omission QC."""

SYNONYMS: dict[str, list[str]] = {
    "Atelectasis": ["atelectasis", "subsegmental atelectasis", "linear atelectasis", "plate-like atelectasis", "basilar atelectasis"],
    "Cardiomegaly": ["cardiomegaly", "enlarged heart", "cardiac enlargement", "increased cardiac silhouette", "CTR"],
    "Effusion": ["effusion", "pleural effusion", "pleural fluid", "blunting of the costophrenic angle", "costophrenic blunting", "layering fluid"],
    "Infiltration": ["infiltration", "infiltrate", "interstitial infiltrate", "airspace infiltrate"],
    "Mass": ["mass", "lung mass", "pulmonary mass", "soft tissue mass"],
    "Nodule": ["nodule", "pulmonary nodule", "lung nodule", "solitary nodule"],
    "Pneumonia": ["pneumonia", "lobar pneumonia", "consolidation", "airspace consolidation", "airspace disease"],
    "Pneumothorax": ["pneumothorax", "ptx", "pneumo", "free air", "pleural air", "collapsed lung"],
    "Consolidation": ["consolidation", "lobar consolidation", "airspace consolidation", "airspace opacification"],
    "Edema": ["edema", "pulmonary edema", "vascular congestion", "interstitial edema", "alveolar edema", "fluid overload"],
    "Emphysema": ["emphysema", "hyperinflation", "hyperlucency", "barrel chest", "flattened diaphragm"],
    "Fibrosis": ["fibrosis", "pulmonary fibrosis", "interstitial fibrosis", "reticular opacities", "honeycombing"],
    "Pleural_Thickening": ["pleural thickening", "pleural calcification", "pleural scarring"],
    "Hernia": ["hernia", "hiatal hernia", "diaphragmatic hernia", "bowel loops in chest"],
    "Lung_Lesion": ["lesion", "lung lesion", "pulmonary lesion"],
    "Lung_Opacity": ["opacity", "lung opacity", "pulmonary opacity", "airspace opacity", "ground-glass opacity", "GGO"],
    "Fracture": ["fracture", "rib fracture", "clavicle fracture", "broken rib"],
    "Enlarged_Cardiomediastinum": ["widened mediastinum", "mediastinal widening", "enlarged mediastinum", "cardiomediastinal silhouette"],
}
