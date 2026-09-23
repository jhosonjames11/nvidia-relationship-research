"""Offline loading, validation, and querying for immutable research snapshots."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import MappingProxyType
from typing import Generic, Mapping, TypeVar

from pydantic import BaseModel, ConfigDict, ValidationError

from .models import (
    Company,
    Evidence,
    Relationship,
    RelationshipStatus,
    RelationshipType,
    SnapshotManifest,
    Source,
)
from .scoring import ScoreBreakdown, score_relationship


T = TypeVar("T")
ModelT = TypeVar("ModelT", bound=BaseModel)


class SnapshotValidationError(ValueError):
    """Raised when a local snapshot has invalid data or broken references."""

    def __init__(self, errors: tuple[str, ...]) -> None:
        self.errors = errors
        super().__init__("snapshot validation failed:\n" + "\n".join(errors))


@dataclass(frozen=True)
class ValidationReport:
    """The complete, non-throwing result of validating a snapshot directory."""

    errors: tuple[str, ...]
    manifest: SnapshotManifest | None
    companies: tuple[Company, ...]
    sources: tuple[Source, ...]
    evidence: tuple[Evidence, ...]
    relationships: tuple[Relationship, ...]

    @property
    def is_valid(self) -> bool:
        return not self.errors


class EvidenceDetail(Evidence):
    """Evidence enriched with the immutable source it cites."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: Source


class RelationshipDetail(Relationship):
    """A relationship with its score and traceable source evidence."""

    confidence_score: ScoreBreakdown
    evidence: tuple[EvidenceDetail, ...]


@dataclass(frozen=True)
class Page(Generic[T]):
    """A deterministic page of a filtered repository query."""

    items: tuple[T, ...]
    total: int
    limit: int
    offset: int


@dataclass(frozen=True)
class NetworkResult:
    """The nodes and qualifying relationship edges reached from a company."""

    nodes: tuple[Company, ...]
    edges: tuple[RelationshipDetail, ...]


def _format_model_error(filename: str, index: int | None, error: Exception) -> str:
    location = filename if index is None else f"{filename}[{index}]"
    return f"{location}: {error}"


def _read_json(snapshot_path: Path, filename: str, errors: list[str]) -> object | None:
    try:
        return json.loads((snapshot_path / filename).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{filename}: could not read valid JSON: {exc}")
        return None


def _parse_one(
    raw: object | None,
    filename: str,
    model: type[SnapshotManifest],
    errors: list[str],
) -> SnapshotManifest | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        errors.append(f"{filename}: expected a JSON object")
        return None
    try:
        return model.model_validate(raw)
    except ValidationError as exc:
        errors.append(_format_model_error(filename, None, exc))
        return None


def _parse_many(
    raw: object | None,
    filename: str,
    model: type[ModelT],
    errors: list[str],
) -> tuple[ModelT, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        errors.append(f"{filename}: expected a JSON array")
        return ()

    parsed: list[ModelT] = []
    for index, item in enumerate(raw):
        try:
            parsed.append(model.model_validate(item))
        except ValidationError as exc:
            errors.append(_format_model_error(filename, index, exc))
    return tuple(parsed)


def _index_unique(
    values: tuple[ModelT, ...], filename: str, errors: list[str]
) -> dict[str, ModelT]:
    indexed: dict[str, ModelT] = {}
    for value in values:
        identifier = str(getattr(value, "id"))
        if identifier in indexed:
            errors.append(f"{filename}: duplicate id '{identifier}'")
        else:
            indexed[identifier] = value
    return indexed


def validate_snapshot(path: Path) -> ValidationReport:
    """Validate all JSON and cross references without modifying the snapshot."""

    snapshot_path = Path(path)
    errors: list[str] = []
    manifest = _parse_one(
        _read_json(snapshot_path, "snapshot.json", errors),
        "snapshot.json",
        SnapshotManifest,
        errors,
    )
    companies = _parse_many(
        _read_json(snapshot_path, "companies.json", errors), "companies.json", Company, errors
    )
    sources = _parse_many(
        _read_json(snapshot_path, "sources.json", errors), "sources.json", Source, errors
    )
    evidence = _parse_many(
        _read_json(snapshot_path, "evidence.json", errors), "evidence.json", Evidence, errors
    )
    relationships = _parse_many(
        _read_json(snapshot_path, "relationships.json", errors),
        "relationships.json",
        Relationship,
        errors,
    )

    companies_by_id = _index_unique(companies, "companies.json", errors)
    sources_by_id = _index_unique(sources, "sources.json", errors)
    evidence_by_id = _index_unique(evidence, "evidence.json", errors)
    _index_unique(relationships, "relationships.json", errors)

    ticker_exchange_pairs: set[tuple[str, str]] = set()
    for company in companies:
        ticker_exchange = (company.ticker.casefold(), company.exchange.casefold())
        if ticker_exchange in ticker_exchange_pairs:
            errors.append(
                "companies.json: duplicate (ticker, exchange) pair "
                f"'{company.ticker}', '{company.exchange}'"
            )
        ticker_exchange_pairs.add(ticker_exchange)

    if manifest is not None and manifest.research_subject_company_id not in companies_by_id:
        errors.append(
            "snapshot.json: research_subject_company_id "
            f"'{manifest.research_subject_company_id}' is not in companies.json"
        )

    for item in evidence:
        if item.source_id not in sources_by_id:
            errors.append(
                f"evidence '{item.id}' references unknown source '{item.source_id}'"
            )

    for relationship in relationships:
        if relationship.from_company_id not in companies_by_id:
            errors.append(
                f"relationship '{relationship.id}' references unknown from_company_id "
                f"'{relationship.from_company_id}'"
            )
        if relationship.to_company_id not in companies_by_id:
            errors.append(
                f"relationship '{relationship.id}' references unknown to_company_id "
                f"'{relationship.to_company_id}'"
            )

        linked_evidence: list[Evidence] = []
        for evidence_id in relationship.evidence_ids:
            item = evidence_by_id.get(evidence_id)
            if item is None:
                errors.append(
                    f"relationship '{relationship.id}' references unknown evidence '{evidence_id}'"
                )
            else:
                linked_evidence.append(item)

        if relationship.status is RelationshipStatus.CONFIRMED and not any(
            item.human_verified for item in linked_evidence
        ):
            errors.append(
                f"confirmed relationship '{relationship.id}' needs human-verified evidence"
            )

        linked_sources = [
            sources_by_id[item.source_id]
            for item in linked_evidence
            if item.source_id in sources_by_id
        ]
        if not linked_sources:
            continue

        latest_evidence_date = max(source.published_at for source in linked_sources)
        if relationship.score_inputs.latest_evidence_date != latest_evidence_date:
            errors.append(
                f"relationship '{relationship.id}' score_inputs.latest_evidence_date "
                f"must equal {latest_evidence_date.isoformat()}"
            )

        independent_publisher_count = len({source.publisher for source in linked_sources})
        if relationship.score_inputs.independent_publisher_count != independent_publisher_count:
            errors.append(
                f"relationship '{relationship.id}' score_inputs.independent_publisher_count "
                f"must equal {independent_publisher_count}"
            )

        if manifest is not None and latest_evidence_date > manifest.as_of:
            errors.append(
                f"relationship '{relationship.id}' latest evidence date is after snapshot as_of"
            )

    return ValidationReport(
        errors=tuple(errors),
        manifest=manifest,
        companies=companies,
        sources=sources,
        evidence=evidence,
        relationships=relationships,
    )


class SnapshotRepository:
    """Read-only, in-memory indexes and deterministic queries for one snapshot."""

    def __init__(
        self,
        manifest: SnapshotManifest,
        company_by_id: Mapping[str, Company],
        source_by_id: Mapping[str, Source],
        evidence_by_id: Mapping[str, Evidence],
        relationship_by_id: Mapping[str, RelationshipDetail],
    ) -> None:
        self.manifest = manifest
        self.company_by_id = MappingProxyType(dict(company_by_id))
        self.source_by_id = MappingProxyType(dict(source_by_id))
        self.evidence_by_id = MappingProxyType(dict(evidence_by_id))
        self.relationship_by_id = MappingProxyType(dict(relationship_by_id))

    @classmethod
    def from_directory(cls, path: Path) -> "SnapshotRepository":
        """Load one local snapshot after all schema and reference checks pass."""

        report = validate_snapshot(path)
        if not report.is_valid:
            raise SnapshotValidationError(report.errors)
        if report.manifest is None:
            raise SnapshotValidationError(("snapshot.json: manifest is missing",))

        company_by_id = {item.id: item for item in report.companies}
        source_by_id = {item.id: item for item in report.sources}
        evidence_by_id = {item.id: item for item in report.evidence}
        relationship_by_id: dict[str, RelationshipDetail] = {}
        for relationship in report.relationships:
            score = score_relationship(
                relationship, evidence_by_id, source_by_id, report.manifest.as_of
            )
            linked_evidence = tuple(
                EvidenceDetail(
                    **item.model_dump(), source=source_by_id[item.source_id]
                )
                for evidence_id in relationship.evidence_ids
                for item in (evidence_by_id[evidence_id],)
            )
            relationship_by_id[relationship.id] = RelationshipDetail(
                **relationship.model_dump(), confidence_score=score, evidence=linked_evidence
            )
        return cls(
            report.manifest,
            company_by_id,
            source_by_id,
            evidence_by_id,
            relationship_by_id,
        )

    @staticmethod
    def _page(items: list[T], *, limit: int, offset: int) -> Page[T]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if offset < 0:
            raise ValueError("offset must be greater than or equal to 0")
        return Page(items=tuple(items[offset : offset + limit]), total=len(items), limit=limit, offset=offset)

    def search_companies(
        self, query: str | None = None, *, limit: int = 20, offset: int = 0
    ) -> Page[Company]:
        """Find companies by id, name, ticker, exchange, or alias."""

        query_normalized = query.casefold().strip() if query is not None else ""
        companies = list(self.company_by_id.values())
        if query_normalized:
            companies = [
                company
                for company in companies
                if query_normalized
                in " ".join(
                    (company.id, company.legal_name, company.ticker, company.exchange, *company.aliases)
                ).casefold()
            ]
        companies.sort(key=lambda company: (company.legal_name.casefold(), company.id))
        return self._page(companies, limit=limit, offset=offset)

    def list_relationships(
        self,
        *,
        company_id: str | None = None,
        relationship_type: RelationshipType | str | None = None,
        status: RelationshipStatus | str | None = None,
        direction: str | None = None,
        valid_on: date | None = None,
        min_confidence: int = 0,
        limit: int = 20,
        offset: int = 0,
    ) -> Page[RelationshipDetail]:
        """Filter relationship edges using snapshot-local data only."""

        if not 0 <= min_confidence <= 100:
            raise ValueError("min_confidence must be between 0 and 100")
        if relationship_type is not None:
            try:
                relationship_type = RelationshipType(relationship_type)
            except ValueError as exc:
                raise ValueError("relationship_type is invalid") from exc
        if status is not None:
            try:
                status = RelationshipStatus(status)
            except ValueError as exc:
                raise ValueError("status is invalid") from exc
        if direction not in (None, "inbound", "outbound"):
            raise ValueError("direction must be inbound or outbound")
        if direction is not None and company_id is None:
            raise ValueError("direction requires company_id")

        relationships = list(self.relationship_by_id.values())
        if company_id is not None:
            relationships = [
                item
                for item in relationships
                if company_id in (item.from_company_id, item.to_company_id)
            ]
        if relationship_type is not None:
            relationships = [
                item for item in relationships if item.relationship_type is relationship_type
            ]
        if status is not None:
            relationships = [item for item in relationships if item.status is status]
        if direction == "inbound":
            relationships = [
                item
                for item in relationships
                if item.directionality.value == "directed" and item.to_company_id == company_id
            ]
        elif direction == "outbound":
            relationships = [
                item
                for item in relationships
                if item.directionality.value == "directed" and item.from_company_id == company_id
            ]
        if valid_on is not None:
            relationships = [
                item
                for item in relationships
                if item.valid_from <= valid_on and (item.valid_to is None or valid_on <= item.valid_to)
            ]
        relationships = [
            item for item in relationships if item.confidence_score.total >= min_confidence
        ]
        relationships.sort(key=lambda item: (-item.confidence_score.total, item.id))
        return self._page(relationships, limit=limit, offset=offset)

    def get_relationship(self, relationship_id: str) -> RelationshipDetail | None:
        """Return one relationship detail, or ``None`` when it is absent."""

        return self.relationship_by_id.get(relationship_id)

    def get_evidence(self, evidence_id: str) -> EvidenceDetail | None:
        """Return one evidence item with its source, or ``None`` when absent."""

        item = self.evidence_by_id.get(evidence_id)
        if item is None:
            return None
        return EvidenceDetail(**item.model_dump(), source=self.source_by_id[item.source_id])

    def network(
        self,
        *,
        company_id: str,
        depth: int,
        min_confidence: int = 0,
        relationship_type: RelationshipType | str | None = None,
        status: RelationshipStatus | str | None = None,
        valid_on: date | None = None,
    ) -> NetworkResult:
        """Traverse qualifying snapshot edges up to the requested hop depth."""

        if company_id not in self.company_by_id:
            raise KeyError(company_id)
        if not 1 <= depth <= 2:
            raise ValueError("depth must be between 1 and 2")

        eligible_edges = self.list_relationships(
            relationship_type=relationship_type,
            status=status,
            valid_on=valid_on,
            min_confidence=min_confidence,
            limit=100,
        ).items
        visited_company_ids = {company_id}
        frontier = {company_id}
        edge_by_id: dict[str, RelationshipDetail] = {}
        for _ in range(depth):
            next_frontier: set[str] = set()
            for edge in eligible_edges:
                endpoints = {edge.from_company_id, edge.to_company_id}
                if not endpoints & frontier:
                    continue
                edge_by_id[edge.id] = edge
                next_frontier.update(endpoints - visited_company_ids)
            visited_company_ids.update(next_frontier)
            frontier = next_frontier
            if not frontier:
                break

        nodes = [self.company_by_id[item] for item in visited_company_ids]
        nodes.sort(key=lambda company: (company.legal_name.casefold(), company.id))
        edges = sorted(edge_by_id.values(), key=lambda item: (-item.confidence_score.total, item.id))
        return NetworkResult(nodes=tuple(nodes), edges=tuple(edges))
