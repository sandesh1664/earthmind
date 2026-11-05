"""M02 persistence contracts, sharing the single M01 SQLAlchemy base."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from geoalchemy2 import Geometry
from geoalchemy2.elements import WKBElement
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from earthmind_api.models import Base


class Identity:
    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )


class Created:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Updated:
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


def geometry_constraint(column: str, kind: str, name: str) -> CheckConstraint:
    return CheckConstraint(
        f"ST_SRID({column}) = 4326 AND ST_NDims({column}) = 2 "
        f"AND GeometryType({column}) = '{kind}' AND NOT ST_IsEmpty({column}) "
        f"AND ST_IsValid({column}) AND ST_NPoints({column}) <= 10000 "
        f"AND ST_XMin(Box3D({column})) >= -180 "
        f"AND ST_XMax(Box3D({column})) <= 180 AND ST_YMin(Box3D({column})) >= -90 "
        f"AND ST_YMax(Box3D({column})) <= 90",
        name=name,
    )


def checksum_constraint(column: str, name: str) -> CheckConstraint:
    return CheckConstraint(f"{column} ~ '^[0-9a-f]{{64}}$'", name=name)


class User(Identity, Created, Updated, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "email = lower(email) AND position('@' in email) > 1", name="ck_users_email"
        ),
        CheckConstraint(
            "password_hash LIKE '$argon2id$%' OR password_hash LIKE '$scrypt$%' "
            "OR password_hash LIKE '$2b$%'",
            name="ck_users_password_hash",
        ),
        CheckConstraint("role IN ('admin','researcher','viewer')", name="ck_users_role"),
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, server_default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class Region(Identity, Created, Updated, Base):
    __tablename__ = "regions"
    __table_args__ = (
        CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="ck_regions_slug"),
        CheckConstraint("length(name) > 0", name="ck_regions_name"),
        CheckConstraint("country_code ~ '^[A-Z]{2}$'", name="ck_regions_country"),
        CheckConstraint("area_km2 > 0 AND area_km2 < 'Infinity'::float8", name="ck_regions_area"),
        geometry_constraint("boundary", "MULTIPOLYGON", "ck_regions_boundary"),
        geometry_constraint("centroid", "POINT", "ck_regions_centroid"),
        CheckConstraint("ST_Covers(boundary, centroid)", name="ck_regions_centroid_covered"),
        Index("ix_regions_boundary_gist", "boundary", postgresql_using="gist"),
    )
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    emirate: Mapped[str | None] = mapped_column(String(100))
    timezone: Mapped[str] = mapped_column(String(100), nullable=False)
    boundary: Mapped[WKBElement] = mapped_column(
        Geometry("MULTIPOLYGON", srid=4326, spatial_index=False), nullable=False
    )
    centroid: Mapped[WKBElement] = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=False),
        Computed(
            "CASE WHEN ST_Covers(boundary, ST_Centroid(boundary::geography)::geometry) "
            "THEN ST_Centroid(boundary::geography)::geometry "
            "ELSE ST_PointOnSurface(boundary) END",
            persisted=True,
        ),
        nullable=False,
    )
    area_km2: Mapped[float] = mapped_column(
        Float, Computed("ST_Area(boundary::geography) / 1000000.0", persisted=True), nullable=False
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )


class DataSource(Identity, Created, Base):
    __tablename__ = "data_sources"
    __table_args__ = (checksum_constraint("checksum_sha256", "ck_data_sources_checksum"),)
    provider_name: Mapped[str] = mapped_column(String(200), nullable=False)
    dataset_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    license_identifier: Mapped[str] = mapped_column(String(200), nullable=False)
    attribution_text: Mapped[str] = mapped_column(Text, nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_version: Mapped[str] = mapped_column(String(100), nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )


class NetworkVersion(Identity, Created, Base):
    __tablename__ = "network_versions"
    __table_args__ = (
        UniqueConstraint("region_id", "version_label", name="uq_network_region_version"),
        UniqueConstraint("region_id", "checksum_sha256", name="uq_network_region_checksum"),
        CheckConstraint(
            "status IN ('draft','validated','published','archived')", name="ck_network_status"
        ),
        checksum_constraint("checksum_sha256", "ck_network_checksum"),
        CheckConstraint("projection_srid = 4326", name="ck_network_srid"),
        CheckConstraint("node_count >= 0 AND edge_count >= 0", name="ck_network_counts"),
        CheckConstraint(
            "status NOT IN ('published','archived') OR is_validated",
            name="ck_network_publication_validated",
        ),
    )
    region_id: Mapped[UUID] = mapped_column(
        ForeignKey("regions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    data_source_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("data_sources.id", ondelete="RESTRICT")
    )
    version_label: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="draft", server_default="draft"
    )
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_uri: Mapped[str | None] = mapped_column(Text)
    source_format: Mapped[str] = mapped_column(String(100), nullable=False)
    projection_srid: Mapped[int] = mapped_column(
        Integer, nullable=False, default=4326, server_default="4326"
    )
    node_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    edge_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_validated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    validation_summary: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )


class Intersection(Identity, Base):
    __tablename__ = "intersections"
    __table_args__ = (
        UniqueConstraint("network_version_id", "id", name="uq_intersection_network_id"),
        UniqueConstraint("network_version_id", "source_node_id", name="uq_intersection_source_id"),
        UniqueConstraint("network_version_id", "sumo_node_id", name="uq_intersection_sumo_id"),
        geometry_constraint("location", "POINT", "ck_intersection_location"),
        Index("ix_intersections_location_gist", "location", postgresql_using="gist"),
    )
    network_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("network_versions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    source_node_id: Mapped[str] = mapped_column(String(128), nullable=False)
    sumo_node_id: Mapped[str | None] = mapped_column(String(128))
    location: Mapped[WKBElement] = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=False), nullable=False
    )
    intersection_type: Mapped[str] = mapped_column(String(64), nullable=False)
    is_signalized: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )


class RoadEdge(Identity, Base):
    __tablename__ = "road_edges"
    __table_args__ = (
        UniqueConstraint("network_version_id", "sumo_edge_id", name="uq_road_edge_sumo_id"),
        ForeignKeyConstraint(
            ["network_version_id", "start_intersection_id"],
            ["intersections.network_version_id", "intersections.id"],
            name="fk_edge_start_same_network",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["network_version_id", "end_intersection_id"],
            ["intersections.network_version_id", "intersections.id"],
            name="fk_edge_end_same_network",
            ondelete="RESTRICT",
        ),
        CheckConstraint("lane_count > 0", name="ck_edge_lanes"),
        CheckConstraint(
            "speed_limit_mps IS NULL OR (speed_limit_mps > 0 "
            "AND speed_limit_mps < 'Infinity'::float8)",
            name="ck_edge_speed",
        ),
        CheckConstraint("length_m >= 0 AND length_m < 'Infinity'::float8", name="ck_edge_length"),
        CheckConstraint(
            "start_intersection_id <> end_intersection_id", name="ck_edge_distinct_endpoints"
        ),
        geometry_constraint("geom", "LINESTRING", "ck_edge_geometry"),
        Index("ix_road_edges_geom_gist", "geom", postgresql_using="gist"),
        Index("ix_road_edges_geography_gist", text("(geom::geography)"), postgresql_using="gist"),
    )
    network_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("network_versions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    start_intersection_id: Mapped[UUID] = mapped_column(nullable=False)
    end_intersection_id: Mapped[UUID] = mapped_column(nullable=False)
    sumo_edge_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_edge_id: Mapped[str | None] = mapped_column(String(128))
    name: Mapped[str | None] = mapped_column(String(200))
    road_class: Mapped[str] = mapped_column(String(64), nullable=False)
    geom: Mapped[WKBElement] = mapped_column(
        Geometry("LINESTRING", srid=4326, spatial_index=False), nullable=False
    )
    lane_count: Mapped[int] = mapped_column(Integer, nullable=False)
    speed_limit_mps: Mapped[float | None] = mapped_column(Float)
    length_m: Mapped[float] = mapped_column(
        Float, Computed("ST_Length(geom::geography)", persisted=True), nullable=False
    )
    is_one_way: Mapped[bool] = mapped_column(Boolean, nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )


class DemandProfile(Identity, Created, Base):
    __tablename__ = "demand_profiles"
    __table_args__ = (
        UniqueConstraint("network_version_id", "id", name="uq_demand_network_id"),
        CheckConstraint(
            "profile_type IN ('synthetic','artifact_reference')", name="ck_demand_profile_type"
        ),
    )
    network_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("network_versions.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    profile_type: Mapped[str] = mapped_column(String(64), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    artifact_uri: Mapped[str | None] = mapped_column(Text)


class Scenario(Identity, Created, Base):
    __tablename__ = "scenarios"
    __table_args__ = (
        ForeignKeyConstraint(
            ["network_version_id", "demand_profile_id"],
            ["demand_profiles.network_version_id", "demand_profiles.id"],
            name="fk_scenario_demand_same_network",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "duration_seconds > 0 AND duration_seconds <= 86400", name="ck_scenario_duration"
        ),
    )
    network_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("network_versions.id", ondelete="RESTRICT"), nullable=False
    )
    demand_profile_id: Mapped[UUID] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    configuration_checksum: Mapped[str | None] = mapped_column(String(64))


class ScenarioIntervention(Identity, Created, Base):
    __tablename__ = "scenario_interventions"
    __table_args__ = (
        CheckConstraint(
            "intervention_type IN ('speed_limit','edge_closure','signal_timing')",
            name="ck_intervention_type",
        ),
    )
    scenario_id: Mapped[UUID] = mapped_column(
        ForeignKey("scenarios.id", ondelete="RESTRICT"), nullable=False
    )
    intervention_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_identifier: Mapped[str] = mapped_column(String(128), nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class SimulationRun(Identity, Created, Base):
    __tablename__ = "simulation_runs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_simulation_runs_idempotency_key"),
        Index("ix_simulation_runs_status_created", "status", "created_at"),
        CheckConstraint(
            "status IN ('queued','running','succeeded','failed','cancelled')", name="ck_run_status"
        ),
        checksum_constraint("input_sha256", "ck_run_input_checksum"),
        CheckConstraint(
            "finished_at IS NULL OR finished_at >= coalesce(started_at, created_at)",
            name="ck_run_timestamp_order",
        ),
        CheckConstraint(
            "(status='queued' AND started_at IS NULL AND finished_at IS NULL) "
            "OR (status='running' AND started_at IS NOT NULL AND finished_at IS NULL) "
            "OR (status='succeeded' AND started_at IS NOT NULL AND finished_at IS NOT NULL) "
            "OR (status IN ('failed','cancelled') AND finished_at IS NOT NULL)",
            name="ck_run_state_timestamps",
        ),
        CheckConstraint(
            "started_at IS NULL OR started_at >= created_at",
            name="ck_run_started_after_creation",
        ),
    )
    scenario_id: Mapped[UUID] = mapped_column(
        ForeignKey("scenarios.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="queued", server_default="queued"
    )
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    input_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    engine_version: Mapped[str | None] = mapped_column(String(100))
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    request_sha256: Mapped[str | None] = mapped_column(String(64))
    input_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    progress: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    worker_id: Mapped[str | None] = mapped_column(String(100))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_requested: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    attempt_number: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    retry_of: Mapped[UUID | None] = mapped_column(
        ForeignKey("simulation_runs.id", ondelete="RESTRICT", name="fk_simulation_retry")
    )
    output_manifest_uri: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(String(1000))


class RunMetric(Base):
    __tablename__ = "run_metrics"
    __table_args__ = (
        CheckConstraint(
            "value > '-Infinity'::float8 AND value < 'Infinity'::float8",
            name="ck_run_metric_finite",
        ),
    )
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("simulation_runs.id", ondelete="RESTRICT"), primary_key=True
    )
    metric_name: Mapped[str] = mapped_column(String(100), primary_key=True)
    aggregation: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(64), nullable=False)
    calculation_version: Mapped[str] = mapped_column(
        String(64), nullable=False, default="sumo-m04-v1", server_default="sumo-m04-v1"
    )


class RunArtifact(Identity, Created, Base):
    __tablename__ = "run_artifacts"
    __table_args__ = (checksum_constraint("checksum_sha256", "ck_run_artifact_checksum"),)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("simulation_runs.id", ondelete="RESTRICT"), nullable=False
    )
    size_bytes: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    content_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="application/octet-stream",
        server_default="application/octet-stream",
    )
    artifact_type: Mapped[str] = mapped_column(String(100), nullable=False)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)


class AuditEvent(Identity, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint(
            'metadata::text !~* \'"[^"]*(password|secret|token|'
            'credential|authorization|api_key)[^"]*"[[:space:]]*:\'',
            name="ck_audit_no_secret_keys",
        ),
    )
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_id: Mapped[UUID] = mapped_column(nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# JSONB is controlled object extensibility, never an arbitrary array/scalar payload.
for _table_name, _column_name in (
    ("regions", "metadata"),
    ("data_sources", "metadata"),
    ("network_versions", "validation_summary"),
    ("road_edges", "metadata"),
    ("intersections", "metadata"),
    ("demand_profiles", "config"),
    ("scenarios", "config"),
    ("scenario_interventions", "parameters"),
    ("audit_events", "metadata"),
):
    Base.metadata.tables[_table_name].append_constraint(
        CheckConstraint(
            f"jsonb_typeof({_column_name}) = 'object'",
            name=f"ck_{_table_name}_{_column_name}_object",
        )
    )

# Align persisted geometry size with the public GeoJSON serialization budget.
# The broader 0003 validity check remains unchanged; 0004 adds these guards.
Base.metadata.tables["regions"].append_constraint(
    CheckConstraint("ST_NPoints(boundary) <= 5000", name="ck_regions_vertex_budget")
)
Base.metadata.tables["road_edges"].append_constraint(
    CheckConstraint("ST_NPoints(geom) <= 5000", name="ck_edges_vertex_budget")
)
