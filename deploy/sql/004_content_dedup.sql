-- 004 — منع التكرار على أساس SHA-256 وجعل الإدخال idempotent
-- backward-compatible: لا يُحذف عمود ولا صف.
--
-- البصمة تُحسب على النص الأصلي بعد التطبيع التقني (canonical body)، لا على بايتات
-- الملف. التطبيع التقني (NFKC، حذف التطويل والمحارف غير المرئية، توحيد المسافات)
-- لا يغيّر المحتوى القانوني، لذا فملف DOCX ونصّ ملصق يحملان النص نفسه يعطيان
-- البصمة نفسها ويُعدّان تكرارًا — وهو المطلوب.
--
-- النطاق: (branch, topic). النص نفسه تحت فرع أو موضوع مختلف إدخال مشروع.

BEGIN;

ALTER TABLE sources
  ADD COLUMN IF NOT EXISTS content_sha256 TEXT,
  ADD COLUMN IF NOT EXISTS branch         TEXT,
  ADD COLUMN IF NOT EXISTS topic          TEXT,
  ADD COLUMN IF NOT EXISTS first_batch_id TEXT;

COMMENT ON COLUMN sources.sha256 IS
  'بصمة بايتات المصدر الخام. تتغير بتغير الصيغة. ليست مفتاح منع التكرار.';
COMMENT ON COLUMN sources.content_sha256 IS
  'بصمة النص بعد التطبيع التقني. هذا هو مفتاح منع التكرار الحاكم.';

-- القيد الحاكم لمنع التكرار: قيد قاعدة بيانات لا قاعدة تطبيقية.
CREATE UNIQUE INDEX IF NOT EXISTS idx_sources_content_dedup
  ON sources (branch, topic, content_sha256)
  WHERE content_sha256 IS NOT NULL AND branch IS NOT NULL AND topic IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_sources_content_sha ON sources (content_sha256);

-- أثر تدقيق: الدفعة المرفوضة كتكرار تُسجَّل ولا تُنشئ كائنات.
ALTER TABLE ingestion_batches DROP CONSTRAINT IF EXISTS ib_status_valid;
ALTER TABLE ingestion_batches ADD CONSTRAINT ib_status_valid
  CHECK (status IN ('started', 'completed', 'failed', 'duplicate'));

COMMIT;
