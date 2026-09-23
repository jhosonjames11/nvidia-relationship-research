"""Offline command-line interface for immutable research snapshots."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .models import RelationshipStatus, RelationshipType
from .repository import SnapshotRepository, SnapshotValidationError, validate_snapshot


DEFAULT_SNAPSHOT_PATH = Path("data/snapshots/nvidia-2026-09-23")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="NVIDIA relationship research")
    parser.add_argument("--snapshot", type=Path, help="local snapshot directory")
    commands = parser.add_subparsers(dest="command", required=True)

    companies = commands.add_parser("companies")
    companies.add_argument("--query")
    companies.add_argument("--ticker")
    companies.add_argument("--exchange")
    _add_pagination(companies)

    relationships = commands.add_parser("relationships")
    relationships.add_argument("--company")
    relationships.add_argument("--type", choices=[item.value for item in RelationshipType])
    relationships.add_argument("--direction", choices=("inbound", "outbound", "either"))
    relationships.add_argument("--status", choices=[item.value for item in RelationshipStatus])
    relationships.add_argument("--as-of", type=date.fromisoformat)
    relationships.add_argument("--min-confidence", type=int, default=0)
    _add_pagination(relationships)

    relationship = commands.add_parser("relationship")
    relationship.add_argument("relationship_id")

    network = commands.add_parser("network")
    network.add_argument("company_id")
    network.add_argument("--depth", type=int, choices=(1, 2), default=1)
    network.add_argument("--type", choices=[item.value for item in RelationshipType])
    network.add_argument("--status", choices=[item.value for item in RelationshipStatus])
    network.add_argument("--as-of", type=date.fromisoformat)
    network.add_argument("--min-confidence", type=int, default=0)

    commands.add_parser("validate")
    return parser


def _add_pagination(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--offset", type=int, default=0)


def _snapshot_path(value: Path | None) -> Path:
    if value is not None:
        return value
    environment_value = os.environ.get("NVIDIA_RESEARCH_SNAPSHOT_PATH")
    return Path(environment_value) if environment_value else DEFAULT_SNAPSHOT_PATH


def _meta(repository: SnapshotRepository, **pagination: int) -> dict[str, Any]:
    manifest = repository.manifest
    return {
        "snapshot_id": manifest.snapshot_id,
        "as_of": manifest.as_of.isoformat(),
        "methodology_version": manifest.methodology_version,
        **pagination,
    }


def _model_data(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _model_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_model_data(item) for item in value]
    return value


def _print(payload: Any) -> None:
    print(json.dumps(_model_data(payload), ensure_ascii=False, indent=2, default=str))


def _response(repository: SnapshotRepository, data: Any, **pagination: int) -> dict[str, Any]:
    return {"meta": _meta(repository, **pagination), "data": data}


def _companies(repository: SnapshotRepository, arguments: argparse.Namespace) -> dict[str, Any]:
    first_page = repository.search_companies(arguments.query, limit=100, offset=0)
    results = list(first_page.items)
    for offset in range(100, first_page.total, 100):
        results.extend(repository.search_companies(arguments.query, limit=100, offset=offset).items)
    results = tuple(
        company
        for company in results
        if (arguments.ticker is None or company.ticker.casefold() == arguments.ticker.casefold())
        and (arguments.exchange is None or company.exchange.casefold() == arguments.exchange.casefold())
    )
    if not 1 <= arguments.limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    if arguments.offset < 0:
        raise ValueError("offset must be greater than or equal to 0")
    return _response(
        repository,
        results[arguments.offset : arguments.offset + arguments.limit],
        limit=arguments.limit,
        offset=arguments.offset,
        total=len(results),
    )


def _relationships(repository: SnapshotRepository, arguments: argparse.Namespace) -> dict[str, Any]:
    page = repository.list_relationships(
        company_id=arguments.company,
        relationship_type=arguments.type,
        direction=None if arguments.direction == "either" else arguments.direction,
        status=arguments.status,
        valid_on=arguments.as_of,
        min_confidence=arguments.min_confidence,
        limit=arguments.limit,
        offset=arguments.offset,
    )
    return _response(
        repository, page.items, limit=page.limit, offset=page.offset, total=page.total
    )


def _relationship(repository: SnapshotRepository, arguments: argparse.Namespace) -> dict[str, Any]:
    result = repository.get_relationship(arguments.relationship_id)
    if result is None:
        raise ValueError(f"relationship '{arguments.relationship_id}' was not found")
    return _response(repository, result)


def _network(repository: SnapshotRepository, arguments: argparse.Namespace) -> dict[str, Any]:
    try:
        result = repository.network(
            company_id=arguments.company_id,
            depth=arguments.depth,
            relationship_type=arguments.type,
            status=arguments.status,
            valid_on=arguments.as_of,
            min_confidence=arguments.min_confidence,
        )
    except KeyError as exc:
        raise ValueError(f"company '{arguments.company_id}' was not found") from exc
    return _response(repository, {"nodes": result.nodes, "edges": result.edges})


def _validate(snapshot_path: Path) -> int:
    report = validate_snapshot(snapshot_path)
    _print({"valid": report.is_valid, "errors": list(report.errors)})
    return 0 if report.is_valid else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    try:
        arguments = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)

    snapshot_path = _snapshot_path(arguments.snapshot)
    if arguments.command == "validate":
        return _validate(snapshot_path)

    try:
        repository = SnapshotRepository.from_directory(snapshot_path)
        handlers = {
            "companies": _companies,
            "relationships": _relationships,
            "relationship": _relationship,
            "network": _network,
        }
        _print(handlers[arguments.command](repository, arguments))
    except (SnapshotValidationError, ValueError, KeyError) as exc:
        _print({"detail": str(exc)})
        return 1
    return 0
