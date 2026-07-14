-- 003 — سلطة الكائنات، المسائل الدقيقة (many-to-many)، والإشارات التشريعية غير المحلولة
-- backward-compatible: لا يُحذف عمود ولا صف. العمود القديم micro_issue يبقى ويُعلَّم deprecated.

BEGIN;

-- ── 1) سلطة الكائن وقابليته للاستشهاد (بند «خامسًا») ──────────────────
ALTER TABLE knowledge_objects
  ADD COLUMN IF NOT EXISTS authority_status   TEXT    NOT NULL DEFAULT 'source_authority',
  ADD COLUMN IF NOT EXISTS usable_as_citation BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE knowledge_objects DROP CONSTRAINT IF EXISTS ko_authority_status_valid;
ALTER TABLE knowledge_objects ADD CONSTRAINT ko_authority_status_valid
  CHECK (authority_status IN ('source_authority', 'non_authoritative', 'human_verified_authority'));

ALTER TABLE knowledge_objects DROP CONSTRAINT IF EXISTS ko_verification_status_valid;
ALTER TABLE knowledge_objects ADD CONSTRAINT ko_verification_status_valid
  CHECK (verification_status IN (
    'source_verified', 'operationally_accepted', 'machine_pending_human',
    'historical_only', 'requires_post_2026_reassessment', 'superseded'
  ));

-- القيد الحاكم: القاعدة الجامعة لا تكون قابلة للاستشهاد أبدًا.
-- هذا قيد قاعدة بيانات، لا قاعدة تطبيقية — لا يمكن الالتفاف عليه من الكود.
ALTER TABLE knowledge_objects DROP CONSTRAINT IF EXISTS ko_synthesized_rule_never_citable;
ALTER TABLE knowledge_objects ADD CONSTRAINT ko_synthesized_rule_never_citable
  CHECK (NOT (object_type = 'synthesized_rule' AND usable_as_citation = TRUE));

-- القاعدة الجامعة لا تكون سلطة مصدرية.
ALTER TABLE knowledge_objects DROP CONSTRAINT IF EXISTS ko_synthesized_rule_non_authoritative;
ALTER TABLE knowledge_objects ADD CONSTRAINT ko_synthesized_rule_non_authoritative
  CHECK (NOT (object_type = 'synthesized_rule' AND authority_status <> 'non_authoritative'));

COMMENT ON COLUMN knowledge_objects.micro_issue IS
  'DEPRECATED — المسألة الرئيسية فقط. المصدر الحاكم: knowledge_object_micro_issues (many-to-many).';

-- ── 2) المسائل الدقيقة many-to-many (بند «رابعًا») ────────────────────
CREATE TABLE IF NOT EXISTS micro_issues (
  id                   BIGSERIAL PRIMARY KEY,
  branch               TEXT NOT NULL,
  topic                TEXT NOT NULL,
  classification_title TEXT NOT NULL,
  micro_issue_name     TEXT NOT NULL,
  normalized_key       TEXT NOT NULL,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (branch, topic, classification_title, normalized_key)
);

CREATE TABLE IF NOT EXISTS knowledge_object_micro_issues (
  knowledge_object_id TEXT   NOT NULL REFERENCES knowledge_objects(id) ON DELETE CASCADE,
  micro_issue_id      BIGINT NOT NULL REFERENCES micro_issues(id)      ON DELETE CASCADE,
  assignment_origin   TEXT   NOT NULL,
  confidence          NUMERIC(5,4),
  is_primary          BOOLEAN NOT NULL DEFAULT FALSE,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (knowledge_object_id, micro_issue_id),
  CONSTRAINT komi_origin_valid
    CHECK (assignment_origin IN ('source_explicit', 'machine_inferred', 'human_verified'))
);

-- مسألة رئيسية واحدة على الأكثر لكل كائن.
CREATE UNIQUE INDEX IF NOT EXISTS idx_komi_one_primary
  ON knowledge_object_micro_issues (knowledge_object_id) WHERE is_primary;

CREATE INDEX IF NOT EXISTS idx_komi_issue ON knowledge_object_micro_issues (micro_issue_id);

-- ── 3) الإشارات التشريعية الصريحة غير المحلولة (بند «ثالثًا») ─────────
-- المبدأ يذكر «م338 ق51/1984» صراحةً، ولا وجود لكائن تشريعي بعد.
-- تُحفظ الإشارة كما وردت. لا يُختلق كائن تشريعي. لا تُنشأ علاقة expressly_mentions
-- إلا بعد إدخال التشريع الأصلي ومطابقته (T-11).
CREATE TABLE IF NOT EXISTS legislation_mentions (
  id                  BIGSERIAL PRIMARY KEY,
  knowledge_object_id TEXT NOT NULL REFERENCES knowledge_objects(id) ON DELETE CASCADE,
  mention_type        TEXT NOT NULL DEFAULT 'legislation_reference',
  mention_origin      TEXT NOT NULL DEFAULT 'source_explicit',
  raw_mention_text    TEXT NOT NULL,
  law_number          TEXT,
  law_year            TEXT,
  article_number      TEXT,
  target_object_id    TEXT REFERENCES knowledge_objects(id) ON DELETE SET NULL,
  resolution_status   TEXT NOT NULL DEFAULT 'unresolved_missing_authority',
  usable_as_authority BOOLEAN NOT NULL DEFAULT FALSE,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolved_at         TIMESTAMPTZ,
  UNIQUE (knowledge_object_id, raw_mention_text),
  CONSTRAINT lm_origin_valid
    CHECK (mention_origin IN ('source_explicit', 'machine_inferred')),
  CONSTRAINT lm_resolution_valid
    CHECK (resolution_status IN ('unresolved_missing_authority', 'resolved_to_verified_authority')),
  -- إشارة غير محلولة لا تكون سندًا، ولا تحمل هدفًا.
  CONSTRAINT lm_unresolved_never_authority
    CHECK (resolution_status <> 'unresolved_missing_authority'
           OR (usable_as_authority = FALSE AND target_object_id IS NULL)),
  -- إشارة محلولة يجب أن تشير إلى كائن حقيقي.
  CONSTRAINT lm_resolved_needs_target
    CHECK (resolution_status <> 'resolved_to_verified_authority' OR target_object_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_lm_object     ON legislation_mentions (knowledge_object_id);
CREATE INDEX IF NOT EXISTS idx_lm_resolution ON legislation_mentions (resolution_status);

-- ── 4) أصل العلاقة (بند «سادسًا») ────────────────────────────────────
ALTER TABLE relationships
  ADD COLUMN IF NOT EXISTS relation_origin TEXT NOT NULL DEFAULT 'source_explicit';

ALTER TABLE relationships DROP CONSTRAINT IF EXISTS rel_origin_valid;
ALTER TABLE relationships ADD CONSTRAINT rel_origin_valid
  CHECK (relation_origin IN ('source_explicit', 'machine_inferred', 'human_verified'));

CREATE INDEX IF NOT EXISTS idx_ko_authority
  ON knowledge_objects (object_type, verification_status, usable_as_citation);

COMMIT;
