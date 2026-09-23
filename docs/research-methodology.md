# Research methodology

## Scope and entity rules

This service records versioned, manually verified public-source research about NVIDIA's relationships with listed companies. NVIDIA and every counterparty are identified by a stable internal ID plus legal name, ticker, and exchange metadata; aliases support search only and do not establish identity. The snapshot has a declared `as_of` date and does not make claims outside its evidence and time bounds.

Only legally accessible public materials may be used. The repository keeps source metadata and short, necessary fair-use excerpts, not complete third-party reports or PDFs. Collection must not bypass robots rules, authentication, paywalls, CAPTCHAs, rate limits, or site terms.

## Source hierarchy

Researchers manually review permitted sources in this preferred order:

1. Regulator and exchange filings.
2. NVIDIA or counterparty annual reports, investor-relations pages, and official releases.
3. Official government or regulator publications.
4. Reputable independent reporting when primary materials do not establish the requested fact.

Every source records its publisher, canonical URL, publication date, access date, source tier, and known access restrictions. Evidence records identify a source, locator, short excerpt, directness, human-verification status, and review date.

## Conclusion states

- `confirmed`: a directly relevant, manually verified evidence item supports the defined relationship.
- `inferred`: the relation is a transparent, limited inference from stated facts; its explanation names the inference and its uncertainty.
- `unknown`: available material is insufficient, ambiguous, or conflicting; no positive relationship conclusion is made.

Only `confirmed` records must contain at least one evidence record marked `human_verified: true`. Uncertain evidence is not promoted to `confirmed` merely to fill a category.

## Relationship direction and roles

The edge direction represents the stated role, not an arbitrary display convention.

| `relationship_type` | `from_role` | `to_role` | Direction |
| --- | --- | --- | --- |
| `supplier` | supplier | buyer | supplier → buyer |
| `customer` | customer | seller | customer → seller |
| `partner` | partner | partner | undirected |
| `investor_or_investee` | investor | investee | investor → investee |
| `peer` | peer | peer | undirected |

For undirected relations, company IDs are stored in lexicographic order to prevent duplicate edges. `valid_to: null` means the available evidence does not establish an end date; it does not assert the relationship continues today. Summaries must not add revenue, volume, exclusivity, causation, customer status, or commercial importance unsupported by the cited material.

## Confidence score

Confidence is calculated at load time from the evidence and is never an unverified hand-entered total:

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
- `independent_corroboration`: `0.40` for one distinct publisher, `0.70` for two, and `1.00` for three or more. Multiple URLs from the same publisher count once; syndicated copies are treated as the origin publisher.
- `recency`: calculated from `as_of - latest_evidence_date`: `1.00` at 12 months or fewer, `0.80` at 13–24 months, `0.60` at 25–48 months, and `0.40` above 48 months. A relationship with a non-null `valid_to` does not receive a currentness assertion in the explanation.
- `directness`: `1.00` when at least one record is `direct`, `0.60` when the strongest record is `inference_support`, otherwise `0.25`.
- `type_verifiability`: `1.00` for `supplier`, `customer`, and `investor_or_investee`; `0.85` for `partner`; `0.75` for `peer`. This reflects only how readily the category can be verified.

Confidence measures support for the classification, not the economic importance, commercial significance, or investment value of a relationship. It is not investment advice.
