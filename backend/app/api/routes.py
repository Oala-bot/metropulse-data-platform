import secrets
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Security
from fastapi.security import APIKeyHeader
from sqlalchemy import Connection

from backend.app.database.session import database
from backend.app.schemas.analytics import (
    Filters,
    ForecastPage,
    IngestAccepted,
    LatestModel,
    PageFilters,
    PaymentResponse,
    PipelineRun,
    RunPage,
    Summary,
    TrendPage,
    ZoneDetail,
    ZoneFilters,
    ZonePage,
)
from backend.app.services import analytics, pipeline

router = APIRouter(prefix="/api/v1")
DB = Annotated[Connection, Depends(database)]
key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_admin(request: Request, api_key: Annotated[str | None, Security(key_header)]) -> None:
    expected = request.app.state.settings.admin_api_key
    if expected is None or not expected.get_secret_value():
        raise HTTPException(503, "Administrative ingestion is disabled; configure ADMIN_API_KEY")
    if api_key is None or not secrets.compare_digest(
        api_key.encode(), expected.get_secret_value().encode()
    ):
        raise HTTPException(401, "Invalid or missing API key")


@router.get("/summary", response_model=Summary)
def get_summary(db: DB, filters: Annotated[Filters, Query()]) -> Summary:
    return Summary.model_validate(analytics.summary(db, filters))


@router.get("/trends/hourly", response_model=TrendPage)
def get_hourly(db: DB, filters: Annotated[PageFilters, Query()]) -> TrendPage:
    return TrendPage.model_validate(analytics.trends(db, filters, hourly=True))


@router.get("/trends/daily", response_model=TrendPage)
def get_daily(db: DB, filters: Annotated[PageFilters, Query()]) -> TrendPage:
    return TrendPage.model_validate(analytics.trends(db, filters, hourly=False))


@router.get("/zones/top", response_model=ZonePage)
def get_zones(db: DB, filters: Annotated[ZoneFilters, Query()]) -> ZonePage:
    return ZonePage.model_validate(analytics.zones(db, filters))


@router.get("/zones/{zone_id}", response_model=ZoneDetail)
def get_zone(
    db: DB, zone_id: Annotated[int, Path(ge=1, le=265)], filters: Annotated[Filters, Query()]
) -> ZoneDetail:
    if filters.zone_id is not None and filters.zone_id != zone_id:
        raise HTTPException(422, "Query zone_id must match the path zone_id")
    result = analytics.zone_detail(db, zone_id, filters)
    if result is None:
        raise HTTPException(404, "Zone not found")
    return ZoneDetail.model_validate(result)


@router.get("/payment-types", response_model=PaymentResponse)
def get_payments(db: DB, filters: Annotated[Filters, Query()]) -> PaymentResponse:
    return PaymentResponse.model_validate(analytics.payments(db, filters))


@router.get("/forecasts", response_model=ForecastPage)
def get_forecasts(db: DB, filters: Annotated[PageFilters, Query()]) -> ForecastPage:
    return ForecastPage.model_validate(analytics.forecasts(db, filters))


@router.get("/models/latest", response_model=LatestModel)
def get_latest_model(db: DB) -> LatestModel:
    return LatestModel.model_validate(analytics.latest_model(db))


@router.get("/pipeline-runs", response_model=RunPage)
def get_runs(
    db: DB,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RunPage:
    return RunPage.model_validate(pipeline.list_runs(db, limit, offset))


@router.get("/pipeline-runs/{run_id}", response_model=PipelineRun)
def get_run(run_id: UUID, db: DB) -> PipelineRun:
    result = pipeline.get_run(db, run_id)
    if result is None:
        raise HTTPException(404, "Pipeline run not found")
    return PipelineRun.model_validate(result)


@router.post(
    "/admin/ingest/{year}/{month}",
    response_model=IngestAccepted,
    status_code=202,
    dependencies=[Depends(require_admin)],
)
def start_ingestion(
    request: Request,
    db: DB,
    year: Annotated[int, Path(ge=2025, le=datetime.now(UTC).year)],
    month: Annotated[int, Path(ge=1, le=12)],
) -> IngestAccepted:
    try:
        run_id = pipeline.enqueue(db, year, month, request.app.state.settings)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from None
    except OSError:
        raise HTTPException(503, "Could not start ingestion worker") from None
    return IngestAccepted(run_id=run_id)
