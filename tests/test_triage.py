"""Phase 3 unit tests: tier coverage, urgency scoring, worklist sort + persistence.

Fast and deterministic — uses synthetic findings, no model load.
"""

from radquant.nodes.triage import (
    WEIGHTS, urgency_score, tier_of, validate_coverage,
)
from radquant.worklist import Case, Worklist


def test_tier_map_covers_all_18_pathologies():
    validate_coverage()
    assert len(WEIGHTS) == 18


def test_critical_outranks_chronic():
    critical = {"Pneumothorax": 0.9}          # weight 1.0
    chronic = {"Emphysema": 0.9}              # weight 0.2
    assert urgency_score(critical) > urgency_score(chronic)
    assert tier_of("Pneumothorax") == "Critical"
    assert tier_of("Emphysema") == "Chronic"


def test_unknown_pathology_contributes_zero():
    assert urgency_score({"NotAPathology": 1.0}) == 0.0


def test_pneumothorax_surfaces_in_top_quartile():
    """A pneumothorax>0.5 case must land in the top quartile of a 20-case list."""
    wl = Worklist(path="/tmp/_wl_test.json")
    # 19 low-urgency chronic cases + 1 pneumothorax case
    for i in range(19):
        wl.add_from_findings(f"low-{i}", f"/img/{i}.png",
                             {"Atelectasis": 0.10, "Emphysema": 0.08})
    wl.add_from_findings("PTX", "/img/ptx.png", {"Pneumothorax": 0.8})

    ranked = wl.sorted(descending=True)
    top_quartile = ranked[: max(1, len(ranked) // 4)]
    assert "PTX" in [c.case_id for c in top_quartile]
    assert ranked[0].case_id == "PTX"


def test_json_round_trip(tmp_path):
    p = tmp_path / "wl.json"
    wl = Worklist(path=p)
    wl.add_from_findings("c1", "/a.png", {"Pneumonia": 0.7, "Effusion": 0.4})
    wl.set_status("c1", "finalized")
    wl.save()

    loaded = Worklist.load(p)
    assert len(loaded) == 1
    c = loaded.get("c1")
    assert c.status == "finalized"
    assert abs(c.urgency_score - wl.get("c1").urgency_score) < 1e-9
