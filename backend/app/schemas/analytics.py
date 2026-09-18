from datetime import date, datetime
from typing import Any, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Filters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_date: date | None = None
    end_date: date | None = None
    zone_id: int | None = Field(default=None, ge=1, le=265)

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        for value in (self.start_date, self.end_date):
            if value and not 2009 <= value.year <= 2100:
                raise ValueError("Dates must be between 2009 and 2100")
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")
        return self


class PageFilters(Filters):
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class ZoneFilters(PageFilters):
    direction: Literal["pickup", "dropoff"] = "pickup"
    sort: Literal["trip_count", "total_revenue"] = "trip_count"
    borough: str | None = Field(default=None, max_length=50)


class Metrics(BaseModel):
    total_trips: int
    total_revenue: float
    average_fare: float | None
    average_trip_distance: float | None
    average_duration_minutes: float | None


class Zone(BaseModel):
    zone_id: int
    zone_name: str
    borough: str
    service_zone: str | None = None


class Summary(Metrics):
    start_date: date | None
    end_date: date | None
    busiest_pickup_zone: Zone | None


class TrendPoint(Metrics):
    period: datetime


class TrendPage(BaseModel):
    items: list[TrendPoint]
    total: int
    limit: int
    offset: int


class ZonePerformance(Zone, Metrics):
    pass


class ZonePage(BaseModel):
    items: list[ZonePerformance]
    total: int
    limit: int
    offset: int


class ZoneDetail(Zone):
    pickups: Metrics
    dropoffs: Metrics


class Payment(BaseModel):
    payment_type: int
    payment_name: str
    trip_count: int
    total_revenue: float
    average_fare: float | None


class PaymentResponse(BaseModel):
    items: list[Payment]


class Forecast(BaseModel):
    hour_at: datetime
    pickup_zone_id: int
    predicted_count: float
    model_version: str


class ForecastPage(BaseModel):
    items: list[Forecast]
    total: int
    limit: int
    offset: int


class ModelRun(BaseModel):
    id: UUID
    model_version: str
    started_at: datetime
    finished_at: datetime | None
    training_start: datetime | None
    training_end: datetime | None
    test_start: datetime | None
    test_end: datetime | None
    features: list[str]
    metrics: dict[str, Any]


class LatestModel(BaseModel):
    model: ModelRun | None


class LoadBatch(BaseModel):
    id: UUID
    source_file: str
    status: str
    rows_read: int
    rows_accepted: int
    rows_rejected: int
    duplicate_rows: int
    started_at: datetime
    finished_at: datetime | None
    failure_message: str | None


class PipelineRun(BaseModel):
    id: UUID
    status: str
    source_year: int | None
    source_month: int | None
    started_at: datetime
    finished_at: datetime | None
    duration_seconds: float
    task_states: dict[str, str]
    failure_message: str | None
    load_batch: LoadBatch | None = None


class RunPage(BaseModel):
    latest_successful_load: LoadBatch | None
    items: list[PipelineRun]
    total: int
    limit: int
    offset: int


class IngestAccepted(BaseModel):
    run_id: UUID
    status: Literal["queued"] = "queued"


class Health(BaseModel):
    status: str
    database: str
    warehouse: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str | None = None
    details: list[dict[str, Any]] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    error: ErrorDetail
