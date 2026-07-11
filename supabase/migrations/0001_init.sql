-- Arch-Prime Tri-Track operational schemas (Supabase remote)
-- Do not share credentials or env with arch_prime_vault Sandbox

CREATE SCHEMA IF NOT EXISTS spatial;
CREATE SCHEMA IF NOT EXISTS sciences;
CREATE SCHEMA IF NOT EXISTS societal;

COMMENT ON SCHEMA spatial IS 'Operational geospatial track; all metric geometry via SpatialContextEnvelope';
COMMENT ON SCHEMA sciences IS 'Operational sciences / UAV / materials track';
COMMENT ON SCHEMA societal IS 'Operational statutory and societal compliance track';

CREATE EXTENSION IF NOT EXISTS postgis;

GRANT USAGE ON SCHEMA spatial TO postgres, service_role;
GRANT USAGE ON SCHEMA sciences TO postgres, service_role;
GRANT USAGE ON SCHEMA societal TO postgres, service_role;

-- Geospatial tables live under spatial; PostGIS types referenced from extension
CREATE TABLE IF NOT EXISTS spatial.spatial_context_envelopes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  crs_authority text NOT NULL,
  crs_epsg integer NOT NULL,
  envelope_geom geometry(Polygon, 0) NOT NULL,
  precision_digits smallint NOT NULL,
  source_engine text NOT NULL,
  provenance_hash text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS spatial_context_envelopes_geom_gix
  ON spatial.spatial_context_envelopes USING GIST (envelope_geom);

CREATE TABLE IF NOT EXISTS sciences.observation_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_label text NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS societal.compliance_flags (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  trigger_key text NOT NULL,
  severity text NOT NULL,
  context jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS compliance_flags_trigger_key_idx
  ON societal.compliance_flags (trigger_key);
