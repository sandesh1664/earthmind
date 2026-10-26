BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001_postgis

CREATE EXTENSION IF NOT EXISTS postgis;

INSERT INTO alembic_version (version_num) VALUES ('0001_postgis') RETURNING alembic_version.version_num;

-- Running upgrade 0001_postgis -> 0002_system_metadata

CREATE TABLE system_metadata (
    id UUID NOT NULL, 
    application_name VARCHAR(64) NOT NULL, 
    schema_version INTEGER DEFAULT 1 NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_system_metadata_application_name UNIQUE (application_name), 
    CONSTRAINT ck_system_metadata_name_nonempty CHECK (length(application_name) > 0), 
    CONSTRAINT ck_system_metadata_schema_version CHECK (schema_version >= 1), 
    CONSTRAINT ck_system_metadata_timestamp_order CHECK (updated_at >= created_at)
);

CREATE INDEX ix_system_metadata_created_at ON system_metadata (created_at);

INSERT INTO system_metadata (id, application_name, schema_version) VALUES ('00000000-0000-4000-8000-000000000001', 'EARTHMIND', 1) ON CONFLICT (application_name) DO NOTHING;

UPDATE alembic_version SET version_num='0002_system_metadata' WHERE alembic_version.version_num = '0001_postgis';

-- Running upgrade 0002_system_metadata -> 0003_geospatial_foundation

CREATE TABLE data_sources (
    provider_name VARCHAR(200) NOT NULL, 
    dataset_name VARCHAR(200) NOT NULL, 
    source_type VARCHAR(64) NOT NULL, 
    source_url TEXT, 
    license_identifier VARCHAR(200) NOT NULL, 
    attribution_text TEXT NOT NULL, 
    collected_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    source_version VARCHAR(100) NOT NULL, 
    checksum_sha256 VARCHAR(64) NOT NULL, 
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL, 
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_data_sources_checksum CHECK (checksum_sha256 ~ '^[0-9a-f]{64}$'), 
    CONSTRAINT ck_data_sources_metadata_object CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE TABLE regions (
    slug VARCHAR(100) NOT NULL, 
    name VARCHAR(200) NOT NULL, 
    country_code VARCHAR(2) NOT NULL, 
    emirate VARCHAR(100), 
    timezone VARCHAR(100) NOT NULL, 
    boundary geometry(MULTIPOLYGON,4326) NOT NULL, 
    centroid geometry(POINT,4326) GENERATED ALWAYS AS (CASE WHEN ST_Covers(boundary, ST_Centroid(boundary::geography)::geometry) THEN ST_Centroid(boundary::geography)::geometry ELSE ST_PointOnSurface(boundary) END) STORED NOT NULL, 
    area_km2 FLOAT GENERATED ALWAYS AS (ST_Area(boundary::geography) / 1000000.0) STORED NOT NULL, 
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL, 
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_regions_slug CHECK (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'), 
    CONSTRAINT ck_regions_name CHECK (length(name) > 0), 
    CONSTRAINT ck_regions_country CHECK (country_code ~ '^[A-Z]{2}$'), 
    CONSTRAINT ck_regions_area CHECK (area_km2 > 0 AND area_km2 < 'Infinity'::float8), 
    CONSTRAINT ck_regions_boundary CHECK (ST_SRID(boundary) = 4326 AND ST_NDims(boundary) = 2 AND GeometryType(boundary) = 'MULTIPOLYGON' AND NOT ST_IsEmpty(boundary) AND ST_IsValid(boundary) AND ST_NPoints(boundary) <= 10000 AND ST_XMin(Box3D(boundary)) >= -180 AND ST_XMax(Box3D(boundary)) <= 180 AND ST_YMin(Box3D(boundary)) >= -90 AND ST_YMax(Box3D(boundary)) <= 90), 
    CONSTRAINT ck_regions_centroid CHECK (ST_SRID(centroid) = 4326 AND ST_NDims(centroid) = 2 AND GeometryType(centroid) = 'POINT' AND NOT ST_IsEmpty(centroid) AND ST_IsValid(centroid) AND ST_NPoints(centroid) <= 10000 AND ST_XMin(Box3D(centroid)) >= -180 AND ST_XMax(Box3D(centroid)) <= 180 AND ST_YMin(Box3D(centroid)) >= -90 AND ST_YMax(Box3D(centroid)) <= 90), 
    CONSTRAINT ck_regions_centroid_covered CHECK (ST_Covers(boundary, centroid)), 
    UNIQUE (slug), 
    CONSTRAINT ck_regions_metadata_object CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE INDEX ix_regions_boundary_gist ON regions USING gist (boundary);

CREATE TABLE users (
    email VARCHAR(320) NOT NULL, 
    password_hash VARCHAR(512) NOT NULL, 
    role VARCHAR(32) DEFAULT 'viewer' NOT NULL, 
    is_active BOOLEAN DEFAULT true NOT NULL, 
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_users_email CHECK (email = lower(email) AND position('@' in email) > 1), 
    CONSTRAINT ck_users_password_hash CHECK (password_hash LIKE '$argon2id$%%' OR password_hash LIKE '$scrypt$%%' OR password_hash LIKE '$2b$%%'), 
    CONSTRAINT ck_users_role CHECK (role IN ('admin','researcher','viewer')), 
    UNIQUE (email)
);

CREATE TABLE audit_events (
    actor_id UUID, 
    action VARCHAR(100) NOT NULL, 
    target_type VARCHAR(100) NOT NULL, 
    target_id UUID NOT NULL, 
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL, 
    occurred_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_audit_no_secret_keys CHECK (metadata::text !~* '"[^"]*(password|secret|token|credential|authorization|api_key)[^"]*"[[:space:]]*:'), 
    FOREIGN KEY(actor_id) REFERENCES users (id) ON DELETE RESTRICT, 
    CONSTRAINT ck_audit_events_metadata_object CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE TABLE network_versions (
    region_id UUID NOT NULL, 
    data_source_id UUID, 
    version_label VARCHAR(100) NOT NULL, 
    status VARCHAR(32) DEFAULT 'draft' NOT NULL, 
    checksum_sha256 VARCHAR(64) NOT NULL, 
    artifact_uri TEXT, 
    source_format VARCHAR(100) NOT NULL, 
    projection_srid INTEGER DEFAULT '4326' NOT NULL, 
    node_count INTEGER DEFAULT '0' NOT NULL, 
    edge_count INTEGER DEFAULT '0' NOT NULL, 
    is_validated BOOLEAN DEFAULT false NOT NULL, 
    validation_summary JSONB DEFAULT '{}'::jsonb NOT NULL, 
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_network_region_version UNIQUE (region_id, version_label), 
    CONSTRAINT uq_network_region_checksum UNIQUE (region_id, checksum_sha256), 
    CONSTRAINT ck_network_status CHECK (status IN ('draft','validated','published','archived')), 
    CONSTRAINT ck_network_checksum CHECK (checksum_sha256 ~ '^[0-9a-f]{64}$'), 
    CONSTRAINT ck_network_srid CHECK (projection_srid = 4326), 
    CONSTRAINT ck_network_counts CHECK (node_count >= 0 AND edge_count >= 0), 
    CONSTRAINT ck_network_publication_validated CHECK (status NOT IN ('published','archived') OR is_validated), 
    FOREIGN KEY(region_id) REFERENCES regions (id) ON DELETE RESTRICT, 
    FOREIGN KEY(data_source_id) REFERENCES data_sources (id) ON DELETE RESTRICT, 
    CONSTRAINT ck_network_versions_validation_summary_object CHECK (jsonb_typeof(validation_summary) = 'object')
);

CREATE INDEX ix_network_versions_region_id ON network_versions (region_id);

CREATE TABLE demand_profiles (
    network_version_id UUID NOT NULL, 
    name VARCHAR(200) NOT NULL, 
    seed INTEGER NOT NULL, 
    profile_type VARCHAR(64) NOT NULL, 
    config JSONB NOT NULL, 
    artifact_uri TEXT, 
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_demand_network_id UNIQUE (network_version_id, id), 
    CONSTRAINT ck_demand_profile_type CHECK (profile_type IN ('synthetic','artifact_reference')), 
    FOREIGN KEY(network_version_id) REFERENCES network_versions (id) ON DELETE RESTRICT, 
    CONSTRAINT ck_demand_profiles_config_object CHECK (jsonb_typeof(config) = 'object')
);

CREATE TABLE intersections (
    network_version_id UUID NOT NULL, 
    source_node_id VARCHAR(128) NOT NULL, 
    sumo_node_id VARCHAR(128), 
    location geometry(POINT,4326) NOT NULL, 
    intersection_type VARCHAR(64) NOT NULL, 
    is_signalized BOOLEAN DEFAULT false NOT NULL, 
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL, 
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_intersection_network_id UNIQUE (network_version_id, id), 
    CONSTRAINT uq_intersection_source_id UNIQUE (network_version_id, source_node_id), 
    CONSTRAINT uq_intersection_sumo_id UNIQUE (network_version_id, sumo_node_id), 
    CONSTRAINT ck_intersection_location CHECK (ST_SRID(location) = 4326 AND ST_NDims(location) = 2 AND GeometryType(location) = 'POINT' AND NOT ST_IsEmpty(location) AND ST_IsValid(location) AND ST_NPoints(location) <= 10000 AND ST_XMin(Box3D(location)) >= -180 AND ST_XMax(Box3D(location)) <= 180 AND ST_YMin(Box3D(location)) >= -90 AND ST_YMax(Box3D(location)) <= 90), 
    FOREIGN KEY(network_version_id) REFERENCES network_versions (id) ON DELETE RESTRICT, 
    CONSTRAINT ck_intersections_metadata_object CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE INDEX ix_intersections_location_gist ON intersections USING gist (location);

CREATE INDEX ix_intersections_network_version_id ON intersections (network_version_id);

CREATE TABLE road_edges (
    network_version_id UUID NOT NULL, 
    start_intersection_id UUID NOT NULL, 
    end_intersection_id UUID NOT NULL, 
    sumo_edge_id VARCHAR(128) NOT NULL, 
    source_edge_id VARCHAR(128), 
    name VARCHAR(200), 
    road_class VARCHAR(64) NOT NULL, 
    geom geometry(LINESTRING,4326) NOT NULL, 
    lane_count INTEGER NOT NULL, 
    speed_limit_mps FLOAT, 
    length_m FLOAT GENERATED ALWAYS AS (ST_Length(geom::geography)) STORED NOT NULL, 
    is_one_way BOOLEAN NOT NULL, 
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL, 
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_road_edge_sumo_id UNIQUE (network_version_id, sumo_edge_id), 
    CONSTRAINT fk_edge_start_same_network FOREIGN KEY(network_version_id, start_intersection_id) REFERENCES intersections (network_version_id, id) ON DELETE RESTRICT, 
    CONSTRAINT fk_edge_end_same_network FOREIGN KEY(network_version_id, end_intersection_id) REFERENCES intersections (network_version_id, id) ON DELETE RESTRICT, 
    CONSTRAINT ck_edge_lanes CHECK (lane_count > 0), 
    CONSTRAINT ck_edge_speed CHECK (speed_limit_mps IS NULL OR (speed_limit_mps > 0 AND speed_limit_mps < 'Infinity'::float8)), 
    CONSTRAINT ck_edge_length CHECK (length_m >= 0 AND length_m < 'Infinity'::float8), 
    CONSTRAINT ck_edge_distinct_endpoints CHECK (start_intersection_id <> end_intersection_id), 
    CONSTRAINT ck_edge_geometry CHECK (ST_SRID(geom) = 4326 AND ST_NDims(geom) = 2 AND GeometryType(geom) = 'LINESTRING' AND NOT ST_IsEmpty(geom) AND ST_IsValid(geom) AND ST_NPoints(geom) <= 10000 AND ST_XMin(Box3D(geom)) >= -180 AND ST_XMax(Box3D(geom)) <= 180 AND ST_YMin(Box3D(geom)) >= -90 AND ST_YMax(Box3D(geom)) <= 90), 
    FOREIGN KEY(network_version_id) REFERENCES network_versions (id) ON DELETE RESTRICT, 
    CONSTRAINT ck_road_edges_metadata_object CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE INDEX ix_road_edges_geography_gist ON road_edges USING gist ((geom::geography));

CREATE INDEX ix_road_edges_geom_gist ON road_edges USING gist (geom);

CREATE INDEX ix_road_edges_network_version_id ON road_edges (network_version_id);

CREATE TABLE scenarios (
    network_version_id UUID NOT NULL, 
    demand_profile_id UUID NOT NULL, 
    name VARCHAR(200) NOT NULL, 
    description TEXT NOT NULL, 
    duration_seconds INTEGER NOT NULL, 
    config JSONB NOT NULL, 
    created_by UUID, 
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT fk_scenario_demand_same_network FOREIGN KEY(network_version_id, demand_profile_id) REFERENCES demand_profiles (network_version_id, id) ON DELETE RESTRICT, 
    CONSTRAINT ck_scenario_duration CHECK (duration_seconds > 0 AND duration_seconds <= 86400), 
    FOREIGN KEY(network_version_id) REFERENCES network_versions (id) ON DELETE RESTRICT, 
    FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE RESTRICT, 
    CONSTRAINT ck_scenarios_config_object CHECK (jsonb_typeof(config) = 'object')
);

CREATE TABLE scenario_interventions (
    scenario_id UUID NOT NULL, 
    intervention_type VARCHAR(64) NOT NULL, 
    target_identifier VARCHAR(128) NOT NULL, 
    parameters JSONB NOT NULL, 
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_intervention_type CHECK (intervention_type IN ('speed_limit','edge_closure','signal_timing')), 
    FOREIGN KEY(scenario_id) REFERENCES scenarios (id) ON DELETE RESTRICT, 
    CONSTRAINT ck_scenario_interventions_parameters_object CHECK (jsonb_typeof(parameters) = 'object')
);

CREATE TABLE simulation_runs (
    scenario_id UUID NOT NULL, 
    status VARCHAR(32) DEFAULT 'queued' NOT NULL, 
    seed INTEGER NOT NULL, 
    input_sha256 VARCHAR(64) NOT NULL, 
    engine_version VARCHAR(100), 
    started_at TIMESTAMP WITH TIME ZONE, 
    finished_at TIMESTAMP WITH TIME ZONE, 
    error_code VARCHAR(100), 
    error_message VARCHAR(1000), 
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_run_status CHECK (status IN ('queued','running','succeeded','failed','cancelled')), 
    CONSTRAINT ck_run_input_checksum CHECK (input_sha256 ~ '^[0-9a-f]{64}$'), 
    CONSTRAINT ck_run_timestamp_order CHECK (finished_at IS NULL OR finished_at >= coalesce(started_at, created_at)), 
    FOREIGN KEY(scenario_id) REFERENCES scenarios (id) ON DELETE RESTRICT
);

CREATE TABLE run_artifacts (
    run_id UUID NOT NULL, 
    artifact_type VARCHAR(100) NOT NULL, 
    storage_uri TEXT NOT NULL, 
    checksum_sha256 VARCHAR(64) NOT NULL, 
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_run_artifact_checksum CHECK (checksum_sha256 ~ '^[0-9a-f]{64}$'), 
    FOREIGN KEY(run_id) REFERENCES simulation_runs (id) ON DELETE RESTRICT
);

CREATE TABLE run_metrics (
    run_id UUID NOT NULL, 
    metric_name VARCHAR(100) NOT NULL, 
    aggregation VARCHAR(64) NOT NULL, 
    value FLOAT NOT NULL, 
    unit VARCHAR(64) NOT NULL, 
    PRIMARY KEY (run_id, metric_name, aggregation), 
    CONSTRAINT ck_run_metric_finite CHECK (value > '-Infinity'::float8 AND value < 'Infinity'::float8), 
    FOREIGN KEY(run_id) REFERENCES simulation_runs (id) ON DELETE RESTRICT
);

CREATE FUNCTION earthmind_m02_network_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'draft' THEN
          RAISE EXCEPTION 'New versions must start as draft' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
      END IF;
      IF OLD.status IN ('published', 'archived') THEN
        IF TG_OP = 'UPDATE' AND OLD.status = 'published' AND NEW.status = 'archived'
          AND (to_jsonb(OLD) - 'status') = (to_jsonb(NEW) - 'status') THEN
          RETURN NEW;
        END IF;
        RAISE EXCEPTION 'Published network versions are immutable; create a new version'
          USING ERRCODE = '23514';
      END IF;
      IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
      IF NEW.status IN ('published', 'archived') THEN
        IF NOT NEW.is_validated OR coalesce(NEW.validation_summary->>'status','NOT_VALIDATED') NOT IN ('VALID','VALID_WITH_WARNINGS')
          OR NEW.node_count <= 0 OR NEW.edge_count <= 0
          OR NEW.node_count <> (SELECT count(*) FROM intersections WHERE network_version_id=NEW.id)
          OR NEW.edge_count <> (SELECT count(*) FROM road_edges WHERE network_version_id=NEW.id) THEN
          RAISE EXCEPTION 'Publication requires a validated nonempty network with matching counts'
            USING ERRCODE='23514';
        END IF;
      END IF;
      RETURN NEW;
    END $$;

CREATE TRIGGER tr_network_immutable BEFORE INSERT OR UPDATE OR DELETE ON network_versions FOR EACH ROW EXECUTE FUNCTION earthmind_m02_network_guard();

CREATE FUNCTION earthmind_m02_child_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE parent record; old_network uuid; new_network uuid;
    BEGIN
      IF TG_OP <> 'INSERT' THEN old_network := OLD.network_version_id; END IF;
      IF TG_OP <> 'DELETE' THEN new_network := NEW.network_version_id; END IF;
      FOR parent IN SELECT id,status FROM network_versions
        WHERE id IN (old_network, new_network) ORDER BY id FOR UPDATE LOOP
        IF parent.status IN ('published','archived') THEN
          RAISE EXCEPTION 'Published network geometry is immutable; create a new version'
            USING ERRCODE = '23514';
        END IF;
        UPDATE network_versions SET is_validated=false, status='draft',
          validation_summary='{"status":"NOT_VALIDATED"}'::jsonb WHERE id=parent.id;
      END LOOP;
      IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
      RETURN NEW;
    END $$;

CREATE TRIGGER tr_edge_immutable BEFORE INSERT OR UPDATE OR DELETE ON road_edges FOR EACH ROW EXECUTE FUNCTION earthmind_m02_child_guard();

CREATE TRIGGER tr_node_immutable BEFORE INSERT OR UPDATE OR DELETE ON intersections FOR EACH ROW EXECUTE FUNCTION earthmind_m02_child_guard();

CREATE FUNCTION earthmind_m02_run_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'queued' OR NEW.started_at IS NOT NULL OR NEW.finished_at IS NOT NULL THEN
          RAISE EXCEPTION 'New simulation contracts must be queued and unexecuted' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
      END IF;
      IF OLD.status IN ('succeeded','failed','cancelled') THEN
        IF to_jsonb(OLD) <> to_jsonb(NEW) THEN
          RAISE EXCEPTION 'Terminal simulation records are immutable' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
      END IF;
      IF (OLD.scenario_id,OLD.seed,OLD.input_sha256) IS DISTINCT FROM
         (NEW.scenario_id,NEW.seed,NEW.input_sha256) THEN
        RAISE EXCEPTION 'Simulation input identity is immutable' USING ERRCODE='23514';
      END IF;
      IF NEW.status <> OLD.status THEN
        IF NOT ((OLD.status='queued' AND NEW.status IN ('running','cancelled'))
          OR (OLD.status='running' AND NEW.status IN ('succeeded','failed','cancelled'))) THEN
          RAISE EXCEPTION 'Invalid simulation state transition' USING ERRCODE='23514';
        END IF;
      END IF;
      IF NEW.status='running' THEN
        NEW.started_at := coalesce(NEW.started_at,clock_timestamp());
        NEW.finished_at := NULL;
      ELSIF NEW.status IN ('succeeded','failed','cancelled') THEN
        NEW.finished_at := coalesce(NEW.finished_at,clock_timestamp());
      END IF;
      RETURN NEW;
    END $$;

CREATE TRIGGER tr_run_states BEFORE INSERT OR UPDATE ON simulation_runs FOR EACH ROW EXECUTE FUNCTION earthmind_m02_run_guard();

CREATE FUNCTION earthmind_m02_region_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_timezone_names WHERE name=NEW.timezone) THEN
        RAISE EXCEPTION 'Unknown region timezone' USING ERRCODE='23514';
      END IF;
      IF TG_OP='UPDATE' THEN NEW.updated_at := clock_timestamp(); END IF;
      RETURN NEW;
    END $$;

CREATE TRIGGER tr_region_timezone BEFORE INSERT OR UPDATE ON regions FOR EACH ROW EXECUTE FUNCTION earthmind_m02_region_guard();

UPDATE alembic_version SET version_num='0003_geospatial_foundation' WHERE alembic_version.version_num = '0002_system_metadata';

COMMIT;

