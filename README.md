# NVIDIA Relationship Research Service

An offline, read-only research service for inspecting evidence-backed, listed-company relationships involving NVIDIA. The committed production snapshot is `nvidia-2026-09-23`, with an as-of date of 2026-09-23.

## Install and verify

From the repository root, install the project and run its entirely local test suite:

```bash
python -m pip install -e '.[dev]'
python -m pytest -q
```

Tests use committed fixtures and snapshots. Runtime does not fetch sources, visit source URLs, or modify snapshot records.

## Run the local API

```bash
uvicorn nvidia_research.api:app --reload
```

The default application loads `data/snapshots/nvidia-2026-09-23` from the repository root. To load a different local snapshot, set `NVIDIA_RESEARCH_SNAPSHOT_PATH` before starting Uvicorn; that environment variable takes precedence over the default.

`GET /docs` exposes the local FastAPI contract using Swagger UI assets installed with the package; it remains usable without runtime network access. `/redoc` is deliberately disabled because it would otherwise depend on remote assets. The read-only research routes are `GET /health`, `GET /v1/companies`, `GET /v1/relationships`, `GET /v1/relationships/{relationship_id}`, `GET /v1/network/{company_id}`, and `GET /v1/evidence/{evidence_id}`.

## Use the CLI

```bash
nvidia-research relationships --company nvidia --status confirmed
nvidia-research network nvidia --depth 2 --min-confidence 70
nvidia-research network nvidia --as-of 2026-09-23
```

Use `nvidia-research validate` to validate the default local snapshot, or pass `--snapshot path/to/snapshot` to select a different local directory. Validation and queries do not fetch URLs.

## Scope and limits

This service is research tooling, not investment advice, financial advice, or a recommendation to buy or sell a security. Confidence scores measure evidentiary support for a stated classification; they do not measure economic importance, commercial significance, or expected investment returns.

Coverage is bounded by the snapshot's as-of date. It excludes private or unverifiable relationships and may not represent all geographic markets or counterparties. See [the research methodology](docs/research-methodology.md), [the data update guide](docs/data-update-guide.md), and [the AI and human review record](docs/ai-and-human-review.md) before interpreting or extending the snapshot.
