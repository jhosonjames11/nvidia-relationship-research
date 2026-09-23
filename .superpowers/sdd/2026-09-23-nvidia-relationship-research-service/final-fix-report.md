# NVIDIA Relationship Research Service — Final Fix Wave Report

Date: 2026-09-23

## Changes

1. Made `GET /docs` fully local after installation. The FastAPI default documentation and ReDoc endpoints are disabled; a custom `/docs` route serves Swagger UI with package-installed `swagger-ui-bundle` files mounted at `/docs/static`. Its generated HTML references only local CSS, JavaScript, favicon, and `/openapi.json` paths. `/redoc` now returns 404, avoiding its default remote dependency.
2. Normalized API `direction=either` to no repository direction filter, matching the CLI and documented semantics.
3. Added CLI `network --as-of YYYY-MM-DD` and forwarded its parsed date to `SnapshotRepository.network(valid_on=...)`.

No snapshot facts, relationship semantics, source policy, mutability, or runtime network behavior changed.

## Files changed

- `pyproject.toml` — adds the package-installed Swagger UI static-asset dependency.
- `src/nvidia_research/api.py` — local Swagger route/static mount, disabled ReDoc, `either` normalization.
- `src/nvidia_research/cli.py` — network `--as-of` parser and repository forwarding.
- `tests/test_api.py` — local docs/no-remote-assets/ReDoc-disabled and API `either` regression tests.
- `tests/test_cli.py` — expired fixture-edge filtering regression test.
- `README.md` — documents offline docs behavior, disabled ReDoc, and CLI network time filtering.

## Focused RED/GREEN evidence

RED command:

```text
python -m pytest tests/test_api.py::test_docs_serve_swagger_assets_locally tests/test_api.py::test_relationships_direction_either_does_not_restrict_results tests/test_cli.py::test_network_as_of_filters_expired_fixture_edges -q
```

Before implementation it failed exactly in the three intended areas: `/docs` used CDN asset URLs, API `direction=either` returned 400, and the CLI rejected `network --as-of` before producing JSON.

GREEN command (after the minimal implementation):

```text
3 passed in 0.21s
```

## Full verification

```text
python -m pip install -e '.[dev]'  # installed the declared local Swagger asset dependency
python -m pytest -q               # 58 passed in 0.28s
nvidia-research validate          # {"valid": true, "errors": []}
git diff --check                  # exit 0, no output
```

## Unresolved concerns

None identified. The Swagger asset wheel is fetched only during normal package installation; after installation, `/docs`, `/openapi.json`, and all application queries are served locally without runtime networking.

## Commit

Fix wave: `735d179 fix: keep docs and filters offline-consistent`
