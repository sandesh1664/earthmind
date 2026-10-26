
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
    END $$

-- statement --
CREATE TRIGGER tr_network_immutable BEFORE INSERT OR UPDATE OR DELETE ON network_versions FOR EACH ROW EXECUTE FUNCTION earthmind_m02_network_guard()
-- statement --

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
    END $$

-- statement --
CREATE TRIGGER tr_edge_immutable BEFORE INSERT OR UPDATE OR DELETE ON road_edges FOR EACH ROW EXECUTE FUNCTION earthmind_m02_child_guard()
-- statement --
CREATE TRIGGER tr_node_immutable BEFORE INSERT OR UPDATE OR DELETE ON intersections FOR EACH ROW EXECUTE FUNCTION earthmind_m02_child_guard()
-- statement --

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
    END $$

-- statement --
CREATE TRIGGER tr_run_states BEFORE INSERT OR UPDATE ON simulation_runs FOR EACH ROW EXECUTE FUNCTION earthmind_m02_run_guard()
-- statement --

    CREATE FUNCTION earthmind_m02_region_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_timezone_names WHERE name=NEW.timezone) THEN
        RAISE EXCEPTION 'Unknown region timezone' USING ERRCODE='23514';
      END IF;
      IF TG_OP='UPDATE' THEN NEW.updated_at := clock_timestamp(); END IF;
      RETURN NEW;
    END $$

-- statement --
CREATE TRIGGER tr_region_timezone BEFORE INSERT OR UPDATE ON regions FOR EACH ROW EXECUTE FUNCTION earthmind_m02_region_guard()
