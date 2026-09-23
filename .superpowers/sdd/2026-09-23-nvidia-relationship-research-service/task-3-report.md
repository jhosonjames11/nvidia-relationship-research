# Task 3 implementation report

## Changes

- Added `src/nvidia_research/scoring.py` with pure deterministic scoring.
- Added immutable `ScoreBreakdown` output carrying formula version, normalized components, raw inputs, total, and explanation.
- Implemented the exact source-authority values, relationship-type factors, publisher-count scale, explicit 365/730/1460 day cutoffs, strongest-directness precedence, and 30/20/20/15/15 formula weights from the brief.
- Explanations include relationship type, every component, evidence dates, publisher count, latest evidence date, score, and the non-currentness caveat for ended relationships.
- Added focused tests for recency boundaries, the 85-point baseline, three-publisher/context-only scoring and explanation, directness precedence, and zero-publisher rejection.

## Files

- `src/nvidia_research/scoring.py`
- `tests/test_scoring.py`

## RED/GREEN evidence

RED: Before implementation, `python -m pytest tests/test_scoring.py -q` failed during collection with `ModuleNotFoundError: No module named 'nvidia_research.scoring'`.

GREEN: After implementation, the focused suite passed: `5 passed in 0.06s`.

## Commands and results

- `python -m pytest tests/test_scoring.py -q` — 5 passed.
- `python -m pytest -q` — 21 passed.
- `git diff --check` — passed with no whitespace errors.
- Commit: `ab7d0da feat: add explainable confidence scoring`.

## Self-review

- Scoring has no I/O or network behavior and depends only on its arguments.
- Missing evidence/source references produce explicit `ValueError`s.
- Source authority and directness use the strongest linked values; publisher count zero is rejected.
- Inputs are retained in the result so later repository/API layers can audit the calculation.

## Concerns

- `score_inputs` consistency with linked source publishers and latest publication date remains a repository validation responsibility for Task 4.

## Review fix

The review identified that `ScoreBreakdown.inputs` did not retain enough raw data to reproduce the score. The scorer now includes `as_of`, relationship type, all linked source-tier values, and all linked evidence directness values alongside the existing evidence dates, publisher count, and latest evidence date. The unused `Directness` import was removed. A focused assertion test covers these audit inputs.

RED: The new assertions initially failed with `KeyError: 'as_of'` (`1 failed, 4 passed`).

GREEN: `python -m pytest tests/test_scoring.py -q` — 5 passed; `python -m pytest -q` — 21 passed; `git diff --check` passed.
