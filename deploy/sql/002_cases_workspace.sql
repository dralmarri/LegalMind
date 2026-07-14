CREATE TABLE IF NOT EXISTS legal_cases (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_key TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  branch TEXT NOT NULL,
  topic TEXT,
  subtopic TEXT,
  client_name TEXT,
  client_capacity TEXT,
  opponent_name TEXT,
  court_name TEXT,
  court_level TEXT,
  status TEXT NOT NULL DEFAULT 'draft',
  facts TEXT NOT NULL DEFAULT '',
  requests TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '',
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS case_documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id UUID NOT NULL REFERENCES legal_cases(id) ON DELETE CASCADE,
  document_type TEXT NOT NULL,
  title TEXT NOT NULL,
  file_name TEXT,
  source_key TEXT REFERENCES sources(source_key),
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS case_authorities (
  id BIGSERIAL PRIMARY KEY,
  case_id UUID NOT NULL REFERENCES legal_cases(id) ON DELETE CASCADE,
  object_id TEXT NOT NULL REFERENCES knowledge_objects(id) ON DELETE CASCADE,
  authority_role TEXT NOT NULL DEFAULT 'supporting',
  relevance_note TEXT,
  verification_status TEXT NOT NULL DEFAULT 'operationally_accepted',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(case_id, object_id, authority_role)
);

CREATE TABLE IF NOT EXISTS case_drafts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id UUID NOT NULL REFERENCES legal_cases(id) ON DELETE CASCADE,
  draft_type TEXT NOT NULL,
  version INTEGER NOT NULL DEFAULT 1,
  title TEXT NOT NULL,
  body TEXT NOT NULL DEFAULT '',
  drafting_status TEXT NOT NULL DEFAULT 'blocked_missing_authorities',
  authority_report JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(case_id, draft_type, version)
);

CREATE INDEX IF NOT EXISTS idx_cases_classification ON legal_cases(branch, topic, subtopic, status);
CREATE INDEX IF NOT EXISTS idx_case_authorities_case ON case_authorities(case_id, authority_role);
CREATE INDEX IF NOT EXISTS idx_case_drafts_case ON case_drafts(case_id, draft_type, version DESC);
