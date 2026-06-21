"""In-memory worklist store, persisted to JSON for session continuity.

A worklist is a set of cases keyed by ``case_id``, sortable by ``urgency_score``.
This is the data model behind the triage UI (Phase 3) and case workflow (Phase 7).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional

from radquant.config import DATA_DIR
from radquant.nodes.triage import top_findings, urgency_score

DEFAULT_PATH = DATA_DIR / "worklist.json"


@dataclass
class Case:
    case_id: str
    image_path: str
    findings: Dict[str, float] = field(default_factory=dict)
    urgency_score: float = 0.0
    status: str = "pending"   # pending | in_review | finalized

    def top(self, n: int = 3) -> List[tuple]:
        return top_findings(self.findings, n)


class Worklist:
    """A keyed collection of cases with urgency-sorted views and JSON persistence."""

    def __init__(self, path: Optional[Path | str] = None):
        self.path = Path(path) if path else DEFAULT_PATH
        self._cases: Dict[str, Case] = {}

    # ---- mutation ------------------------------------------------------- #
    def upsert(self, case: Case) -> Case:
        """Insert or replace a case by id."""
        self._cases[case.case_id] = case
        return case

    def add_from_findings(self, case_id: str, image_path: str,
                          findings: Dict[str, float], status: str = "pending") -> Case:
        """Build a case from classifier findings, computing its urgency score."""
        return self.upsert(Case(
            case_id=case_id,
            image_path=image_path,
            findings=findings,
            urgency_score=urgency_score(findings),
            status=status,
        ))

    def set_status(self, case_id: str, status: str) -> None:
        self._cases[case_id].status = status

    # ---- access --------------------------------------------------------- #
    def get(self, case_id: str) -> Optional[Case]:
        return self._cases.get(case_id)

    def __len__(self) -> int:
        return len(self._cases)

    def sorted(self, descending: bool = True) -> List[Case]:
        """Cases ordered by urgency score (highest first by default)."""
        return sorted(self._cases.values(), key=lambda c: c.urgency_score,
                      reverse=descending)

    # ---- persistence ---------------------------------------------------- #
    def save(self, path: Optional[Path | str] = None) -> Path:
        p = Path(path) if path else self.path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps([asdict(c) for c in self._cases.values()], indent=2))
        return p

    @classmethod
    def load(cls, path: Optional[Path | str] = None) -> "Worklist":
        wl = cls(path)
        if wl.path.exists():
            for row in json.loads(wl.path.read_text()):
                wl.upsert(Case(**row))
        return wl
