-- CHORA LABS: PROV-O Provenance Chain of Custody
-- Target: PostgreSQL 17 + PostGIS (Supabase managed)
-- Purpose: Remediation of D-04 (Provenance Chain Absent) - establishes a
--          mathematically traceable chain of custody across the 5-plane
--          architecture (Supabase, GitHub, Linear, Notion, Tana).
-- Ticket:  MBSCI-6
-- Notes:   Non-destructive, schema-only. RLS policies to follow in a
--          downstream MBSCI ticket. Legacy "QUAD-PLATFORM" nomenclature is
--          deprecated; 'platform' column enum is the canonical 5-plane list.

CREATE SCHEMA IF NOT EXISTS prov;

COMMENT ON SCHEMA prov IS
  'W3C PROV-O core (Entity/Activity/Agent + wasGeneratedBy/used/wasAttributedTo/wasDerivedFrom). Platform enum: github|supabase|linear|notion|tana.';

-- ---------- Core PROV-O classes ----------

CREATE TABLE IF NOT EXISTS prov.entity (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  iri          text NOT NULL UNIQUE,
  label        text,
  entity_type  text,
  platform     text CHECK (platform IN ('github','supabase','linear','notion','tana')),
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS prov.activity (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  iri            text UNIQUE,
  label          text NOT NULL,
  activity_type  text,
  started_at     timestamptz,
  ended_at       timestamptz,
  platform       text CHECK (platform IN ('github','supabase','linear','notion','tana')),
  created_at     timestamptz NOT NULL DEFAULT now(),
  CHECK (ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at)
);

CREATE TABLE IF NOT EXISTS prov.agent (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  iri         text NOT NULL UNIQUE,
  label       text NOT NULL,
  agent_type  text,
  platform    text CHECK (platform IN ('github','supabase','linear','notion','tana')),
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- ---------- PROV-O relations ----------

CREATE TABLE IF NOT EXISTS prov.was_generated_by (
  entity_id    uuid NOT NULL REFERENCES prov.entity(id)   ON DELETE CASCADE,
  activity_id  uuid NOT NULL REFERENCES prov.activity(id) ON DELETE CASCADE,
  created_at   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (entity_id, activity_id)
);

CREATE TABLE IF NOT EXISTS prov.used (
  activity_id  uuid NOT NULL REFERENCES prov.activity(id) ON DELETE CASCADE,
  entity_id    uuid NOT NULL REFERENCES prov.entity(id)   ON DELETE CASCADE,
  created_at   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (activity_id, entity_id)
);

CREATE TABLE IF NOT EXISTS prov.was_attributed_to (
  entity_id   uuid NOT NULL REFERENCES prov.entity(id) ON DELETE CASCADE,
  agent_id    uuid NOT NULL REFERENCES prov.agent(id)  ON DELETE CASCADE,
  created_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (entity_id, agent_id)
);

CREATE TABLE IF NOT EXISTS prov.was_derived_from (
  generated_entity_id  uuid NOT NULL REFERENCES prov.entity(id) ON DELETE CASCADE,
  source_entity_id     uuid NOT NULL REFERENCES prov.entity(id) ON DELETE CASCADE,
  created_at           timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (generated_entity_id, source_entity_id),
  CHECK (generated_entity_id <> source_entity_id)
);

-- ---------- Indexes for high-frequency provenance traversal ----------

CREATE INDEX IF NOT EXISTS idx_prov_entity_platform    ON prov.entity   (platform);
CREATE INDEX IF NOT EXISTS idx_prov_activity_platform  ON prov.activity (platform);
CREATE INDEX IF NOT EXISTS idx_prov_agent_platform     ON prov.agent    (platform);
CREATE INDEX IF NOT EXISTS idx_prov_activity_time      ON prov.activity (started_at, ended_at);

-- ---------- Grants (align with 0001_init.sql conventions) ----------

GRANT USAGE ON SCHEMA prov TO postgres, service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA prov TO service_role;
