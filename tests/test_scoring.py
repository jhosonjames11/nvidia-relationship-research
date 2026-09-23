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
        source_tier="issuer_or_counterparty", directness="direct",
        relationship_type="supplier", publisher_count=1,
        latest_evidence_date=date(2026, 9, 23),
    ))
    assert breakdown.total == 85
    assert breakdown.components["source_authority"] == 0.9
    assert breakdown.components["independent_corroboration"] == 0.4


def test_three_publishers_and_context_only_evidence_are_explained(score_case) -> None:
    breakdown = score_relationship(**score_case(
        source_tier="regulator_or_exchange", directness="context_only",
        relationship_type="peer", publisher_count=3,
        latest_evidence_date=date(2020, 1, 1),
    ))
    assert breakdown.components["independent_corroboration"] == 1.0
    assert breakdown.components["directness"] == 0.25
    assert "peer" in breakdown.explanation
    assert "2020-01-01" in breakdown.explanation
    assert "publisher count: 3" in breakdown.explanation


def test_directness_uses_strongest_evidence(score_case) -> None:
    case = score_case(
        source_tier="other_public", directness="context_only",
        relationship_type="customer", publisher_count=2,
        latest_evidence_date=date(2026, 1, 1),
    )
    stronger = Evidence(
        id="ev-direct", source_id="src-score", locator="page 2", excerpt="Direct.",
        directness="direct", human_verified=True, reviewed_at=date(2026, 9, 23),
    )
    case["relationship"] = case["relationship"].model_copy(update={"evidence_ids": ("ev-score", "ev-direct")})
    case["evidence_by_id"][stronger.id] = stronger
    result = score_relationship(**case)
    assert result.components["directness"] == 1.0


def test_zero_publishers_are_rejected(score_case) -> None:
    with pytest.raises(ValueError):
        score_relationship(**score_case(
            source_tier="other_public", directness="direct",
            relationship_type="supplier", publisher_count=0,
            latest_evidence_date=date(2026, 1, 1),
        ))
