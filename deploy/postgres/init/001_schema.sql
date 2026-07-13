CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS sources (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_key TEXT UNIQUE NOT NULL,
  source_type TEXT NOT NULL,
  title TEXT NOT NULL,
  file_name TEXT,
  sha256 TEXT NOT NULL,
  verification_status TEXT NOT NULL DEFAULT 'operationally_accepted',
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS knowledge_objects (
  id TEXT PRIMARY KEY,
  object_type TEXT NOT NULL,
  branch TEXT NOT NULL,
  topic TEXT,
  subtopic TEXT,
  micro_issue TEXT,
  title TEXT,
  original_text TEXT NOT NULL,
  normalized_text TEXT,
  source_key TEXT REFERENCES sources(source_key),
  verification_status TEXT NOT NULL,
  temporal_scope JSONB NOT NULL DEFAULT '{}'::jsonb,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS relationships (
  id BIGSERIAL PRIMARY KEY,
  from_id TEXT NOT NULL REFERENCES knowledge_objects(id) ON DELETE CASCADE,
  relation_type TEXT NOT NULL,
  to_id TEXT NOT NULL REFERENCES knowledge_objects(id) ON DELETE CASCADE,
  confidence NUMERIC(5,4),
  verification_status TEXT NOT NULL DEFAULT 'operationally_accepted',
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE(from_id, relation_type, to_id)
);

CREATE TABLE IF NOT EXISTS verification_issues (
  id TEXT PRIMARY KEY,
  object_id TEXT REFERENCES knowledge_objects(id) ON DELETE SET NULL,
  status TEXT NOT NULL DEFAULT 'open',
  issue_type TEXT NOT NULL,
  description TEXT NOT NULL,
  evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
  resolution TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolved_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS ingestion_batches (
  batch_id TEXT PRIMARY KEY,
  source_key TEXT,
  status TEXT NOT NULL,
  object_count INTEGER NOT NULL DEFAULT 0,
  relationship_count INTEGER NOT NULL DEFAULT 0,
  report JSONB NOT NULL DEFAULT '{}'::jsonb,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_ko_classification ON knowledge_objects(branch, topic, subtopic, micro_issue);
CREATE INDEX IF NOT EXISTS idx_ko_type ON knowledge_objects(object_type);
CREATE INDEX IF NOT EXISTS idx_ko_metadata_gin ON knowledge_objects USING GIN(metadata);
CREATE INDEX IF NOT EXISTS idx_rel_from ON relationships(from_id, relation_type);
CREATE INDEX IF NOT EXISTS idx_rel_to ON relationships(to_id, relation_type);
