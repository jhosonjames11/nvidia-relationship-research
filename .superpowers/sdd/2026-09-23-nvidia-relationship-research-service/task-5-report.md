# Task 5 implementation report

## Changes

- Added `create_app(repository)` in `src/nvidia_research/api.py`; it is an application factory only and does not create a module-level default application.
- Added the six read-only routes: `/health`, `/v1/companies`, `/v1/relationships`, `/v1/relationships/{relationship_id}`, `/v1/network/{company_id}`, and `/v1/evidence/{evidence_id}`.
- Every successful service response is wrapped in `meta` and `data`. Metadata carries the loaded snapshot ID, as-of date, and methodology version; company and relationship pages also carry `limit`, `offset`, and `total`.
- Added company query/ticker/exchange filtering and stable pagination, and forwarded relationship and network filters to `SnapshotRepository`.
- Added FastAPI query constraints for pagination, depth, and confidence bounds. A `RequestValidationError` handler converts validation failures, including invalid enum/date values and out-of-range values, from 422 to `{"detail": "..."}` with HTTP 400. Repository `ValueError`s use the same 400 envelope.
- Missing relationships and evidence, plus a missing network root (`KeyError` from the repository), return HTTP 404 JSON detail responses.
- Added integration-style HTTP tests using the real immutable fixture snapshot, covering each endpoint, filtering, metadata envelopes, traceability data, validation failures, and missing resources.

## RED/GREEN evidence

RED: `python -m pytest tests/test_api.py -q` failed during collection with `ModuleNotFoundError: No module named 'nvidia_research.api'`, proving the newly added tests exercised an absent public API module.

GREEN: After adding the factory and routes, `python -m pytest tests/test_api.py -q` passed with `12 passed in 0.19s`.

## Verification

- `python -m pytest tests/test_api.py -q` — 12 passed.
- Generated route inspection listed all required paths: `/health`, `/v1/companies`, `/v1/relationships`, `/v1/relationships/{relationship_id}`, `/v1/network/{company_id}`, and `/v1/evidence/{evidence_id}`.
- `python -m pytest -q` — 43 passed.
- `git diff --check` — no whitespace errors.

## Self-review

- The API exclusively reads the provided in-memory `SnapshotRepository`; it fetches no sources, starts no background work, exposes no write route, and configures no CORS policy.
- The health, detail, graph, and list handlers consistently use the same metadata helper. Pagination is present only for paginated responses.
- FastAPI validation, repository validation, and absent-resource cases have distinct documented status behavior: 400 for invalid query/filter input and 404 for absent entities.
- No production data or module-level default app was added; that remains deferred to Task 8 as required.

## Concerns

- None. The fixture remains fictional, test-only data and is not production research.

## Commits

- `08081de feat: add read-only research API`
