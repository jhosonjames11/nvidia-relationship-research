# Data update guide

Snapshots are immutable, local research releases. An update creates a new directory under `data/snapshots/`; it never edits an existing snapshot.

Use this required sequence:

1. Choose a new, unique snapshot ID and its ISO-8601 as-of date.
2. Collect only permitted, lawfully accessible public sources, following the source hierarchy and access restrictions in the [research methodology](research-methodology.md). Do not use automated browsing or bypass access controls.
3. Verify each entity's legal name, ticker, exchange, and stable ID before recording a relationship.
4. Create the new `data/snapshots/<snapshot_id>/` directory and write its `snapshot.json`, `companies.json`, `sources.json`, `evidence.json`, and `relationships.json` records. Include source metadata, precise evidence locators, short necessary excerpts, relationship roles and dates, conclusion state, and score inputs derived from the linked evidence.
5. Run `nvidia-research --snapshot data/snapshots/<snapshot_id> validate` and correct every reported error.
6. Run `python -m pytest -q` without network access.
7. Obtain a human audit of entity identity, lawful source access, quotations and locators, relationship classification and timing, score inputs, and conclusion wording. Record the dated outcome in [the review record](ai-and-human-review.md).
8. Add the new snapshot directory to version control without editing the old snapshot directory.

The runtime only reads the selected snapshot; it does not refresh sources. Preserve source access limitations in the records so later reviewers can understand what was reviewed.
