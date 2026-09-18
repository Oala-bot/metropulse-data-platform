from typing import Any

from sqlalchemy import Connection, text

from backend.app.schemas.analytics import Filters, PageFilters, ZoneFilters

METRICS = """
    coalesce(sum(trip_count), 0)::bigint as total_trips,
    coalesce(sum(total_revenue), 0)::double precision as total_revenue,
    (sum(total_fare) / nullif(sum(trip_count), 0))::double precision as average_fare,
    sum(total_distance) / nullif(sum(trip_count), 0) as average_trip_distance,
    sum(total_duration_seconds) / nullif(sum(trip_count), 0) / 60 as average_duration_minutes
"""


def conditions(date_column: str = "trip_date", zone_column: str = "pickup_zone_id") -> str:
    return f"""
        (cast(:start_date as date) IS NULL OR {date_column} >= cast(:start_date as date))
        AND (cast(:end_date as date) IS NULL OR
            {date_column} < cast(:end_date as date) + interval '1 day')
        AND (cast(:zone_id as integer) IS NULL OR {zone_column} = :zone_id)
    """


def summary(connection: Connection, filters: Filters) -> dict[str, Any]:
    params = filters.model_dump()
    row = (
        connection.execute(
            text(f"""
        SELECT {METRICS}, min(trip_date) AS start_date, max(trip_date) AS end_date
        FROM analytics.mart_trip_summary_daily WHERE {conditions()}
    """),
            params,
        )
        .mappings()
        .one()
    )
    busiest = (
        connection.execute(
            text(f"""
        SELECT z.* FROM analytics.dim_zone z JOIN (
            SELECT pickup_zone_id, sum(trip_count) AS trips
            FROM analytics.mart_trip_summary_daily WHERE {conditions()}
            GROUP BY pickup_zone_id ORDER BY trips DESC, pickup_zone_id LIMIT 1
        ) b ON z.zone_id = b.pickup_zone_id
    """),
            params,
        )
        .mappings()
        .first()
    )
    return dict(row) | {"busiest_pickup_zone": dict(busiest) if busiest else None}


def trends(connection: Connection, filters: PageFilters, hourly: bool) -> dict[str, Any]:
    table = "agg_zone_hour" if hourly else "mart_trip_summary_daily"
    column = "pickup_hour" if hourly else "trip_date"
    base = f"""SELECT {column}::timestamp AS period, {METRICS}
        FROM analytics.{table} WHERE {conditions(column)} GROUP BY {column}"""
    params = filters.model_dump()
    total = connection.execute(text(f"SELECT count(*) FROM ({base}) grouped"), params).scalar_one()
    rows = connection.execute(text(base + " ORDER BY period LIMIT :limit OFFSET :offset"), params)
    return {
        "items": [dict(r) for r in rows.mappings()],
        "total": total,
        "limit": filters.limit,
        "offset": filters.offset,
    }


def zones(connection: Connection, filters: ZoneFilters) -> dict[str, Any]:
    where = (
        conditions("p.trip_date", "p.zone_id")
        + """
        AND p.direction = :direction
        AND (cast(:borough as text) IS NULL OR z.borough = :borough)
    """
    )
    base = f"""SELECT z.zone_id, z.zone_name, z.borough, z.service_zone, {METRICS}
        FROM analytics.mart_zone_performance p
        JOIN analytics.dim_zone z ON z.zone_id = p.zone_id
        WHERE {where} GROUP BY z.zone_id, z.zone_name, z.borough, z.service_zone"""
    params = filters.model_dump()
    total = connection.execute(text(f"SELECT count(*) FROM ({base}) grouped"), params).scalar_one()
    order = "total_trips" if filters.sort == "trip_count" else "total_revenue"
    rows = connection.execute(
        text(base + f" ORDER BY {order} DESC, zone_id LIMIT :limit OFFSET :offset"), params
    )
    return {
        "items": [dict(r) for r in rows.mappings()],
        "total": total,
        "limit": filters.limit,
        "offset": filters.offset,
    }


def zone_detail(connection: Connection, zone_id: int, filters: Filters) -> dict[str, Any] | None:
    zone = (
        connection.execute(
            text("SELECT * FROM analytics.dim_zone WHERE zone_id=:id"), {"id": zone_id}
        )
        .mappings()
        .first()
    )
    if zone is None:
        return None
    params = filters.model_dump() | {"zone_id": zone_id}
    result = dict(zone)
    for direction, key in [("pickup", "pickups"), ("dropoff", "dropoffs")]:
        row = (
            connection.execute(
                text(f"""
            SELECT {METRICS} FROM analytics.mart_zone_performance
            WHERE {conditions(zone_column="zone_id")} AND direction=:direction
        """),
                params | {"direction": direction},
            )
            .mappings()
            .one()
        )
        result[key] = dict(row)
    return result


def payments(connection: Connection, filters: Filters) -> dict[str, Any]:
    rows = connection.execute(
        text(f"""
        SELECT p.payment_type, d.payment_name, sum(trip_count)::bigint AS trip_count,
            sum(total_revenue)::double precision AS total_revenue,
            (sum(total_fare) / nullif(sum(trip_count),0))::double precision AS average_fare
        FROM analytics.mart_payment_analysis p
        JOIN analytics.dim_payment_type d USING(payment_type)
        WHERE {conditions()} GROUP BY p.payment_type, d.payment_name ORDER BY p.payment_type
    """),
        filters.model_dump(),
    )
    return {"items": [dict(r) for r in rows.mappings()]}


def forecasts(connection: Connection, filters: PageFilters) -> dict[str, Any]:
    base = f"""SELECT f.hour_at, f.pickup_zone_id, f.predicted_count, m.model_version
        FROM forecast_zone_hour f JOIN model_run m ON m.id = f.model_run_id
        WHERE f.model_run_id = (
            SELECT id FROM model_run WHERE status='succeeded'
            ORDER BY finished_at DESC NULLS LAST, started_at DESC, id LIMIT 1
        ) AND {conditions("f.hour_at", "f.pickup_zone_id")}"""
    params = filters.model_dump()
    total = connection.execute(
        text(f"SELECT count(*) FROM ({base}) forecasts"), params
    ).scalar_one()
    rows = connection.execute(
        text(base + " ORDER BY hour_at, pickup_zone_id LIMIT :limit OFFSET :offset"), params
    )
    return {
        "items": [dict(r) for r in rows.mappings()],
        "total": total,
        "limit": filters.limit,
        "offset": filters.offset,
    }


def latest_model(connection: Connection) -> dict[str, Any]:
    row = (
        connection.execute(
            text("""SELECT * FROM model_run WHERE status='succeeded'
        ORDER BY finished_at DESC NULLS LAST, started_at DESC, id LIMIT 1""")
        )
        .mappings()
        .first()
    )
    return {"model": dict(row) if row else None}
