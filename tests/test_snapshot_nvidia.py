from pathlib import Path

from nvidia_research.repository import SnapshotRepository


SNAPSHOT = Path("data/snapshots/nvidia-2026-09-23")


def test_nvidia_snapshot_loads_and_covers_required_relationship_types() -> None:
    repo = SnapshotRepository.from_directory(SNAPSHOT)
    assert repo.manifest.research_subject_company_id == "nvidia"
    confirmed_types = {
        item.relationship_type.value
        for item in repo.list_relationships(company_id="nvidia", status="confirmed", limit=100).items
    }
    assert {"supplier", "customer", "partner", "investor_or_investee", "peer"} <= confirmed_types


def test_every_confirmed_nvidia_relation_has_traceable_evidence() -> None:
    repo = SnapshotRepository.from_directory(SNAPSHOT)
    for detail in repo.list_relationships(company_id="nvidia", status="confirmed", limit=100).items:
        assert detail.evidence
        for evidence in detail.evidence:
            assert evidence.human_verified is True
            assert evidence.locator
            assert str(evidence.source.url).startswith("https://")
