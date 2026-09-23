from datetime import date
from pathlib import Path

import json
import shutil

import pytest

from nvidia_research.repository import SnapshotRepository, SnapshotValidationError, validate_snapshot


FIXTURE = Path(__file__).parent / "fixtures" / "snapshot-valid"


def make_invalid_snapshot(tmp_path: Path, *, human_verified: bool) -> Path:
    snapshot_dir = tmp_path / "invalid-snapshot"
    shutil.copytree(FIXTURE, snapshot_dir)
    evidence_path = snapshot_dir / "evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence[0]["human_verified"] = human_verified
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    return snapshot_dir


def test_loads_a_valid_snapshot_and_filters_supplier_edges() -> None:
    repo = SnapshotRepository.from_directory(FIXTURE)

    results = repo.list_relationships(company_id="nvidia", relationship_type="supplier")

    assert results.total == 1
    assert results.items[0].from_company_id == "tsmc"
    assert results.items[0].confidence_score.total == 85


def test_rejects_a_confirmed_relationship_without_human_verified_evidence(tmp_path: Path) -> None:
    invalid_dir = make_invalid_snapshot(tmp_path, human_verified=False)

    with pytest.raises(SnapshotValidationError, match="human-verified evidence"):
        SnapshotRepository.from_directory(invalid_dir)


def test_validation_report_aggregates_score_input_cross_reference_errors(tmp_path: Path) -> None:
    invalid_dir = make_invalid_snapshot(tmp_path, human_verified=True)
    relationships_path = invalid_dir / "relationships.json"
    relationships = json.loads(relationships_path.read_text(encoding="utf-8"))
    relationships[0]["score_inputs"] = {
        "independent_publisher_count": 2,
        "latest_evidence_date": "2026-09-22",
    }
    relationships_path.write_text(json.dumps(relationships), encoding="utf-8")

    report = validate_snapshot(invalid_dir)

    assert report.is_valid is False
    assert "latest_evidence_date" in "\n".join(report.errors)
    assert "independent_publisher_count" in "\n".join(report.errors)


def test_search_companies_uses_stable_name_order_and_pagination() -> None:
    repo = SnapshotRepository.from_directory(FIXTURE)

    results = repo.search_companies(limit=2, offset=1)

    assert results.total == 5
    assert [company.id for company in results.items] == ["coreweave", "dell"]


def test_list_relationships_filters_by_direction_and_valid_date() -> None:
    repo = SnapshotRepository.from_directory(FIXTURE)

    inbound = repo.list_relationships(company_id="nvidia", direction="inbound", limit=100)
    current = repo.list_relationships(company_id="nvidia", valid_on=date(2026, 9, 23), limit=100)

    assert {item.id for item in inbound.items} == {
        "rel-coreweave-nvidia-customer",
        "rel-tsmc-nvidia-supplier",
    }
    assert "rel-amd-nvidia-peer" not in {item.id for item in current.items}


def test_getters_return_traceable_detail_or_none() -> None:
    repo = SnapshotRepository.from_directory(FIXTURE)

    relationship = repo.get_relationship("rel-tsmc-nvidia-supplier")
    evidence = repo.get_evidence("ev-tsmc")

    assert relationship is not None
    assert str(relationship.evidence[0].source.url) == "https://research.example.test/tsmc-filing"
    assert evidence is not None
    assert evidence.human_verified is True
    assert repo.get_relationship("missing") is None
    assert repo.get_evidence("missing") is None


def test_network_respects_depth_and_returns_nodes_and_edges() -> None:
    repo = SnapshotRepository.from_directory(FIXTURE)

    result = repo.network(company_id="nvidia", depth=1, min_confidence=0)

    assert {node.id for node in result.nodes} >= {"nvidia", "tsmc"}
    assert all("nvidia" in {edge.from_company_id, edge.to_company_id} for edge in result.edges)


def test_invalid_page_bounds_raise_value_error() -> None:
    repo = SnapshotRepository.from_directory(FIXTURE)

    with pytest.raises(ValueError, match="limit"):
        repo.list_relationships(company_id="nvidia", limit=101)
