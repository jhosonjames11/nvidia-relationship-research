from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nvidia_research.api import create_app
from nvidia_research.repository import SnapshotRepository


def test_default_app_loads_the_committed_default_snapshot(monkeypatch) -> None:
    monkeypatch.delenv("NVIDIA_RESEARCH_SNAPSHOT_PATH", raising=False)
    from nvidia_research.api import create_default_app

    client = TestClient(create_default_app())
    assert client.get("/health").json()["meta"]["snapshot_id"] == "nvidia-2026-09-23"


def test_default_app_prefers_the_snapshot_path_environment_variable(
    monkeypatch, fixture_snapshot_path: Path
) -> None:
    monkeypatch.setenv("NVIDIA_RESEARCH_SNAPSHOT_PATH", str(fixture_snapshot_path))
    from nvidia_research.api import create_default_app

    client = TestClient(create_default_app())
    assert client.get("/health").json()["meta"]["snapshot_id"] == "fixture-2026-09-23"


@pytest.fixture
def fixture_snapshot_path() -> Path:
    return Path(__file__).parent / "fixtures" / "snapshot-valid"


@pytest.fixture
def client(fixture_snapshot_path: Path) -> TestClient:
    repository = SnapshotRepository.from_directory(fixture_snapshot_path)
    return TestClient(create_app(repository))


def test_health_reports_snapshot_metadata_and_record_counts(client: TestClient) -> None:
    """Removing the loaded snapshot summary from health must break this contract."""

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "meta": {
            "snapshot_id": "fixture-2026-09-23",
            "as_of": "2026-09-23",
            "methodology_version": "fixture-1.0",
        },
        "data": {
            "status": "ok",
            "counts": {
                "companies": 5,
                "relationships": 4,
                "evidence": 4,
                "sources": 4,
            },
        },
    }


def test_companies_support_search_filters_and_paginated_metadata(client: TestClient) -> None:
    """Dropping a company query filter or pagination envelope must break this contract."""

    response = client.get(
        "/v1/companies",
        params={"query": "fictional", "ticker": "TSM", "exchange": "xtest", "limit": 1},
    )

    assert response.status_code == 200
    assert response.json() == {
        "meta": {
            "snapshot_id": "fixture-2026-09-23",
            "as_of": "2026-09-23",
            "methodology_version": "fixture-1.0",
            "limit": 1,
            "offset": 0,
            "total": 1,
        },
        "data": [
            {
                "id": "tsmc",
                "legal_name": "TSMC Fictional Corporation",
                "ticker": "TSM",
                "exchange": "XTEST",
                "country_or_region": "Testland",
                "aliases": ["TSMC Fixture"],
            }
        ],
    }


def test_relationships_apply_filters_and_keep_page_metadata(client: TestClient) -> None:
    """Ignoring relationship filters or their pagination results must break this contract."""

    response = client.get(
        "/v1/relationships",
        params={
            "company_id": "nvidia",
            "relationship_type": "supplier",
            "status": "confirmed",
            "as_of": "2026-09-23",
            "min_confidence": 85,
            "limit": 1,
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["meta"] == {
        "snapshot_id": "fixture-2026-09-23",
        "as_of": "2026-09-23",
        "methodology_version": "fixture-1.0",
        "limit": 1,
        "offset": 0,
        "total": 1,
    }
    assert [relationship["id"] for relationship in body["data"]] == [
        "rel-tsmc-nvidia-supplier"
    ]


def test_relationship_detail_contains_score_and_evidence(client: TestClient) -> None:
    """Omitting the cached score or traceable evidence must break this contract."""

    response = client.get("/v1/relationships/rel-tsmc-nvidia-supplier")

    body = response.json()
    assert response.status_code == 200
    assert body["meta"]["snapshot_id"] == "fixture-2026-09-23"
    assert body["data"]["confidence_score"]["total"] == 85
    assert body["data"]["evidence"][0]["locator"] == "Fictional page 1"
    assert body["data"]["evidence"][0]["source"]["id"] == "src-tsmc"


@pytest.mark.parametrize(
    ("path", "params"),
    [
        ("/v1/relationships", {"limit": 101}),
        ("/v1/relationships", {"relationship_type": "not-a-type"}),
        ("/v1/relationships", {"as_of": "not-a-date"}),
        ("/v1/relationships", {"direction": "inbound"}),
        ("/v1/network/nvidia", {"depth": 3}),
    ],
)
def test_invalid_queries_return_json_400(
    client: TestClient, path: str, params: dict[str, object]
) -> None:
    """Returning FastAPI's 422 or allowing invalid repository filters must break this contract."""

    response = client.get(path, params=params)

    assert response.status_code == 400
    assert isinstance(response.json()["detail"], str)


def test_missing_resource_ids_return_json_404(client: TestClient) -> None:
    """Letting missing repository entities become successful empty results must break this contract."""

    responses = [
        client.get("/v1/relationships/missing-relationship"),
        client.get("/v1/evidence/missing-evidence"),
        client.get("/v1/network/missing-company"),
    ]

    assert [response.status_code for response in responses] == [404, 404, 404]
    assert all(isinstance(response.json()["detail"], str) for response in responses)


def test_network_returns_filtered_nodes_and_edges(client: TestClient) -> None:
    """Failing to expose a network result from the repository must break this contract."""

    response = client.get(
        "/v1/network/nvidia",
        params={"depth": 1, "relationship_type": "supplier", "min_confidence": 85},
    )

    assert response.status_code == 200
    assert {node["id"] for node in response.json()["data"]["nodes"]} == {"nvidia", "tsmc"}
    assert [edge["id"] for edge in response.json()["data"]["edges"]] == [
        "rel-tsmc-nvidia-supplier"
    ]


def test_evidence_detail_exposes_source_metadata(client: TestClient) -> None:
    """Stripping evidence source metadata must break this traceability contract."""

    response = client.get("/v1/evidence/ev-tsmc")

    assert response.status_code == 200
    assert response.json()["data"]["source"]["url"] == "https://research.example.test/tsmc-filing"
