"""
radquant/worklist.py — JSON-persisted case store with prior-study linking.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
DEFAULT_STORE = Path("data/worklist.json")


class Worklist:
    def __init__(self, store_path: Path = DEFAULT_STORE) -> None:
        self.store_path = store_path
        self.cases: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if self.store_path.exists():
            try:
                with open(self.store_path) as f:
                    self.cases = json.load(f)
            except Exception as exc:
                logger.warning("worklist: could not load %s — %s", self.store_path, exc)
                self.cases = {}

    def _save(self) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.store_path, "w") as f:
            json.dump(self.cases, f, indent=2, default=str)

    def add_case(
        self,
        image_path: str,
        patient_id: str = "",
        study_date: str | None = None,
        dicom_metadata: dict | None = None,
    ) -> str:
        case_id = str(uuid.uuid4())[:8]
        self.cases[case_id] = {
            "case_id": case_id,
            "image_path": image_path,
            "patient_id": patient_id,
            "study_date": study_date or str(date.today()),
            "dicom_metadata": dicom_metadata or {},
            "findings": {},
            "urgency_score": 0.0,
            "urgency_tier": "Chronic",
            "status": "pending",
            "prior_image_path": None,
            "prior_study_date": None,
            "prior_findings": None,
        }
        self._save()
        return case_id

    def update_case(self, case_id: str, **kwargs: Any) -> None:
        if case_id not in self.cases:
            raise KeyError(f"Case {case_id!r} not found")
        self.cases[case_id].update(kwargs)
        self._save()

    def get_case(self, case_id: str) -> dict:
        if case_id not in self.cases:
            raise KeyError(f"Case {case_id!r} not found")
        return self.cases[case_id]

    def sorted_cases(self) -> list[dict]:
        return sorted(
            self.cases.values(),
            key=lambda c: c.get("urgency_score", 0.0),
            reverse=True,
        )

    def link_prior(self, case_id: str, prior_case_id: str) -> None:
        if case_id not in self.cases:
            raise KeyError(f"Case {case_id!r} not found")
        if prior_case_id not in self.cases:
            raise KeyError(f"Prior case {prior_case_id!r} not found")
        if case_id == prior_case_id:
            raise ValueError("A case cannot be linked to itself")
        prior = self.cases[prior_case_id]
        self.cases[case_id].update({
            "prior_image_path": prior["image_path"],
            "prior_study_date": prior.get("study_date"),
            "prior_findings": prior.get("findings") or None,
        })
        self._save()

    def unlink_prior(self, case_id: str) -> None:
        if case_id not in self.cases:
            raise KeyError(f"Case {case_id!r} not found")
        self.cases[case_id].update({
            "prior_image_path": None,
            "prior_study_date": None,
            "prior_findings": None,
        })
        self._save()

    def has_prior(self, case_id: str) -> bool:
        return bool(self.cases.get(case_id, {}).get("prior_image_path"))

    def get_same_patient_cases(self, patient_id: str, exclude: str | None = None) -> list[dict]:
        if not patient_id:
            return []
        results = [
            c for c in self.cases.values()
            if c.get("patient_id") == patient_id and c["case_id"] != exclude
        ]
        results.sort(key=lambda c: c.get("study_date") or "")
        return results

    def seed_demo(self, image_paths: list[str]) -> list[str]:
        """Add demo cases from a list of image paths. Returns list of case_ids."""
        ids = []
        for p in image_paths:
            ids.append(self.add_case(p, patient_id="DEMO", study_date=str(date.today())))
        return ids
