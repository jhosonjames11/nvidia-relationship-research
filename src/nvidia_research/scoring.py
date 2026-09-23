"""Pure, deterministic confidence scoring for relationship evidence."""

from datetime import date
from typing import Mapping

from pydantic import BaseModel, ConfigDict

from .models import Evidence, Relationship, Source


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
DIRECTNESS_SCORE = {
    "direct": 1.00,
    "inference_support": 0.60,
    "context_only": 0.25,
}
FORMULA_VERSION = "confidence-v1"


class ScoreBreakdown(BaseModel):
    """The score, its normalized components, and reproducible raw inputs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    formula_version: str
    components: dict[str, float]
    inputs: dict[str, object]
    total: int
    explanation: str


def score_recency(latest_evidence_date: date, as_of: date) -> float:
    """Return the recency component using explicit calendar-day cutoffs."""

    age_days = (as_of - latest_evidence_date).days
    if age_days < 0:
        raise ValueError("latest evidence date cannot be after as_of")
    if age_days <= 365:
        return 1.00
    if age_days <= 730:
        return 0.80
    if age_days <= 1460:
        return 0.60
    return 0.40


def _value(value: object) -> str:
    return str(getattr(value, "value", value))


def _corroboration(publisher_count: int) -> float:
    if publisher_count <= 0:
        raise ValueError("independent publisher count must be positive")
    if publisher_count == 1:
        return 0.40
    if publisher_count == 2:
        return 0.70
    return 1.00


def score_relationship(
    relationship: Relationship,
    evidence_by_id: Mapping[str, Evidence],
    source_by_id: Mapping[str, Source],
    as_of: date,
) -> ScoreBreakdown:
    """Calculate a relationship's evidence-support score without side effects."""

    evidence: list[Evidence] = []
    for evidence_id in relationship.evidence_ids:
        try:
            item = evidence_by_id[evidence_id]
        except KeyError as exc:
            raise ValueError(f"relationship references unknown evidence: {evidence_id}") from exc
        evidence.append(item)

    sources: list[Source] = []
    for item in evidence:
        try:
            source = source_by_id[item.source_id]
        except KeyError as exc:
            raise ValueError(f"evidence references unknown source: {item.source_id}") from exc
        sources.append(source)

    source_authority = max(SOURCE_AUTHORITY[_value(source.source_tier)] for source in sources)
    directness = max(DIRECTNESS_SCORE[_value(item.directness)] for item in evidence)
    publisher_count = relationship.score_inputs.independent_publisher_count
    corroboration = _corroboration(publisher_count)
    latest_date = relationship.score_inputs.latest_evidence_date
    recency = score_recency(latest_date, as_of)
    relationship_type = _value(relationship.relationship_type)
    try:
        type_verifiability = TYPE_VERIFIABILITY[relationship_type]
    except KeyError as exc:
        raise ValueError(f"unsupported relationship type: {relationship_type}") from exc

    components = {
        "source_authority": source_authority,
        "independent_corroboration": corroboration,
        "recency": recency,
        "directness": directness,
        "type_verifiability": type_verifiability,
    }
    weighted_sum = (
        0.30 * source_authority
        + 0.20 * corroboration
        + 0.20 * recency
        + 0.15 * directness
        + 0.15 * type_verifiability
    )
    total = round(100 * weighted_sum)
    evidence_dates = sorted(source.published_at for source in sources)
    currentness_note = (
        "The available evidence does not assert that this relationship continues today."
        if relationship.valid_to is not None
        else ""
    )
    explanation = (
        f"{relationship_type} relationship: source authority={source_authority:.2f}, "
        f"independent corroboration={corroboration:.2f} (publisher count: {publisher_count}), "
        f"recency={recency:.2f} (latest evidence date: {latest_date.isoformat()}), "
        f"directness={directness:.2f}, type verifiability={type_verifiability:.2f}. "
        f"Linked evidence dates: {', '.join(item.isoformat() for item in evidence_dates)}. "
        f"Weighted evidence-support confidence score: {total}/100. {currentness_note}"
    )
    return ScoreBreakdown(
        formula_version=FORMULA_VERSION,
        components=components,
        inputs={
            "evidence_dates": tuple(evidence_dates),
            "independent_publisher_count": publisher_count,
            "latest_evidence_date": latest_date,
            "as_of": as_of,
            "relationship_type": relationship_type,
            "source_tiers": tuple(_value(source.source_tier) for source in sources),
            "directness_values": tuple(_value(item.directness) for item in evidence),
        },
        total=total,
        explanation=explanation,
    )
