-- CHORA LABS: PROV-O 5-Plane Agent Seed
-- Target: prov.agent (W3C PROV-O :Agent)
-- Purpose: Establish canonical software agent identities for the 5-plane
--          architecture so downstream provenance edges (was_attributed_to,
--          was_generated_by) can resolve to a stable IRI per platform.
-- Depends on: 0002_prov.sql (MBSCI-6, commit 653a419)
-- Non-destructive: ON CONFLICT (iri) DO NOTHING.

INSERT INTO prov.agent (iri, label, agent_type, platform) VALUES
  ('urn:chora:agent:platform:github',   'GitHub Plane',   'SoftwareAgent', 'github'),
  ('urn:chora:agent:platform:supabase', 'Supabase Plane', 'SoftwareAgent', 'supabase'),
  ('urn:chora:agent:platform:linear',   'Linear Plane',   'SoftwareAgent', 'linear'),
  ('urn:chora:agent:platform:notion',   'Notion Plane',   'SoftwareAgent', 'notion'),
  ('urn:chora:agent:platform:tana',     'Tana Plane',     'SoftwareAgent', 'tana')
ON CONFLICT (iri) DO NOTHING;
