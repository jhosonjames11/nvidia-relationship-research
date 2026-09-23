"""Immutable Pydantic contracts for one local research snapshot."""

from datetime import date, datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints, model_validator


Slug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")]
NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class RelationshipType(str, Enum):
    SUPPLIER = "supplier"
    CUSTOMER = "customer"
    PARTNER = "partner"
    INVESTOR_OR_INVESTEE = "investor_or_investee"
    PEER = "peer"


class RelationshipStatus(str, Enum):
    CONFIRMED = "confirmed"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


class SourceTier(str, Enum):
    REGULATOR_OR_EXCHANGE = "regulator_or_exchange"
    ISSUER_OR_COUNTERPARTY = "issuer_or_counterparty"
    OFFICIAL_PUBLIC_BODY = "official_public_body"
    INDEPENDENT_REPORTING = "independent_reporting"
    OTHER_PUBLIC = "other_public"


class Directness(str, Enum):
    DIRECT = "direct"
    INFERENCE_SUPPORT = "inference_support"
    CONTEXT_ONLY = "context_only"


class Directionality(str, Enum):
    DIRECTED = "directed"
    UNDIRECTED = "undirected"


ROLE_PAIRS = {
    RelationshipType.SUPPLIER: ("supplier", "buyer", Directionality.DIRECTED),
    RelationshipType.CUSTOMER: ("customer", "seller", Directionality.DIRECTED),
    RelationshipType.PARTNER: ("partner", "partner", Directionality.UNDIRECTED),
    RelationshipType.INVESTOR_OR_INVESTEE: ("investor", "investee", Directionality.DIRECTED),
    RelationshipType.PEER: ("peer", "peer", Directionality.UNDIRECTED),
}


class SnapshotModel(BaseModel):
    """Base model that prevents mutation and rejects undeclared snapshot fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class SnapshotManifest(SnapshotModel):
    snapshot_id: Slug
    as_of: date
    generated_at: datetime
    methodology_version: NonEmptyText
    research_subject_company_id: Slug
    research_boundary: NonEmptyText


class Company(SnapshotModel):
    id: Slug
    legal_name: NonEmptyText
    ticker: NonEmptyText
    exchange: NonEmptyText
    country_or_region: NonEmptyText
    aliases: tuple[NonEmptyText, ...] = ()


class Source(SnapshotModel):
    id: Slug
    title: NonEmptyText
    url: HttpUrl
    publisher: NonEmptyText
    published_at: date
    accessed_at: date
    source_tier: SourceTier
    access_limitations: NonEmptyText


class Evidence(SnapshotModel):
    id: Slug
    source_id: Slug
    locator: NonEmptyText
    excerpt: NonEmptyText
    directness: Directness
    human_verified: bool
    reviewed_at: date


class ScoreInputs(SnapshotModel):
    independent_publisher_count: Annotated[int, Field(ge=1)]
    latest_evidence_date: date


class Relationship(SnapshotModel):
    id: Slug
    from_company_id: Slug
    to_company_id: Slug
    relationship_type: RelationshipType
    from_role: NonEmptyText
    to_role: NonEmptyText
    directionality: Directionality
    status: RelationshipStatus
    summary: NonEmptyText
    event_or_business_context: NonEmptyText
    valid_from: date
    valid_to: date | None
    evidence_ids: Annotated[tuple[Slug, ...], Field(min_length=1)]
    score_inputs: ScoreInputs

    @model_validator(mode="after")
    def validate_relationship_invariants(self) -> "Relationship":
        expected_from_role, expected_to_role, expected_directionality = ROLE_PAIRS[self.relationship_type]
        if (self.from_role, self.to_role, self.directionality) != (
            expected_from_role,
            expected_to_role,
            expected_directionality,
        ):
            raise ValueError(
                "relationship roles and directionality must match the relationship type"
            )
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValueError("valid_to must be on or after valid_from")
        if self.from_company_id == self.to_company_id:
            raise ValueError("relationship endpoints must identify different companies")
        if (
            self.directionality is Directionality.UNDIRECTED
            and self.from_company_id >= self.to_company_id
        ):
            raise ValueError("undirected relationship endpoints must be in lexicographic order")
        return self
