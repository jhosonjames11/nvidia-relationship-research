"""Read-only HTTP adaptation for an already-loaded research snapshot."""

from __future__ import annotations

from datetime import date
import os
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from swagger_ui_bundle import swagger_ui_path

from .models import Company, RelationshipStatus, RelationshipType
from .repository import SnapshotRepository


Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]
Depth = Annotated[int, Query(ge=1, le=2)]
Confidence = Annotated[int, Query(ge=0, le=100)]


def _validation_detail(error: RequestValidationError) -> str:
    return "; ".join(str(item["msg"]) for item in error.errors())


def _meta(repository: SnapshotRepository, **pagination: int) -> dict[str, Any]:
    manifest = repository.manifest
    return {
        "snapshot_id": manifest.snapshot_id,
        "as_of": manifest.as_of.isoformat(),
        "methodology_version": manifest.methodology_version,
        **pagination,
    }


def _response(repository: SnapshotRepository, data: Any, **pagination: int) -> dict[str, Any]:
    return {"meta": _meta(repository, **pagination), "data": data}


def _not_found(resource: str, identifier: str) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": f"{resource} '{identifier}' was not found"})


def _matches_company_query(company: Company, query: str | None) -> bool:
    if query is None or not query.strip():
        return True
    candidate_text = " ".join(
        (company.id, company.legal_name, company.ticker, company.exchange, *company.aliases)
    )
    return query.casefold().strip() in candidate_text.casefold()


def create_app(repository: SnapshotRepository) -> FastAPI:
    """Create an offline, read-only application for one immutable snapshot."""

    app = FastAPI(
        title="NVIDIA Relationship Research",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
    )
    app.mount("/docs/static", StaticFiles(directory=swagger_ui_path), name="swagger-ui-assets")

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        del request
        return JSONResponse(status_code=400, content={"detail": _validation_detail(exc)})

    @app.exception_handler(ValueError)
    async def repository_value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        del request
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.get("/docs", include_in_schema=False)
    def documentation() -> Any:
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} - Swagger UI",
            swagger_js_url="/docs/static/swagger-ui-bundle.js",
            swagger_css_url="/docs/static/swagger-ui.css",
            swagger_favicon_url="/docs/static/favicon-32x32.png",
        )

    @app.get("/health")
    def health() -> dict[str, Any]:
        return _response(
            repository,
            {
                "status": "ok",
                "counts": {
                    "companies": len(repository.company_by_id),
                    "relationships": len(repository.relationship_by_id),
                    "evidence": len(repository.evidence_by_id),
                    "sources": len(repository.source_by_id),
                },
            },
        )

    @app.get("/v1/companies")
    def companies(
        query: str | None = None,
        ticker: str | None = None,
        exchange: str | None = None,
        limit: Limit = 20,
        offset: Offset = 0,
    ) -> dict[str, Any]:
        results = [
            company
            for company in repository.company_by_id.values()
            if _matches_company_query(company, query)
            and (ticker is None or company.ticker.casefold() == ticker.casefold())
            and (exchange is None or company.exchange.casefold() == exchange.casefold())
        ]
        results.sort(key=lambda company: (company.legal_name.casefold(), company.id))
        total = len(results)
        return _response(
            repository,
            results[offset : offset + limit],
            limit=limit,
            offset=offset,
            total=total,
        )

    @app.get("/v1/relationships")
    def relationships(
        company_id: str | None = None,
        relationship_type: RelationshipType | None = None,
        direction: str | None = None,
        status: RelationshipStatus | None = None,
        as_of: date | None = None,
        min_confidence: Confidence = 0,
        limit: Limit = 20,
        offset: Offset = 0,
    ) -> dict[str, Any]:
        page = repository.list_relationships(
            company_id=company_id,
            relationship_type=relationship_type,
            direction=None if direction == "either" else direction,
            status=status,
            valid_on=as_of,
            min_confidence=min_confidence,
            limit=limit,
            offset=offset,
        )
        return _response(
            repository,
            page.items,
            limit=page.limit,
            offset=page.offset,
            total=page.total,
        )

    @app.get("/v1/relationships/{relationship_id}", response_model=None)
    def relationship_detail(relationship_id: str) -> dict[str, Any] | JSONResponse:
        relationship = repository.get_relationship(relationship_id)
        if relationship is None:
            return _not_found("relationship", relationship_id)
        return _response(repository, relationship)

    @app.get("/v1/network/{company_id}", response_model=None)
    def network(
        company_id: str,
        depth: Depth = 1,
        relationship_type: RelationshipType | None = None,
        status: RelationshipStatus | None = None,
        as_of: date | None = None,
        min_confidence: Confidence = 0,
    ) -> dict[str, Any] | JSONResponse:
        try:
            result = repository.network(
                company_id=company_id,
                depth=depth,
                relationship_type=relationship_type,
                status=status,
                valid_on=as_of,
                min_confidence=min_confidence,
            )
        except KeyError:
            return _not_found("company", company_id)
        return _response(repository, {"nodes": result.nodes, "edges": result.edges})

    @app.get("/v1/evidence/{evidence_id}", response_model=None)
    def evidence_detail(evidence_id: str) -> dict[str, Any] | JSONResponse:
        evidence = repository.get_evidence(evidence_id)
        if evidence is None:
            return _not_found("evidence", evidence_id)
        return _response(repository, evidence)

    return app


def create_default_app() -> FastAPI:
    """Create the read-only application from the configured local snapshot."""

    configured_path = os.environ.get("NVIDIA_RESEARCH_SNAPSHOT_PATH")
    snapshot_path = (
        Path(configured_path)
        if configured_path
        else Path(__file__).resolve().parents[2] / "data/snapshots/nvidia-2026-09-23"
    )
    return create_app(SnapshotRepository.from_directory(snapshot_path))


app = create_default_app()
