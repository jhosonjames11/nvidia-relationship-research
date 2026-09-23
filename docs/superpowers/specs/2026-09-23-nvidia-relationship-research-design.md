# NVIDIA Relationship Research Service — Design Specification

**Status:** approved design, awaiting specification review

**Research subject:** NVIDIA Corporation (`nvidia`)

**Purpose:** Deliver an offline-runnable, evidence-backed research service that explains NVIDIA's relationships with listed companies. The service must make each relationship conclusion, its timing, direction, evidence, status, and confidence score inspectable without asking a reviewer to re-fetch public web pages.

## 1. Scope and success criteria

The first release is a local Python service and command-line program. It provides a versioned snapshot of manually verified public-source research and read-only HTTP/JSON queries over that snapshot.

The first release includes:

- NVIDIA as the single research subject and a documented `as_of` date.
- Listed-company relationships in the categories `supplier`, `customer`, `partner`, `investor_or_investee`, and `peer` where evidence satisfies the stated rules.
- Explicit entity identities, relationship directions and roles, business events, time bounds, conclusion states, evidence locators, and explainable 0–100 confidence scores.
- A FastAPI HTTP API, an equivalent `argparse` CLI, offline test fixtures, validation, and documentation.

The first release explicitly excludes:

- A web frontend, authentication, database server, graph database, background jobs, or a cloud deployment.
- Automatic web crawling, browser automation, paywall/login/robots bypasses, or any collection of personal, customer, or private data.
- Investment advice, financial recommendations, or a score intended to predict returns or commercial importance.

Success means a reviewer can clone the repository, install the declared dependencies, execute tests without network access, start the service, and trace every returned relationship to versioned local evidence metadata and its public original URL.

## 2. Research boundaries and evidence policy

### 2.1 Entity and time boundary

The snapshot manifest names a unique `snapshot_id`, ISO-8601 `as_of` date, methodology version, and research boundary. NVIDIA is identified by a stable internal ID and its exchange/ticker metadata, not by name matching alone.

The scope includes listed counterparties and comparables for which an evidence-backed conclusion can be made. A company that appears in an article but cannot be disambiguated to a listed legal entity is excluded. An uncertain relationship is retained only as `inferred` or `unknown`; it is never converted to `confirmed` merely to fill a category.

### 2.2 Permitted sources

Researchers manually review legally accessible public materials. Preferred source order is:

1. regulator and exchange filings;
2. NVIDIA or counterparty annual reports, investor-relations pages, and official releases;
3. official government or regulator publications;
4. reputable independent reporting when primary materials do not establish the requested fact.

Each source records its publisher, canonical URL, publication date, access date, source tier, and known access restrictions. The repository stores metadata and a short fair-use evidence excerpt; it does not redistribute complete third-party reports or PDFs.

No workflow may bypass robots rules, authentication, a paywall, a CAPTCHA, rate limits, or site terms. A source that cannot be revisited lawfully is not needed at runtime because the curated snapshot remains locally available, but it must still be clearly labelled with its access limitation.

### 2.3 Research conclusion states

- `confirmed`: a directly relevant, manually verified evidence item supports the defined relationship.
- `inferred`: the relation is a transparent, limited inference from stated facts; its explanation names the inference and its uncertainty.
- `unknown`: available material is insufficient, ambiguous, or conflicting; no positive relationship conclusion is made.

Only `confirmed` records must contain at least one evidence record marked `human_verified: true`. The score measures support for the classification, not the economic significance of the relation.

## 3. Snapshot storage and data contracts

Every dataset release is an immutable directory under `data/snapshots/<snapshot_id>/`:

```text
data/snapshots/<snapshot_id>/
├── snapshot.json
├── companies.json
├── sources.json
├── evidence.json
└── relationships.json
```

`snapshot.json` contains `snapshot_id`, `as_of`, `generated_at`, `methodology_version`, `research_subject_company_id`, and a concise boundary statement. The application accepts exactly one snapshot directory at startup; it does not merge files from different snapshots.

### 3.1 Company record

```json
{
  "id": "nvidia",
  "legal_name": "NVIDIA Corporation",
  "ticker": "NVDA",
  "exchange": "NASDAQ",
  "country_or_region": "US",
  "aliases": ["NVIDIA", "Nvidia"]
}
```

All IDs are lower-case, hyphen-separated slugs and unique within the snapshot. `ticker` plus `exchange` is unique. `aliases` support search only and never identify an entity without the canonical company record.

### 3.2 Source and evidence records

```json
{
  "id": "src-example",
  "title": "Document title",
  "url": "https://example.com/document",
  "publisher": "Publisher name",
  "published_at": "2026-01-15",
  "accessed_at": "2026-09-23",
  "source_tier": "issuer_or_counterparty",
  "access_limitations": "Public page; no login required"
}
```

```json
{
  "id": "ev-example",
  "source_id": "src-example",
  "locator": "Annual report, page 42, section heading",
  "excerpt": "Short, necessary quotation supporting the claim.",
  "directness": "direct",
  "human_verified": true,
  "reviewed_at": "2026-09-23"
}
```

`source_tier` is one of `regulator_or_exchange`, `issuer_or_counterparty`, `official_public_body`, `independent_reporting`, or `other_public`. `directness` is one of `direct`, `inference_support`, or `context_only`. Each evidence record belongs to one source and has a non-empty locator and excerpt.

### 3.3 Relationship record and direction semantics

```json
{
  "id": "rel-example",
  "from_company_id": "provider-company",
  "to_company_id": "nvidia",
  "relationship_type": "supplier",
  "from_role": "supplier",
  "to_role": "buyer",
  "directionality": "directed",
  "status": "confirmed",
  "summary": "A concise, evidence-bounded relationship statement.",
  "event_or_business_context": "The product, service, transaction, or named event.",
  "valid_from": "2025-01-01",
  "valid_to": null,
  "evidence_ids": ["ev-example"],
  "score_inputs": {
    "independent_publisher_count": 1,
    "latest_evidence_date": "2026-01-15"
  }
}
```

The edge direction represents the stated role, not an arbitrary display convention:

| `relationship_type` | `from_role` | `to_role` | Direction |
|---|---|---|---|
| `supplier` | supplier | buyer | supplier → buyer |
| `customer` | customer | seller | customer → seller |
| `partner` | partner | partner | undirected |
| `investor_or_investee` | investor | investee | investor → investee |
| `peer` | peer | peer | undirected |

For undirected relations, company IDs are stored in lexicographic order to prevent duplicate edges. The API derives `inbound`, `outbound`, and `either` relative to the company passed by a caller. `valid_to: null` means the available evidence does not establish an end date; it does not assert that the relation continues today.

`summary` must describe what the cited material supports. It cannot add revenue, volume, exclusivity, causation, customer status, or commercial importance that the evidence does not support.

## 4. Deterministic, explainable confidence score

`confidence_score` is calculated at load time and never stored as an unverified hand-entered total. The response includes the formula version, weighted components, raw inputs, total, and a human-readable explanation.

```text
confidence_score = round(100 * (
  0.30 * source_authority +
  0.20 * independent_corroboration +
  0.20 * recency +
  0.15 * directness +
  0.15 * type_verifiability
))
```

All components are bounded in `[0.0, 1.0]`.

- `source_authority`: the highest authority value among linked evidence sources: `regulator_or_exchange=1.00`, `issuer_or_counterparty=0.90`, `official_public_body=0.85`, `independent_reporting=0.60`, `other_public=0.35`.
- `independent_corroboration`: `0.40` for one distinct publisher, `0.70` for two, `1.00` for three or more. Multiple URLs from the same publisher count once; syndicated copies are treated as the origin publisher.
- `recency`: calculated from `as_of - latest_evidence_date`: `1.00` at 12 months or fewer, `0.80` at 13–24 months, `0.60` at 25–48 months, `0.40` above 48 months. A relationship with a non-null `valid_to` does not receive a currentness assertion in the explanation.
- `directness`: `1.00` when at least one record is `direct`, `0.60` when the strongest record is `inference_support`, otherwise `0.25`.
- `type_verifiability`: `1.00` for `supplier`, `customer`, and `investor_or_investee`; `0.85` for `partner`; `0.75` for `peer`. This only reflects how readily the specified category can be verified, not a judgment that one relation matters more than another.

Any conflicting material is represented by an `inferred` or `unknown` relation with an explanation. It must not be suppressed merely because it reduces confidence.

## 5. Service, API, and CLI

The service uses FastAPI and Pydantic. A repository layer validates and indexes the JSON snapshot once at startup; the API and CLI both call the same query layer. The process is read-only and requires no network connection after installation.

### 5.1 HTTP interface

| Endpoint | Required behavior |
|---|---|
| `GET /health` | Return application status, snapshot ID, as-of date, and record counts. |
| `GET /v1/companies` | Search by `query`, `ticker`, `exchange`; paginate with `limit` and `offset`. |
| `GET /v1/relationships` | Filter with `company_id`, `relationship_type`, `direction`, `status`, `as_of`, `min_confidence`, `limit`, and `offset`. |
| `GET /v1/relationships/{relationship_id}` | Return a relation, score breakdown, evidence, and source metadata. |
| `GET /v1/network/{company_id}` | Return 1–2-hop graph edges and nodes; accept the relation filters and `depth`. |
| `GET /v1/evidence/{evidence_id}` | Return evidence locator and its source metadata. |

`limit` defaults to `20` and is bounded to `1..100`; `offset` defaults to `0`. `depth` is bounded to `1..2`. Invalid enum values, dates, numeric ranges, and incompatible query arguments return a structured `400` response. Missing companies, relationships, and evidence return `404`.

Every successful response has an `meta` object containing `snapshot_id`, `as_of`, `methodology_version`, and, when paginated, `limit`, `offset`, and `total`. Detail responses never return a full third-party document: only the short excerpt, locator, source metadata, and original URL.

### 5.2 Command-line interface

The console script is named `nvidia-research` and returns JSON by default. It supports:

```bash
nvidia-research companies --query TSMC
nvidia-research relationships --company nvidia --type supplier --status confirmed
nvidia-research relationship rel-nvidia-tsmc-supplier
nvidia-research network nvidia --depth 2 --min-confidence 70
nvidia-research validate
```

The first four commands use the same filters and output schemas as the API. `validate` checks all snapshot files and writes a machine-readable validation summary. It exits `0` for a valid snapshot and `1` when validation errors exist. It neither fetches URLs nor changes snapshot files.

## 6. Repository layout

```text
nvidia-relationship-research/
├── pyproject.toml
├── README.md
├── src/nvidia_research/
│   ├── __init__.py
│   ├── models.py
│   ├── repository.py
│   ├── scoring.py
│   ├── api.py
│   └── cli.py
├── data/snapshots/<snapshot_id>/
│   ├── snapshot.json
│   ├── companies.json
│   ├── sources.json
│   ├── evidence.json
│   └── relationships.json
├── tests/
│   ├── fixtures/
│   ├── test_models.py
│   ├── test_scoring.py
│   ├── test_repository.py
│   ├── test_api.py
│   └── test_cli.py
└── docs/
    ├── research-methodology.md
    ├── data-update-guide.md
    ├── ai-and-human-review.md
    └── superpowers/specs/2026-09-23-nvidia-relationship-research-design.md
```

`models.py` owns all Pydantic schemas and enums. `repository.py` owns file loading, cross-reference validation, indexes, and query filtering. `scoring.py` owns the formula and score explanations. `api.py` is limited to HTTP parsing and response mapping. `cli.py` is limited to argument parsing, invoking the query layer, and formatting output. This separation allows the API and CLI to be tested against the same data logic.

## 7. Validation, tests, and reproducibility

The test suite runs entirely on committed fixtures. It must cover:

1. Pydantic rejection of malformed IDs, invalid date ranges, invalid enum values, and duplicate company ticker/exchange pairs.
2. Snapshot cross-reference checks: every relationship company and evidence ID exists; every evidence source exists; `confirmed` relationships include human-verified evidence.
3. Exact confidence-score boundary tests for source authority, one/two/three independent publishers, recency cutoffs, directness precedence, and type factors.
4. Company search, relationship filters, detail retrieval, network depth, and response metadata through FastAPI's test client.
5. `400` for an invalid `relationship_type`, invalid ISO date, `limit=101`, negative offset, and `depth=3`; `404` for a missing entity or relationship.
6. CLI output equivalence with the corresponding query-layer result and `validate` returning non-zero for a deliberately invalid fixture.
7. A representative confirmed supplier relationship, at least one relationship in every required category where evidence is available, and an explicitly uncertain or boundary case.

`README.md` documents installation, running the API, CLI examples, testing, snapshot selection, and known coverage limits. `docs/research-methodology.md` defines the evidence hierarchy, conclusion states, entity rules, relationship semantics, and scoring. `docs/data-update-guide.md` documents the manual collection and review sequence, including source restriction checks and how to create a new snapshot without overwriting old ones. `docs/ai-and-human-review.md` discloses any AI-assisted tasks and requires human validation for entity identity, source interpretation, quotations, relationship classification, and final conclusions.

## 8. Acceptance mapping

| Challenge requirement | Design response |
|---|---|
| Company/entity, evidence labels, scope and non-advice | Snapshot manifest, company contract, statuses, README and methodology. |
| Listed-company relationship coverage and direction | Typed edge roles and directions; documented category coverage. |
| Only lawful public sources | Source policy and manual review process; no crawler. |
| URLs, publisher, time, locator, and limitations | Source and evidence contracts. |
| 0–100 explainable score | Versioned deterministic formula and component-level output. |
| Reproducible GitHub delivery | Immutable local snapshot, fixtures, no runtime fetch requirement. |
| HTTP JSON and CLI | FastAPI endpoints and equivalent CLI commands. |
| Environment, test, and update instructions | README plus data-update guide. |
| Key and negative/boundary tests | Explicit offline test matrix. |
| AI usage and human judgment disclosure | Dedicated AI-and-human-review document. |

## 9. Decisions deliberately deferred

The first snapshot's exact counterparty roster, citations, and as-of date are research inputs, not fabricated design content. They will be added only after manual evidence review. Adding automatic source refresh, a web UI, user accounts, an external database, or graph analytics requires a new design decision because each would change the reproducibility and operational model.
