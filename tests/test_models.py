from datetime import date

import pytest
from pydantic import ValidationError

from nvidia_research.models import (
    Company,
    Directionality,
    Relationship,
    RelationshipStatus,
    RelationshipType,
    SnapshotManifest,
    SourceTier,
)


def test_company_requires_a_slug_id_and_exchange_ticker() -> None:
    company = Company(
        id="nvidia",
        legal_name="NVIDIA Corporation",
        ticker="NVDA",
        exchange="NASDAQ",
        country_or_region="US",
        aliases=["NVIDIA"],
    )
    assert company.id == "nvidia"

    with pytest.raises(ValidationError):
        Company(
            id="NVIDIA Corporation",
            legal_name="NVIDIA Corporation",
            ticker="NVDA",
            exchange="NASDAQ",
            country_or_region="US",
            aliases=[],
        )


def test_supplier_relationship_requires_supplier_and_buyer_roles() -> None:
    relationship = Relationship(
        id="rel-tsmc-nvidia-supplier",
        from_company_id="tsmc",
        to_company_id="nvidia",
        relationship_type=RelationshipType.SUPPLIER,
        from_role="supplier",
        to_role="buyer",
        directionality="directed",
        status="confirmed",
        summary="TSMC supplies manufacturing services to NVIDIA.",
        event_or_business_context="GPU manufacturing",
        valid_from=date(2025, 1, 1),
        valid_to=None,
        evidence_ids=["ev-tsmc"],
        score_inputs={"independent_publisher_count": 1, "latest_evidence_date": date(2025, 1, 15)},
    )
    assert relationship.relationship_type is RelationshipType.SUPPLIER

    with pytest.raises(ValidationError):
        Relationship(
            id="rel-tsmc-nvidia-supplier",
            from_company_id="tsmc",
            to_company_id="nvidia",
            relationship_type=RelationshipType.SUPPLIER,
            from_role="supplier",
            to_role="investee",
            directionality="directed",
            status="confirmed",
            summary="TSMC supplies manufacturing services to NVIDIA.",
            event_or_business_context="GPU manufacturing",
            valid_from=date(2025, 1, 1),
            valid_to=None,
            evidence_ids=["ev-tsmc"],
            score_inputs={"independent_publisher_count": 1, "latest_evidence_date": date(2025, 1, 15)},
        )


def relationship_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": "rel-tsmc-nvidia-supplier",
        "from_company_id": "tsmc",
        "to_company_id": "nvidia",
        "relationship_type": RelationshipType.SUPPLIER,
        "from_role": "supplier",
        "to_role": "buyer",
        "directionality": Directionality.DIRECTED,
        "status": RelationshipStatus.CONFIRMED,
        "summary": "TSMC supplies manufacturing services to NVIDIA.",
        "event_or_business_context": "GPU manufacturing",
        "valid_from": date(2025, 1, 1),
        "valid_to": None,
        "evidence_ids": ["ev-tsmc"],
        "score_inputs": {
            "independent_publisher_count": 1,
            "latest_evidence_date": date(2025, 1, 15),
        },
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("valid_to", date(2024, 12, 31)),
        ("evidence_ids", []),
        ("summary", ""),
        ("event_or_business_context", ""),
    ],
)
def test_relationship_rejects_invalid_required_content(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        Relationship(**relationship_payload(**{field: value}))


@pytest.mark.parametrize(
    ("relationship_type", "from_role", "to_role", "directionality"),
    [
        (RelationshipType.CUSTOMER, "customer", "seller", Directionality.DIRECTED),
        (RelationshipType.PARTNER, "partner", "partner", Directionality.UNDIRECTED),
        (RelationshipType.INVESTOR_OR_INVESTEE, "investor", "investee", Directionality.DIRECTED),
        (RelationshipType.PEER, "peer", "peer", Directionality.UNDIRECTED),
    ],
)
def test_relationship_accepts_each_exact_role_direction_pair(
    relationship_type: RelationshipType,
    from_role: str,
    to_role: str,
    directionality: Directionality,
) -> None:
    payload = relationship_payload(
        relationship_type=relationship_type,
        from_role=from_role,
        to_role=to_role,
        directionality=directionality,
        from_company_id="nvidia",
        to_company_id="tsmc",
    )
    relationship = Relationship(**payload)
    assert relationship.directionality is directionality


def test_undirected_relationship_requires_canonical_endpoint_order() -> None:
    payload = relationship_payload(
        relationship_type=RelationshipType.PEER,
        from_role="peer",
        to_role="peer",
        directionality=Directionality.UNDIRECTED,
        from_company_id="tsmc",
        to_company_id="nvidia",
    )
    with pytest.raises(ValidationError):
        Relationship(**payload)


def test_fixed_vocabularies_reject_unrecognized_values() -> None:
    assert SourceTier.ISSUER_OR_COUNTERPARTY == "issuer_or_counterparty"
    with pytest.raises(ValueError):
        RelationshipType("competitor")


def test_manifest_accepts_the_local_snapshot_boundary_contract() -> None:
    manifest = SnapshotManifest(
        snapshot_id="nvidia-2026-09-23",
        as_of=date(2026, 9, 23),
        methodology_version="1.0",
        research_subject_company_id="nvidia",
        research_boundary="Publicly accessible, manually verified listed-company relationships.",
    )
    assert manifest.research_subject_company_id == "nvidia"
