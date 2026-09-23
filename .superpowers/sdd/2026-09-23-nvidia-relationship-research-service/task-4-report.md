# Task 4 implementation report

## Changes

- Added an offline-only `SnapshotRepository` that reads one local JSON snapshot, validates every JSON item through the immutable Pydantic contracts, and creates immutable in-memory indexes.
- Added aggregated schema and cross-reference validation for required files, duplicate company/source/evidence/relationship IDs, duplicate ticker/exchange pairs, subject company presence, source/evidence/relationship links, confirmed human verification, and score-input/source consistency.
- Validates `latest_evidence_date` and distinct publisher count before invoking the pure confidence scorer; each relationship score is calculated once at load time.
- Added deterministic company and relationship queries, bounds-checked pagination, date/type/status/direction/confidence filtering, evidence and relationship detail lookup, and depth-limited network traversal.
- Added a clearly fictional, test-only snapshot fixture. Every fixture relationship, source, and boundary is marked as fictional and not a research conclusion; all fixture URLs use `research.example.test`.

## Files

- `src/nvidia_research/repository.py`
- `tests/test_repository.py`
- `tests/fixtures/snapshot-valid/snapshot.json`
- `tests/fixtures/snapshot-valid/companies.json`
- `tests/fixtures/snapshot-valid/sources.json`
- `tests/fixtures/snapshot-valid/evidence.json`
- `tests/fixtures/snapshot-valid/relationships.json`

## RED/GREEN evidence

RED: `python -m pytest tests/test_repository.py -q` failed during collection with `ModuleNotFoundError: No module named 'nvidia_research.repository'` before implementation.

RED: The getter contract test failed with `AttributeError` after temporarily removing the getter methods, confirming it exercises the public repository behavior.

GREEN: `python -m pytest tests/test_repository.py -q` passed with `8 passed in 0.05s`.

## Commands and results

- `python -m pytest tests/test_repository.py -q` — 8 passed.
- `python -m pytest -q` — 29 passed.
- `python -m compileall -q src` — passed.
- `git diff --check` — passed with no whitespace errors.

## Self-review

- The repository performs no network access, writes, fetching, API routing, or CLI behavior.
- JSON is loaded with `json.loads(path.read_text(encoding="utf-8"))`; invalid JSON, model errors, and relationship inconsistencies are accumulated into one validation report.
- Repository maps are mapping proxies, and the loaded entity Pydantic models use the immutable contracts from Task 2.
- Company ordering is `(legal_name.casefold(), id)`; relationship and network-edge ordering is `(-confidence_score, id)`.
- Direct graph traversal only includes qualifying edges reached within one or two hops, and unknown graph roots are explicit `KeyError`s for later HTTP-layer mapping to 404.

## Concerns

- `SnapshotRepository.network()` deliberately raises `KeyError` for an absent root company rather than assigning HTTP semantics. Task 5 should map that condition to its documented 404 response.
- The fixture is intentionally fictional and must remain test-only; it is not usable as production relationship research.

## Commits

- `ddecfdd feat: load and query immutable research snapshots`

## Review fixes

The Task 4 review found two important correctness issues and both now have focused regression coverage.

- Network traversal previously reused `list_relationships(..., limit=100)`, so its unpaginated graph result silently excluded eligible edges after the first 100. Filtering now lives in `_filtered_relationships()`; paginated listing applies the page only afterward, while `network()` traverses the entire filtered edge set. `test_network_includes_all_101_eligible_root_edges` confirms the 101st qualifying root edge is returned.
- `ScoreBreakdown` is frozen only at the attribute level; its `components` and `inputs` dictionaries were still mutable after being cached inside a relationship detail. The repository now replaces them with a JSON-serializable immutable dictionary at load time. `test_mutating_a_returned_score_mapping_cannot_corrupt_cached_details` proves an attempted mutation cannot affect a later lookup. A direct `model_dump(mode="json")` check confirms this representation remains serializable for the later API layer.

RED: both new tests failed against the reviewed implementation: graph traversal returned 100 rather than 101 edges, and mutating `components["source_authority"]` changed the later lookup from `0.9` to `0.0`.

GREEN: `python -m pytest tests/test_repository.py -q` — 10 passed; `python -m pytest -q` — 31 passed; `python -m compileall -q src` and `git diff --check` passed.
