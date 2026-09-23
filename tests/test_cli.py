import json
import shutil
from pathlib import Path

import pytest

from nvidia_research.cli import main


@pytest.fixture
def fixture_snapshot_path() -> Path:
    return Path(__file__).parent / "fixtures" / "snapshot-valid"


@pytest.fixture
def invalid_snapshot_path(tmp_path: Path, fixture_snapshot_path: Path) -> Path:
    snapshot_path = tmp_path / "invalid-snapshot"
    shutil.copytree(fixture_snapshot_path, snapshot_path)
    evidence_path = snapshot_path / "evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence[0]["human_verified"] = False
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    return snapshot_path


def test_relationships_command_outputs_the_same_snapshot_metadata(
    fixture_snapshot_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Dropping repository relationship output or its metadata must break this contract."""
    exit_code = main([
        "--snapshot", str(fixture_snapshot_path),
        "relationships", "--company", "nvidia", "--type", "supplier",
    ])
    body = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert body["meta"]["snapshot_id"] == "fixture-2026-09-23"
    assert body["data"][0]["id"] == "rel-tsmc-nvidia-supplier"


def test_validate_returns_one_for_an_invalid_snapshot(
    invalid_snapshot_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Treating an invalid snapshot as valid must break this command result."""
    assert main(["--snapshot", str(invalid_snapshot_path), "validate"]) == 1
    body = json.loads(capsys.readouterr().out)
    assert body["valid"] is False
    assert "human-verified evidence" in "\n".join(body["errors"])


def test_companies_command_applies_all_filters_and_page_metadata(
    fixture_snapshot_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Ignoring any company filter or pagination metadata must break this contract."""
    exit_code = main([
        "--snapshot", str(fixture_snapshot_path), "companies",
        "--query", "fictional", "--ticker", "TSM", "--exchange", "xtest", "--limit", "1",
    ])
    body = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert body["meta"] == {
        "snapshot_id": "fixture-2026-09-23", "as_of": "2026-09-23",
        "methodology_version": "fixture-1.0", "limit": 1, "offset": 0, "total": 1,
    }
    assert [company["id"] for company in body["data"]] == ["tsmc"]


def test_companies_filters_before_paging_the_complete_repository_result(
    tmp_path: Path, fixture_snapshot_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Limiting the repository query before ticker filtering must not hide later matches."""
    snapshot_path = tmp_path / "large-snapshot"
    shutil.copytree(fixture_snapshot_path, snapshot_path)
    companies_path = snapshot_path / "companies.json"
    companies = json.loads(companies_path.read_text(encoding="utf-8"))
    companies.extend(
        {
            "id": f"extra-company-{index:03d}",
            "legal_name": f"ZZZ Fixture Company {index:03d}",
            "ticker": "MATCH" if index == 100 else f"X{index:03d}",
            "exchange": "XTEST",
            "country_or_region": "Testland",
            "aliases": [],
        }
        for index in range(101)
    )
    companies_path.write_text(json.dumps(companies), encoding="utf-8")

    assert main(["--snapshot", str(snapshot_path), "companies", "--ticker", "MATCH"]) == 0
    body = json.loads(capsys.readouterr().out)
    assert body["meta"]["total"] == 1
    assert [company["id"] for company in body["data"]] == ["extra-company-100"]


def test_network_and_relationship_detail_use_repository_results(
    fixture_snapshot_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Replacing detailed and network repository reads with empty data must break this contract."""
    relationship_exit_code = main([
        "--snapshot", str(fixture_snapshot_path), "relationship", "rel-tsmc-nvidia-supplier",
    ])
    relationship_body = json.loads(capsys.readouterr().out)
    network_exit_code = main([
        "--snapshot", str(fixture_snapshot_path), "network", "nvidia", "--depth", "1",
        "--type", "supplier", "--min-confidence", "85",
    ])
    network_body = json.loads(capsys.readouterr().out)
    assert relationship_exit_code == network_exit_code == 0
    assert relationship_body["data"]["confidence_score"]["total"] == 85
    assert {node["id"] for node in network_body["data"]["nodes"]} == {"nvidia", "tsmc"}
    assert [edge["id"] for edge in network_body["data"]["edges"]] == [
        "rel-tsmc-nvidia-supplier"
    ]


def test_network_as_of_filters_expired_fixture_edges(
    fixture_snapshot_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Dropping the network valid-on argument must retain the expired AMD fixture edge."""

    exit_code = main([
        "--snapshot", str(fixture_snapshot_path), "network", "nvidia", "--as-of", "2026-09-23",
    ])

    body = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert "rel-amd-nvidia-peer" not in {edge["id"] for edge in body["data"]["edges"]}
    assert {edge["id"] for edge in body["data"]["edges"]} == {
        "rel-tsmc-nvidia-supplier",
        "rel-coreweave-nvidia-customer",
        "rel-nvidia-dell-customer",
    }


def test_missing_relationship_returns_a_json_runtime_error(
    fixture_snapshot_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Formatting a missing relationship error differently from API semantics must break this contract."""
    assert main(["--snapshot", str(fixture_snapshot_path), "relationship", "missing"]) == 1
    assert json.loads(capsys.readouterr().out) == {
        "detail": "relationship 'missing' was not found"
    }


def test_snapshot_environment_default_is_used_when_no_option_is_given(
    fixture_snapshot_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Ignoring the snapshot environment default must break an option-free query."""
    monkeypatch.setenv("NVIDIA_RESEARCH_SNAPSHOT_PATH", str(fixture_snapshot_path))
    assert main(["relationships", "--company", "nvidia", "--direction", "either"]) == 0
    body = json.loads(capsys.readouterr().out)
    assert body["meta"]["snapshot_id"] == "fixture-2026-09-23"
    assert len(body["data"]) == 4


def test_parser_errors_return_two() -> None:
    """Accepting malformed command arguments must break the parser exit contract."""
    assert main(["relationships", "--limit", "not-an-integer"]) == 2
