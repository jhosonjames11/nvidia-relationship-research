# NVIDIA Relationship Research Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an offline-runnable FastAPI and CLI service that serves manually verified, evidence-backed NVIDIA relationships with listed companies from versioned local JSON snapshots.

**Architecture:** A Pydantic model layer validates one immutable snapshot at startup. A repository layer cross-validates and indexes JSON records, then exposes shared query methods to a deterministic scoring module, FastAPI routes, and an `argparse` CLI. The application makes no network requests at runtime; source URLs and precise evidence locators are stored in the snapshot for auditability.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, Uvicorn, standard-library `argparse`, pytest, HTTPX/FastAPI TestClient.

**Spec:** `docs/superpowers/specs/2026-09-23-nvidia-relationship-research-design.md`

## Global Constraints

- Research subject: NVIDIA Corporation, canonical company ID `nvidia`.
- The service is read-only and must run and test without network access.
- Store only manually verified, legally accessible public-source metadata and short necessary excerpts; do not scrape, automate browsing, bypass restrictions, or include personal/private data.
- Each relationship has a type, endpoint roles, directionality, conclusion status, evidence IDs, timing fields, and a deterministically calculated 0–100 confidence score.
- Allowed relationship types are exactly `supplier`, `customer`, `partner`, `investor_or_investee`, and `peer`.
- Allowed conclusion statuses are exactly `confirmed`, `inferred`, and `unknown`; a confirmed record needs at least one human-verified evidence record.
- API and CLI results include snapshot identity and as-of date; scores are evidence-support scores, never investment advice.
- The committed snapshot is immutable. A data update creates a new snapshot directory rather than overwriting an existing one.

---

## File Structure

| Path | Responsibility |
|---|---|
| `pyproject.toml` | Package metadata, runtime/dev dependencies, console script, pytest configuration. |
| `src/nvidia_research/models.py` | Pydantic enums and schemas for all snapshot records and API-independent result types. |
| `src/nvidia_research/scoring.py` | Pure confidence-score calculation and score-explanation generation. |
| `src/nvidia_research/repository.py` | Snapshot loading, cross-reference validation, in-memory indexes, search and graph queries. |
| `src/nvidia_research/api.py` | FastAPI application factory and read-only HTTP route mapping. |
| `src/nvidia_research/cli.py` | `argparse` commands and JSON output over the shared repository. |
| `data/snapshots/nvidia-2026-09-23/*.json` | First audited NVIDIA research snapshot. |
| `tests/fixtures/snapshot-valid/*.json` | Small fictional but schema-valid fixture used by deterministic tests. |
| Temporary `tmp_path` snapshots in tests | Copies of the valid fixture modified in one field to assert validation failures. |
| `tests/test_models.py` | Model parsing and invariant tests. |
| `tests/test_scoring.py` | Exact score and threshold tests. |
| `tests/test_repository.py` | Loading, validation, filtering, paging, and graph-query tests. |
| `tests/test_api.py` | HTTP status, response-shape, and query behavior tests. |
| `tests/test_cli.py` | CLI JSON output and validation exit-code tests. |
| `README.md` | Install, run, query, test, snapshot selection, and scope instructions. |
| `docs/research-methodology.md` | Evidence policy, entity rules, conclusion states, relationship semantics, and scoring. |
| `docs/data-update-guide.md` | Manual, lawful process for curating a subsequent immutable snapshot. |
| `docs/ai-and-human-review.md` | AI-assisted work disclosure and required human review steps. |

## Task 1: Create the Python package and executable shell

**Files:**

- Create: `pyproject.toml`
- Create: `src/nvidia_research/__init__.py`
- Create: `src/nvidia_research/__main__.py`
- Create: `src/nvidia_research/cli.py`
- Create: `tests/test_package.py`
- Create: `.gitignore`

**Interfaces:**

- Produces `nvidia_research.__version__: str` and `nvidia_research.cli.main(argv: Sequence[str] | None = None) -> int`.
- Produces console command `nvidia-research` that delegates to `main()`.
- Later tasks import `__version__` for the health response and use `main()` for CLI tests.

- [ ] **Step 1: Write the failing package and command test**

```python
# tests/test_package.py
from nvidia_research import __version__
from nvidia_research.cli import main


def test_package_exports_a_nonempty_version() -> None:
    assert __version__ == "0.1.0"


def test_cli_help_exits_successfully(capsys) -> None:
    assert main(["--help"]) == 0
    assert "NVIDIA relationship research" in capsys.readouterr().out
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_package.py -q`

Expected: FAIL during collection because `nvidia_research` does not exist.

- [ ] **Step 3: Add package configuration and minimal command implementation**

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "nvidia-relationship-research"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115,<1",
  "pydantic>=2.8,<3",
  "uvicorn>=0.30,<1",
]

[project.optional-dependencies]
dev = ["httpx>=0.27,<1", "pytest>=8,<9"]

[project.scripts]
nvidia-research = "nvidia_research.cli:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra"
```

```python
# src/nvidia_research/__init__.py
__version__ = "0.1.0"
```

```python
# src/nvidia_research/cli.py
from __future__ import annotations

import argparse
from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NVIDIA relationship research")
    try:
        parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)
    return 0
```

```python
# src/nvidia_research/__main__.py
from nvidia_research.cli import main

raise SystemExit(main())
```

Add `.gitignore` entries for `.venv/`, `__pycache__/`, `.pytest_cache/`, `.coverage`, and `*.egg-info/`.

- [ ] **Step 4: Install editable dependencies and run the package test**

Run: `python -m pip install -e '.[dev]' && python -m pytest tests/test_package.py -q`

Expected: PASS with two tests.

- [ ] **Step 5: Commit the package shell**

```bash
git add pyproject.toml .gitignore src/nvidia_research tests/test_package.py
git commit -m "chore: scaffold NVIDIA research package"
```

## Task 2: Define and validate immutable snapshot contracts

**Files:**

- Create: `src/nvidia_research/models.py`
- Create: `tests/test_models.py`

**Interfaces:**

- Consumes the package from Task 1.
- Produces `SnapshotManifest`, `Company`, `Source`, `Evidence`, `Relationship`, `ScoreInputs`, `RelationshipType`, `RelationshipStatus`, `SourceTier`, `Directness`, and `Directionality` Pydantic models.
- Later tasks consume `Relationship`, `Evidence`, `Source`, and `SnapshotManifest` without parsing raw dictionaries themselves.

- [ ] **Step 1: Write failing schema tests for valid records and invalid invariants**

```python
# tests/test_models.py
from datetime import date

import pytest
from pydantic import ValidationError

from nvidia_research.models import Company, Relationship, RelationshipType


def test_company_requires_a_slug_id_and_exchange_ticker() -> None:
    company = Company(
        id="nvidia",
        legal_name="NVIDIA Corporation",
        ticker="NVDA",
        exchange="NASDAQ",
        country_or_region="US",
        aliases=["NVIDIA"],
    )
    assert company.id == "nvidia"

    with pytest.raises(ValidationError):
        Company(
            id="NVIDIA Corporation",
            legal_name="NVIDIA Corporation",
            ticker="NVDA",
            exchange="NASDAQ",
            country_or_region="US",
            aliases=[],
        )


def test_supplier_relationship_requires_supplier_and_buyer_roles() -> None:
    relationship = Relationship(
        id="rel-tsmc-nvidia-supplier",
        from_company_id="tsmc",
        to_company_id="nvidia",
        relationship_type=RelationshipType.SUPPLIER,
        from_role="supplier",
        to_role="buyer",
        directionality="directed",
        status="confirmed",
        summary="TSMC supplies manufacturing services to NVIDIA.",
        event_or_business_context="GPU manufacturing",
        valid_from=date(2025, 1, 1),
        valid_to=None,
        evidence_ids=["ev-tsmc"],
        score_inputs={"independent_publisher_count": 1, "latest_evidence_date": date(2025, 1, 15)},
    )
    assert relationship.relationship_type is RelationshipType.SUPPLIER

    with pytest.raises(ValidationError):
        Relationship(
            id="rel-tsmc-nvidia-supplier",
            from_company_id="tsmc",
            to_company_id="nvidia",
            relationship_type=RelationshipType.SUPPLIER,
            from_role="supplier",
            to_role="investee",
            directionality="directed",
            status="confirmed",
            summary="TSMC supplies manufacturing services to NVIDIA.",
            event_or_business_context="GPU manufacturing",
            valid_from=date(2025, 1, 1),
            valid_to=None,
            evidence_ids=["ev-tsmc"],
            score_inputs={"independent_publisher_count": 1, "latest_evidence_date": date(2025, 1, 15)},
        )
```

- [ ] **Step 2: Run the model tests to verify they fail**

Run: `python -m pytest tests/test_models.py -q`

Expected: FAIL during collection because `nvidia_research.models` does not exist.

- [ ] **Step 3: Implement precise models and relationship-role validation**

Use `str, Enum` classes for all fixed vocabularies. Define the exact role map below and call it from a Pydantic `model_validator(mode="after")` on `Relationship`:

```python
ROLE_PAIRS = {
    RelationshipType.SUPPLIER: ("supplier", "buyer", Directionality.DIRECTED),
    RelationshipType.CUSTOMER: ("customer", "seller", Directionality.DIRECTED),
    RelationshipType.PARTNER: ("partner", "partner", Directionality.UNDIRECTED),
    RelationshipType.INVESTOR_OR_INVESTEE: ("investor", "investee", Directionality.DIRECTED),
    RelationshipType.PEER: ("peer", "peer", Directionality.UNDIRECTED),
}
```

Implement `Slug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")]`. Require `valid_to >= valid_from` when `valid_to` is present, at least one `evidence_id`, a nonempty summary/context, and dates typed as `datetime.date`. For undirected relationships, reject records whose `from_company_id >= to_company_id` so an inverse duplicate cannot enter a snapshot.

- [ ] **Step 4: Run the schema tests to verify they pass**

Run: `python -m pytest tests/test_models.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the snapshot contracts**

```bash
git add src/nvidia_research/models.py tests/test_models.py
git commit -m "feat: define research snapshot models"
```

## Task 3: Implement deterministic confidence scoring

**Files:**

- Create: `src/nvidia_research/scoring.py`
- Create: `tests/test_scoring.py`

**Interfaces:**

- Consumes `Relationship`, `Evidence`, `Source`, `SourceTier`, and `Directness` from Task 2.
- Produces `ScoreBreakdown` and `score_relationship(relationship, evidence_by_id, source_by_id, as_of) -> ScoreBreakdown`.
- Task 4 and later return `ScoreBreakdown` as part of relationship detail responses.

- [ ] **Step 1: Write failing tests for the formula and calendar cutoffs**

```python
# tests/test_scoring.py
from datetime import date

import pytest

from nvidia_research.models import Evidence, Relationship, RelationshipType, Source
from nvidia_research.scoring import score_recency, score_relationship


@pytest.fixture
def score_case():
    def build(**overrides):
        relationship_type = RelationshipType(overrides["relationship_type"])
        roles = {
            RelationshipType.SUPPLIER: ("supplier", "buyer", "directed"),
            RelationshipType.CUSTOMER: ("customer", "seller", "directed"),
            RelationshipType.PARTNER: ("partner", "partner", "undirected"),
            RelationshipType.INVESTOR_OR_INVESTEE: ("investor", "investee", "directed"),
            RelationshipType.PEER: ("peer", "peer", "undirected"),
        }[relationship_type]
        source = Source(
            id="src-score", title="Score source", url="https://research.example.test/score",
            publisher="Score publisher", published_at=overrides["latest_evidence_date"],
            accessed_at=date(2026, 9, 23), source_tier=overrides["source_tier"],
            access_limitations="Public fixture",
        )
        evidence = Evidence(
            id="ev-score", source_id="src-score", locator="page 1",
            excerpt="Fixture evidence.", directness=overrides["directness"],
            human_verified=True, reviewed_at=date(2026, 9, 23),
        )
        relationship = Relationship(
            id="rel-score-case", from_company_id="nvidia", to_company_id="tsmc",
            relationship_type=relationship_type, from_role=roles[0], to_role=roles[1],
            directionality=roles[2], status="confirmed", summary="Fixture relation.",
            event_or_business_context="Fixture context.", valid_from=date(2025, 1, 1),
            valid_to=None, evidence_ids=["ev-score"],
            score_inputs={
                "independent_publisher_count": overrides["publisher_count"],
                "latest_evidence_date": overrides["latest_evidence_date"],
            },
        )
        return {
            "relationship": relationship,
            "evidence_by_id": {evidence.id: evidence},
            "source_by_id": {source.id: source},
            "as_of": date(2026, 9, 23),
        }
    return build


def test_recency_uses_explicit_day_cutoffs() -> None:
    as_of = date(2026, 9, 23)
    assert score_recency(date(2025, 9, 23), as_of) == 1.0
    assert score_recency(date(2024, 9, 23), as_of) == 0.8
    assert score_recency(date(2022, 9, 24), as_of) == 0.6
    assert score_recency(date(2022, 9, 23), as_of) == 0.4


def test_primary_direct_supplier_with_one_publisher_scores_85(score_case) -> None:
    breakdown = score_relationship(**score_case(
        source_tier="issuer_or_counterparty",
        directness="direct",
        relationship_type="supplier",
        publisher_count=1,
        latest_evidence_date=date(2026, 9, 23),
    ))
    assert breakdown.total == 85
    assert breakdown.components["source_authority"] == 0.9
    assert breakdown.components["independent_corroboration"] == 0.4
```

- [ ] **Step 2: Run the scoring tests to verify they fail**

Run: `python -m pytest tests/test_scoring.py -q`

Expected: FAIL during collection because `nvidia_research.scoring` does not exist.

- [ ] **Step 3: Implement the formula with no hidden defaults**

Implement these exact constants:

```python
SOURCE_AUTHORITY = {
    "regulator_or_exchange": 1.00,
    "issuer_or_counterparty": 0.90,
    "official_public_body": 0.85,
    "independent_reporting": 0.60,
    "other_public": 0.35,
}
TYPE_VERIFIABILITY = {
    "supplier": 1.00,
    "customer": 1.00,
    "investor_or_investee": 1.00,
    "partner": 0.85,
    "peer": 0.75,
}
```

Use day thresholds `<=365`, `<=730`, `<=1460`, and `>1460` for recency values `1.00`, `0.80`, `0.60`, and `0.40`. Map distinct publisher counts `1`, `2`, and `>=3` to `0.40`, `0.70`, and `1.00`; reject zero. Use the strongest linked evidence directness (`direct=1.00`, `inference_support=0.60`, `context_only=0.25`) and the highest linked source authority. Return the total as `round(100 * weighted_sum)` plus a complete explanation listing the evidence dates, publisher count, and each component.

- [ ] **Step 4: Add cases for two/three publishers and non-direct evidence, then run the full scoring test file**

```python
def test_three_publishers_and_context_only_evidence_are_explained(score_case) -> None:
    breakdown = score_relationship(**score_case(
        source_tier="regulator_or_exchange",
        directness="context_only",
        relationship_type="peer",
        publisher_count=3,
        latest_evidence_date=date(2020, 1, 1),
    ))
    assert breakdown.components["independent_corroboration"] == 1.0
    assert breakdown.components["directness"] == 0.25
    assert "peer" in breakdown.explanation
```

Run: `python -m pytest tests/test_scoring.py -q`

Expected: PASS.

- [ ] **Step 5: Commit score calculation**

```bash
git add src/nvidia_research/scoring.py tests/test_scoring.py
git commit -m "feat: add explainable confidence scoring"
```

## Task 4: Load, validate, index, and query local snapshots

**Files:**

- Create: `src/nvidia_research/repository.py`
- Create: `tests/fixtures/snapshot-valid/snapshot.json`
- Create: `tests/fixtures/snapshot-valid/companies.json`
- Create: `tests/fixtures/snapshot-valid/sources.json`
- Create: `tests/fixtures/snapshot-valid/evidence.json`
- Create: `tests/fixtures/snapshot-valid/relationships.json`
- Create: `tests/test_repository.py`

**Interfaces:**

- Consumes all Task 2 models and the Task 3 `score_relationship()` function.
- Produces `SnapshotRepository.from_directory(path: Path) -> SnapshotRepository`, `validate_snapshot(path: Path) -> ValidationReport`, `search_companies(...)`, `list_relationships(...)`, `get_relationship(id)`, `get_evidence(id)`, and `network(company_id, depth, ...)`.
- API and CLI in Tasks 5–6 consume this repository; neither reads JSON files directly.

- [ ] **Step 1: Create a small valid, fictional fixture snapshot and write failing repository tests**

Make `snapshot-valid` contain `nvidia`, `tsmc`, `dell`, `coreweave`, and `amd`, with one human-verified evidence item per relation. The fixture is test-only and must use clearly fictional URLs such as `https://research.example.test/tsmc-filing`.

```python
# tests/test_repository.py
from pathlib import Path

import json
import shutil

import pytest

from nvidia_research.repository import SnapshotRepository, SnapshotValidationError


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
    assert results.items[0].confidence_score == 85


def test_rejects_a_confirmed_relationship_without_human_verified_evidence(tmp_path) -> None:
    # Copy the fixture and replace the confirmed relation evidence with human_verified=false.
    invalid_dir = make_invalid_snapshot(tmp_path, human_verified=False)
    with pytest.raises(SnapshotValidationError, match="human-verified evidence"):
        SnapshotRepository.from_directory(invalid_dir)
```

- [ ] **Step 2: Run repository tests to verify they fail**

Run: `python -m pytest tests/test_repository.py -q`

Expected: FAIL during collection because `nvidia_research.repository` does not exist.

- [ ] **Step 3: Implement strict loading and cross-reference validation**

Read each JSON file with `json.loads(path.read_text(encoding="utf-8"))`, validate every item through the Pydantic models, and aggregate validation failures before raising `SnapshotValidationError`. Validate all of the following before constructing indexes:

- `research_subject_company_id` exists in `companies.json`.
- company IDs and `(ticker, exchange)` pairs are unique;
- source, evidence, and relationship IDs are unique;
- every `Evidence.source_id` exists;
- every relationship endpoint and evidence ID exists;
- a confirmed relationship references at least one evidence item with `human_verified=True`;
- the relationship's `score_inputs.latest_evidence_date` equals the maximum `published_at` across its linked sources;
- `independent_publisher_count` equals the number of distinct linked source publishers.

Build `dict[str, Company]`, `dict[str, Source]`, `dict[str, Evidence]`, and `dict[str, RelationshipDetail]` indexes. Calculate and attach each `ConfidenceScore` once after validation. Sort company search results by `(legal_name.casefold(), id)` and relationship query results by `(-confidence_score, id)` for deterministic pagination.

- [ ] **Step 4: Add paging, date, direction, and graph tests**

```python
def test_network_respects_depth_and_returns_nodes_and_edges() -> None:
    repo = SnapshotRepository.from_directory(FIXTURE)
    result = repo.network(company_id="nvidia", depth=1, min_confidence=0)
    assert {node.id for node in result.nodes} >= {"nvidia", "tsmc"}
    assert all("nvidia" in {edge.from_company_id, edge.to_company_id} for edge in result.edges)


def test_invalid_page_bounds_raise_value_error() -> None:
    repo = SnapshotRepository.from_directory(FIXTURE)
    with pytest.raises(ValueError, match="limit"):
        repo.list_relationships(company_id="nvidia", limit=101)
```

Run: `python -m pytest tests/test_repository.py -q`

Expected: PASS.

- [ ] **Step 5: Commit repository and fixtures**

```bash
git add src/nvidia_research/repository.py tests/fixtures tests/test_repository.py
git commit -m "feat: load and query immutable research snapshots"
```

## Task 5: Expose the repository through a read-only FastAPI application

**Files:**

- Create: `src/nvidia_research/api.py`
- Create: `tests/test_api.py`

**Interfaces:**

- Consumes `SnapshotRepository` from Task 4.
- Produces `create_app(repository: SnapshotRepository) -> FastAPI`. Task 8 adds the module-level default app after the audited production snapshot exists.
- Task 6 reuses `SnapshotRepository` rather than making HTTP calls to this API.

- [ ] **Step 1: Write failing API tests for health, details, filters, and errors**

```python
# tests/test_api.py
from fastapi.testclient import TestClient

from nvidia_research.api import create_app
from nvidia_research.repository import SnapshotRepository


def test_health_reports_loaded_snapshot(fixture_snapshot_path) -> None:
    client = TestClient(create_app(SnapshotRepository.from_directory(fixture_snapshot_path)))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["meta"]["snapshot_id"] == "fixture-2026-09-23"


def test_relationship_detail_contains_score_and_evidence(fixture_snapshot_path) -> None:
    client = TestClient(create_app(SnapshotRepository.from_directory(fixture_snapshot_path)))
    response = client.get("/v1/relationships/rel-tsmc-nvidia-supplier")
    body = response.json()
    assert response.status_code == 200
    assert body["data"]["confidence_score"]["total"] == 85
    assert body["data"]["evidence"][0]["locator"]


def test_invalid_limit_and_unknown_company_have_distinct_statuses(fixture_snapshot_path) -> None:
    client = TestClient(create_app(SnapshotRepository.from_directory(fixture_snapshot_path)))
    assert client.get("/v1/relationships", params={"limit": 101}).status_code == 400
    assert client.get("/v1/network/missing-company").status_code == 404
```

- [ ] **Step 2: Run API tests to verify they fail**

Run: `python -m pytest tests/test_api.py -q`

Expected: FAIL during collection because `nvidia_research.api` does not exist.

- [ ] **Step 3: Implement the application factory and all read-only routes**

Implement `/health`, `/v1/companies`, `/v1/relationships`, `/v1/relationships/{relationship_id}`, `/v1/network/{company_id}`, and `/v1/evidence/{evidence_id}`. Map all successful responses into this envelope:

```json
{
  "meta": {
    "snapshot_id": "nvidia-2026-09-23",
    "as_of": "2026-09-23",
    "methodology_version": "1.0"
  },
  "data": {}
}
```

For paginated endpoints, add `limit`, `offset`, and `total` to `meta`. Use Pydantic/FastAPI query constraints for `limit=1..100`, `offset>=0`, and `depth=1..2`. Register a `RequestValidationError` exception handler that converts query-validation failures from FastAPI's default `422` into `{ "detail": "..." }` with status `400`. Convert repository `ValueError` cases into the same `400` shape and absent IDs into `404` responses. Do not add mutation routes, background tasks, source fetching, or CORS configuration.

- [ ] **Step 4: Run API tests and inspect generated OpenAPI routes**

Run: `python -m pytest tests/test_api.py -q && python -c 'from pathlib import Path; from nvidia_research.api import create_app; from nvidia_research.repository import SnapshotRepository; app = create_app(SnapshotRepository.from_directory(Path("tests/fixtures/snapshot-valid"))); print("\\n".join(route.path for route in app.routes))'`

Expected: API tests PASS and output includes all six required endpoint paths.

- [ ] **Step 5: Commit the HTTP interface**

```bash
git add src/nvidia_research/api.py tests/test_api.py pyproject.toml
git commit -m "feat: add read-only research API"
```

## Task 6: Add an equivalent offline command-line interface

**Files:**

- Modify: `src/nvidia_research/cli.py`
- Create: `tests/test_cli.py`

**Interfaces:**

- Consumes Task 4 `SnapshotRepository` and the default snapshot-path convention introduced in this task.
- Produces `companies`, `relationships`, `relationship`, `network`, and `validate` CLI subcommands.
- Uses `main(argv)` from Task 1 and prints one JSON document to stdout for every command.

- [ ] **Step 1: Write failing CLI behavior tests**

```python
# tests/test_cli.py
import json

from nvidia_research.cli import main


def test_relationships_command_outputs_the_same_snapshot_metadata(fixture_snapshot_path, capsys) -> None:
    exit_code = main([
        "--snapshot", str(fixture_snapshot_path),
        "relationships", "--company", "nvidia", "--type", "supplier",
    ])
    body = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert body["meta"]["snapshot_id"] == "fixture-2026-09-23"
    assert body["data"][0]["id"] == "rel-tsmc-nvidia-supplier"


def test_validate_returns_one_for_an_invalid_snapshot(invalid_snapshot_path, capsys) -> None:
    assert main(["--snapshot", str(invalid_snapshot_path), "validate"]) == 1
    assert "human-verified evidence" in capsys.readouterr().out
```

- [ ] **Step 2: Run CLI tests to verify they fail**

Run: `python -m pytest tests/test_cli.py -q`

Expected: FAIL because the command parser does not define the required subcommands.

- [ ] **Step 3: Implement the CLI without duplicating query logic**

Add root option `--snapshot PATH`, defaulting to the `NVIDIA_RESEARCH_SNAPSHOT_PATH` environment variable when present and otherwise `data/snapshots/nvidia-2026-09-23`. Define subcommands and options exactly as follows:

```text
companies --query TEXT --ticker TICKER --exchange EXCHANGE --limit N --offset N
relationships --company ID --type TYPE --direction inbound|outbound|either --status STATUS --as-of YYYY-MM-DD --min-confidence N --limit N --offset N
relationship RELATIONSHIP_ID
network COMPANY_ID --depth 1|2 --type TYPE --status STATUS --min-confidence N
validate
```

Use `json.dumps(payload, ensure_ascii=False, indent=2, default=str)` for successful output. Return `2` for parser errors, `1` for validation or runtime query errors, and `0` for successful queries. Keep `validate` offline and print `{ "valid": false, "errors": [...] }` instead of a traceback for an invalid directory.

- [ ] **Step 4: Run CLI tests and real help output**

Run: `python -m pytest tests/test_cli.py -q && nvidia-research --help`

Expected: tests PASS and help lists `companies`, `relationships`, `relationship`, `network`, and `validate`.

- [ ] **Step 5: Commit the CLI**

```bash
git add src/nvidia_research/cli.py tests/test_cli.py
git commit -m "feat: add offline research CLI"
```

## Task 7: Curate the first audited NVIDIA snapshot

**Files:**

- Create: `data/snapshots/nvidia-2026-09-23/snapshot.json`
- Create: `data/snapshots/nvidia-2026-09-23/companies.json`
- Create: `data/snapshots/nvidia-2026-09-23/sources.json`
- Create: `data/snapshots/nvidia-2026-09-23/evidence.json`
- Create: `data/snapshots/nvidia-2026-09-23/relationships.json`
- Create: `tests/test_snapshot_nvidia.py`

**Interfaces:**

- Consumes the production contracts and validation rule from Tasks 2–4.
- Produces the production default snapshot `nvidia-2026-09-23` for Task 8's module-level application and Task 6's default CLI.
- Documentation tasks use its exact snapshot ID and boundaries.

- [ ] **Step 1: Write the failing production-snapshot acceptance test**

```python
# tests/test_snapshot_nvidia.py
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
            assert evidence.source.url.startswith("https://")
```

- [ ] **Step 2: Run the acceptance test to verify it fails before data exists**

Run: `python -m pytest tests/test_snapshot_nvidia.py -q`

Expected: FAIL because `data/snapshots/nvidia-2026-09-23/` does not exist.

- [ ] **Step 3: Research and manually verify only lawful, primary-source candidates**

For each required category, begin with the following evidence families, recording the exact source title, canonical URL, publisher, publication date, page/section locator, short excerpt, access date, and any limitations:

| Category | Candidate listed counterparty | First primary-source evidence family | Acceptance condition |
|---|---|---|---|
| Supplier | Taiwan Semiconductor Manufacturing Company (`TSM`) | NVIDIA product technical materials and/or TSMC annual filing that directly identifies the manufacturing relationship | The excerpt directly connects the named product/service and both entities; do not infer exclusivity. |
| Customer | A listed cloud or systems company | Counterparty regulatory filing or official release that explicitly identifies its purchase/use of NVIDIA products or services | Confirm the company and transaction role; do not equate technical availability with a direct purchase. |
| Partner | Dell Technologies (`DELL`) | Joint NVIDIA/Dell official announcement or both companies' investor-relations materials | Record the named collaboration and its product/event scope. |
| Investor or investee | CoreWeave (`CRWV`) | CoreWeave registration/annual filing and, where available, NVIDIA official material documenting the investment | Record investor → investee; do not classify a supply agreement alone as an investment. |
| Peer | Advanced Micro Devices (`AMD`) or Intel (`INTC`) | NVIDIA annual filing's competition section plus the comparable's listed-company identity | State the comparison axis from the source; do not represent it as a supply-chain tie. |

Reject any candidate whose available material only consists of paywalled reporting, a login-protected document, a robot-restricted page, untraceable reposts, customer anecdotes, or a conclusion that lacks an entity/ticker match. If no candidate meets the `customer` condition, document the gap and add a lawful, direct source before claiming category coverage.

- [ ] **Step 4: Enter the audited snapshot records and validate factual integrity**

Set the manifest to:

```json
{
  "snapshot_id": "nvidia-2026-09-23",
  "as_of": "2026-09-23",
  "methodology_version": "1.0",
  "research_subject_company_id": "nvidia",
  "research_boundary": "Publicly accessible, manually verified listed-company relationships involving NVIDIA; no investment recommendation."
}
```

For every confirmed relation, add at least one `human_verified: true` evidence record with a nonempty locator and source excerpt. Set `latest_evidence_date` and `independent_publisher_count` from the actual linked sources rather than estimating them. Use `inferred` or `unknown` where evidence does not meet the confirmed threshold.

Run: `nvidia-research --snapshot data/snapshots/nvidia-2026-09-23 validate && python -m pytest tests/test_snapshot_nvidia.py -q`

Expected: validation returns `0` and both production-snapshot tests PASS.

- [ ] **Step 5: Perform a human audit before committing research conclusions**

For every confirmed record, verify the following against the original public source in a normal browser session:

1. Legal entity name, ticker, and exchange match the company record.
2. The quote and locator lead to the stated relationship, not merely adjacent context.
3. Relationship direction, type, event scope, and effective dates match the source.
4. The evidence is public without bypassing access controls and the source metadata is accurate.
5. The conclusion wording does not imply exclusivity, volume, continuation, causality, or investment advice absent in the evidence.

Record the reviewer and date in `docs/ai-and-human-review.md` without personal data beyond a role or initials chosen by the reviewer.

- [ ] **Step 6: Commit the first research snapshot**

```bash
git add data/snapshots/nvidia-2026-09-23 tests/test_snapshot_nvidia.py docs/ai-and-human-review.md
git commit -m "data: add audited NVIDIA relationship snapshot"
```

## Task 8: Write reproducibility, methodology, and AI-review documentation

**Files:**

- Create: `README.md`
- Create: `docs/research-methodology.md`
- Create: `docs/data-update-guide.md`
- Create: `docs/ai-and-human-review.md`
- Modify: `tests/test_api.py`

**Interfaces:**

- Consumes the actual commands and snapshot ID from Tasks 5–7.
- Produces instructions a reviewer can execute without rediscovering project assumptions.
- The updated API test confirms the documented default snapshot starts successfully.

- [ ] **Step 1: Write the failing default-startup test**

```python
def test_default_app_loads_the_committed_default_snapshot(monkeypatch) -> None:
    monkeypatch.delenv("NVIDIA_RESEARCH_SNAPSHOT_PATH", raising=False)
    from nvidia_research.api import create_default_app

    client = TestClient(create_default_app())
    assert client.get("/health").json()["meta"]["snapshot_id"] == "nvidia-2026-09-23"
```

- [ ] **Step 2: Run the startup test to verify its current behavior**

Run: `python -m pytest tests/test_api.py::test_default_app_loads_the_committed_default_snapshot -q`

Expected: FAIL because `create_default_app()` has not been implemented yet.

- [ ] **Step 3: Implement the documented default-path helper and write exact operating instructions**

Add `create_default_app()` in `api.py`, resolving `NVIDIA_RESEARCH_SNAPSHOT_PATH` first and `data/snapshots/nvidia-2026-09-23` second, then expose `app = create_default_app()` for the documented Uvicorn command.

In `README.md`, include these exact commands:

```bash
python -m pip install -e '.[dev]'
python -m pytest -q
uvicorn nvidia_research.api:app --reload
nvidia-research relationships --company nvidia --status confirmed
nvidia-research network nvidia --depth 2 --min-confidence 70
```

Document that `GET /docs` exposes the local FastAPI contract, that runtime does not fetch sources, and that the service is not investment advice. List known coverage limits: the snapshot is bounded by its as-of date, excludes private/unverifiable relationships, and may not represent all geographic markets or counterparties.

In `docs/research-methodology.md`, copy the source hierarchy, conclusion-state definitions, endpoint-role table, exact formula, and distinction between confidence and economic importance from the approved specification.

In `docs/data-update-guide.md`, require this sequence: choose a new snapshot ID; collect only permitted sources; verify entities; write source/evidence/relationship records; run `validate`; run tests; obtain human audit; add a new directory without editing the old snapshot.

In `docs/ai-and-human-review.md`, state that AI may assist with candidate discovery, code drafting, and wording review, but humans must validate entities, source access, quotations, relationship classification, score inputs, and final conclusions. Include a dated review checklist table with columns `snapshot_id`, `reviewer_role_or_initials`, `review_date`, `scope`, and `outcome`.

- [ ] **Step 4: Run documentation-linked startup and complete test suite**

Run: `python -m pytest tests/test_api.py::test_default_app_loads_the_committed_default_snapshot -q && python -m pytest -q`

Expected: both commands PASS with no network access.

- [ ] **Step 5: Commit reproducibility documentation**

```bash
git add README.md docs src/nvidia_research/api.py tests/test_api.py
git commit -m "docs: document reproducible NVIDIA research workflow"
```

## Task 9: Run final offline verification and review the release surface

**Files:**

- Modify only if verification exposes a defect: files directly responsible for that defect.

**Interfaces:**

- Consumes the completed package, snapshot, API, CLI, tests, and documentation from Tasks 1–8.
- Produces verified local release evidence; no new feature interfaces.

- [ ] **Step 1: Run format-independent integrity checks**

Run:

```bash
git diff --check
nvidia-research --snapshot data/snapshots/nvidia-2026-09-23 validate
python -m pytest -q
```

Expected: no whitespace errors, validation exit `0`, and all tests PASS.

- [ ] **Step 2: Exercise the documented user-facing paths without the network**

Run:

```bash
uvicorn nvidia_research.api:app --host 127.0.0.1 --port 8000
curl -s http://127.0.0.1:8000/health
curl -s 'http://127.0.0.1:8000/v1/relationships?company_id=nvidia&status=confirmed&limit=20'
nvidia-research relationship rel-tsmc-nvidia-supplier
```

Expected: every response includes `snapshot_id` and `as_of`; the relationship detail contains an evidence locator, original URL, conclusion status, and component-level score explanation. Stop the local Uvicorn process after the smoke test.

- [ ] **Step 3: Perform final acceptance review against the challenge**

Verify the repository demonstrates all ten challenge requirements: legal public-source boundaries, entity clarity, category coverage, directions and timing, traceable source metadata, explainable score, immutable snapshots, HTTP JSON API, CLI, pagination/input validation, negative tests, reproducible instructions, known limitations, and AI/human-review disclosure.

If a requirement is missing, create a focused defect commit containing the test that exposed it and the smallest corrective implementation. Do not add a frontend, crawler, external database, or unapproved source category during release review.

- [ ] **Step 4: Commit any verification-driven correction and record the final state**

Run:

```bash
git status --short
git log --oneline --max-count=10
```

Expected: a clean working tree and a concise sequence of independently reviewable commits.

## Plan self-review

- **Spec coverage:** Tasks 2–4 cover structured entities, relations, evidence, timing, status, and explainable scoring. Tasks 5–6 cover HTTP JSON, CLI, validation, filtering, pagination, and errors. Task 7 covers lawful manual research, listed-company category coverage, immutable source snapshots, and human verification. Task 8 covers reproducibility, limits, updates, AI, and human-review disclosure. Task 9 checks the full acceptance surface offline.
- **Placeholder scan:** The plan contains no unfinished implementation markers. The initial factual relationship roster is intentionally acquired only through Task 7's manual, lawful evidence review; no relationship fact is fabricated in this plan.
- **Type consistency:** `RelationshipType`, `RelationshipStatus`, and `Directionality` originate in `models.py`; `SnapshotRepository` owns loading/querying; `score_relationship()` owns scoring; API and CLI both consume the repository. All later task names and parameters use these same interfaces.
