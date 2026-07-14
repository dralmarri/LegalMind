#!/usr/bin/env python3
"""اختبارات خط الإدخال — على PostgreSQL وQdrant الحقيقيين، لا على بدائل وهمية.

الاختبار الذي يعمل على mock لا يثبت أن النظام يعمل. كل اختبار هنا يكتب فعلًا
ثم يقرأ فعلًا ثم ينظّف أثره. يُشغَّل بفرع اختبار معزول لا يلوّث المعرفة الحقيقية.

    pytest engine/test_ingestion.py -v
"""
from __future__ import annotations

import json
import os
import sys
import zipfile
from pathlib import Path

import psycopg
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import embedding
import legalmind_engine as eng
from normalizer import normalize
from normalizer.readers import UnsupportedSource

TEST_BRANCH = "اختبار آلي"
TEST_TOPIC = "خط الإدخال"
TEST_FILES = ["scanned.pdf", "scan.jpg", "hadana.docx", "pasted.md", "law.md",
              "law-a.md", "law-b.docx", "noisy.txt", "clean.txt"]

LEGISLATION = """المادة 1
تثبت الحضانة للأم ما لم يقض القاضي بغير ذلك لمصلحة المحضون.

المادة 2
يسقط حق الحاضنة في الحضانة إذا تزوجت بأجنبي عن المحضون.
"""


def db():
    return psycopg.connect(eng.database_url())


def cleanup():
    """يمحو أثر الاختبار من PostgreSQL وQdrant معًا."""
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT source_key FROM sources WHERE branch=%s", (TEST_BRANCH,))
        keys = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT id FROM knowledge_objects WHERE branch=%s", (TEST_BRANCH,))
        ids = [r[0] for r in cur.fetchall()]
        cur.execute("DELETE FROM knowledge_objects WHERE branch=%s", (TEST_BRANCH,))
        if keys:
            cur.execute("DELETE FROM ingestion_batches WHERE source_key = ANY(%s)", (keys,))
            cur.execute("DELETE FROM sources WHERE source_key = ANY(%s)", (keys,))
        # الدفعة المرفوضة عند التطبيع بلا source_key، فلا تطالها الجملة أعلاه.
        cur.execute(
            "DELETE FROM ingestion_batches WHERE source_key IS NULL AND report->>'file' = ANY(%s)",
            (TEST_FILES,),
        )
        conn.commit()
    if ids:
        try:
            eng.qdrant_request(
                "POST", f"/collections/{eng.COLLECTION}/points/delete?wait=true",
                {"points": [embedding.point_id(i) for i in ids]},
            )
        except Exception:
            pass


@pytest.fixture(autouse=True)
def clean_slate():
    cleanup()
    yield
    cleanup()


@pytest.fixture
def workspace(tmp_path):
    inbox, archive, failed = tmp_path / "inbox", tmp_path / "archive", tmp_path / "failed"
    inbox.mkdir()
    return inbox, archive, failed


def put_source(inbox: Path, name: str, body: str | bytes, **meta) -> Path:
    path = inbox / name
    if isinstance(body, bytes):
        path.write_bytes(body)
    else:
        path.write_text(body, encoding="utf-8")
    metadata = {
        "source_type": "legislation", "branch": TEST_BRANCH, "topic": TEST_TOPIC,
        "classification_title": "الحضانة وسقوطها", "title": name,
        "verification_status": "source_verified", "upload_origin": "file_upload",
    }
    metadata.update(meta)
    path.with_suffix(path.suffix + ".json").write_text(
        json.dumps(metadata, ensure_ascii=False), encoding="utf-8"
    )
    return path


def make_docx(path: Path, paragraphs: list[str]) -> Path:
    """DOCX حقيقي بأصغر بنية صالحة — لا نعتمد على مكتبة خارجية للاختبار."""
    body = "".join(
        f'<w:p><w:r><w:t xml:space="preserve">{p}</w:t></w:r></w:p>' for p in paragraphs
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
        'relationships/officeDocument" Target="word/document.xml"/></Relationships>'
    )
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", document)
    return path


def scanned_pdf_bytes() -> bytes:
    """PDF صالح بصفحة بلا أي طبقة نصية — يحاكي الممسوح ضوئيًا."""
    objects = [
        "1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj",
        "2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj",
        "3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for obj in objects:
        offsets.append(len(out))
        out += obj.encode() + b"\n"
    xref = len(out)
    out += f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer<</Size {len(objects)+1}/Root 1 0 R>>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


# ── 1) رفع ملف صالح ────────────────────────────────────────────────
def test_valid_file_upload(workspace):
    inbox, archive, failed = workspace
    path = make_docx(inbox / "hadana.docx", ["المادة 1", "تثبت الحضانة للأم.", "المادة 2", "يسقط حقها بالزواج."])
    put_source(inbox, "hadana.docx", path.read_bytes())
    result = eng.ingest_file(inbox / "hadana.docx", archive, failed)
    assert result["status"] == "completed"
    assert result["source_format"] == "docx"
    assert result["object_count"] == 2
    assert not (inbox / "hadana.docx").exists(), "الملف المعالَج يجب أن يغادر inbox"


# ── 2) لصق نص صالح ─────────────────────────────────────────────────
def test_valid_pasted_text(workspace):
    inbox, archive, failed = workspace
    path = put_source(inbox, "pasted.md", LEGISLATION, upload_origin="pasted_text")
    result = eng.ingest_file(path, archive, failed)
    assert result["status"] == "completed"
    assert result["object_count"] == 2
    rows = query("SELECT report->>'upload_origin' FROM ingestion_batches WHERE batch_id=%s",
                 (result["batch_id"],))
    assert rows[0][0] == "pasted_text", "أصل الإدخال يجب أن يُحفظ كما هو"


# ── 3) رفض نوع ملف غير مدعوم ───────────────────────────────────────
def test_unsupported_file_rejected(workspace):
    inbox, archive, failed = workspace
    path = put_source(inbox, "scan.jpg", b"\xff\xd8\xff\xe0not-a-document")
    with pytest.raises(Exception) as exc:
        eng.ingest_file(path, archive, failed)
    assert "jpg" in str(exc.value).lower() or "غير مدعوم" in str(exc.value)
    assert count_objects() == 0, "الملف المرفوض لا يترك كائنًا"


# ── 4) رفض PDF ممسوح ضوئيًا بلا سجل فارغ ──────────────────────────
def test_scanned_pdf_rejected_without_empty_record(workspace):
    inbox, archive, failed = workspace
    path = put_source(inbox, "scanned.pdf", scanned_pdf_bytes())
    with pytest.raises(Exception) as exc:
        eng.ingest_file(path, archive, failed)
    message = str(exc.value)
    assert "ممسوح ضوئيًا" in message and "OCR" in message, "الرسالة يجب أن تشرح السبب بالعربية"
    assert count_objects() == 0, "PDF بلا نص لا يُنشئ سجلًا فارغًا"
    assert count_sources() == 0
    assert (failed / "scanned.pdf").exists(), "الملف الفاشل يُنقل إلى failed"
    assert not (inbox / "scanned.pdf").exists(), "لا يبقى في inbox فتتكرر محاولته بلا نهاية"

    # السبب يصل إلى المستخدم: دفعة فاشلة تحمل الرسالة العربية، لا رسالة عامة.
    rows = query(
        """SELECT status, report->>'error' FROM ingestion_batches
           WHERE report->>'file'='scanned.pdf' ORDER BY started_at DESC LIMIT 1"""
    )
    assert rows and rows[0][0] == "failed"
    assert "ممسوح ضوئيًا" in rows[0][1], "سبب الرفض يُحفظ بالعربية ليعرضه الواجهة"


# ── 5) منع التكرار ─────────────────────────────────────────────────
def test_duplicate_detection(workspace):
    inbox, archive, failed = workspace
    first = eng.ingest_file(put_source(inbox, "law-a.md", LEGISLATION), archive, failed)
    assert first["status"] == "completed"

    # النص نفسه، اسم ملف مختلف، وصيغة مختلفة (DOCX) — التكرار على المحتوى لا على البايتات.
    docx = inbox / "law-b.docx"
    make_docx(docx, LEGISLATION.split("\n"))
    put_source(inbox, "law-b.docx", docx.read_bytes())
    second = eng.ingest_file(inbox / "law-b.docx", archive, failed)

    assert second["status"] == "duplicate"
    assert second["duplicate_of"]["first_batch_id"] == first["batch_id"], "يجب أن يُظهر الدفعة السابقة"
    assert count_objects() == 2, "التكرار لا يضاعف الكائنات"
    assert count_sources() == 1, "التكرار لا يُنشئ مصدرًا ثانيًا"


# ── 6) سلامة الـCanonical Markdown ────────────────────────────────
def test_canonical_markdown_integrity(workspace):
    inbox, _, _ = workspace
    # تطويل ومحارف غير مرئية ومسافات زائدة: تُنظَّف دون المساس بالمحتوى القانوني.
    noisy = "المادة 1\nتثبت الحـــضانة   للأم‏.\r\n\n\n\nالمادة 2\nيسقط الحق."
    path = inbox / "noisy.txt"
    path.write_text(noisy, encoding="utf-8")
    canonical = normalize(path)

    assert "ـ" not in canonical.body, "التطويل يُحذف"
    assert "‏" not in canonical.body, "المحارف غير المرئية تُحذف"
    assert "\r" not in canonical.body
    assert "\n\n\n" not in canonical.body
    assert "تثبت الحضانة للأم" in canonical.body, "المحتوى القانوني لا يتغير"
    assert "المادة 1" in canonical.body and "المادة 2" in canonical.body

    markdown = canonical.to_markdown()
    assert markdown.startswith("---"), "ترويسة تدقيق إلزامية"
    assert canonical.source_sha256 in markdown
    assert canonical.body in markdown, "المتن يُحفظ كاملًا في الأرشيف"

    # التطبيع مستقر (idempotent): إعادة تطبيع متن مُطبَّع لا تغيّره، فالبصمة ثابتة
    # مهما تكرّر المرور. هذا شرط منع التكرار: لولاه لاختلفت بصمة النص عن نفسه.
    assert eng.content_digest(canonical.body) == eng.content_digest(eng.normalize_text(canonical.body))
    assert normalize(path).body == canonical.body, "التطبيع حتمي عبر المرات"

    # وبصمة النص نفسه لا تتأثر بضوضاء الصيغة: نسخة «نظيفة» تعطي البصمة ذاتها.
    clean = inbox / "clean.txt"
    clean.write_text("المادة 1\nتثبت الحضانة للأم.\nالمادة 2\nيسقط الحق.", encoding="utf-8")
    assert eng.content_digest(normalize(clean).body) == eng.content_digest(canonical.body), (
        "التطويل والمحارف غير المرئية لا تُنتج مصدرًا مختلفًا"
    )


# ── 7) الإدراج في PostgreSQL ──────────────────────────────────────
def test_postgres_insert(workspace):
    inbox, archive, failed = workspace
    result = eng.ingest_file(put_source(inbox, "law.md", LEGISLATION), archive, failed)
    rows = query(
        """SELECT id, object_type, branch, topic, subtopic, verification_status,
                  authority_status, usable_as_citation, original_text
           FROM knowledge_objects WHERE branch=%s ORDER BY id""", (TEST_BRANCH,))
    assert len(rows) == 2
    assert rows[0][1] == "legislation"
    assert rows[0][2] == TEST_BRANCH and rows[0][3] == TEST_TOPIC
    assert rows[0][4] == "الحضانة وسقوطها", "عنوان التصنيف يُحفظ"
    assert rows[0][5] == "source_verified"
    assert rows[0][6] == "source_authority" and rows[0][7] is True
    assert "الحضانة" in rows[0][8], "النص الأصلي يُحفظ حرفيًا"

    src = query("SELECT content_sha256, branch, topic, first_batch_id FROM sources WHERE branch=%s",
                (TEST_BRANCH,))
    assert len(src) == 1
    assert src[0][0] == result["content_sha256"]
    assert src[0][3] == result["batch_id"]


# ── 8) الفهرسة في Qdrant ──────────────────────────────────────────
def test_qdrant_indexing(workspace):
    inbox, archive, failed = workspace
    result = eng.ingest_file(put_source(inbox, "law.md", LEGISLATION), archive, failed)
    for object_id in result["objects"]:
        point = eng.qdrant_request(
            "POST", f"/collections/{eng.COLLECTION}/points",
            {"ids": [embedding.point_id(object_id)], "with_payload": True, "with_vector": True},
        )["result"]
        assert point, f"لا نقطة مفهرسة للكائن {object_id}"
        assert len(point[0]["vector"]) == embedding.VECTOR_SIZE == 768
        payload = point[0]["payload"]
        assert payload["object_id"] == object_id
        assert payload["branch"] == TEST_BRANCH
        assert payload["embedding_model"] == embedding.MODEL_ID
        assert "hash" not in payload.get("embedding_model", "").lower(), "hash_embedding محظور"


# ── 9) اتساق PostgreSQL وQdrant ───────────────────────────────────
def test_postgres_qdrant_consistency(workspace):
    inbox, archive, failed = workspace
    eng.ingest_file(put_source(inbox, "law.md", LEGISLATION), archive, failed)
    ids = [r[0] for r in query("SELECT id FROM knowledge_objects WHERE branch=%s", (TEST_BRANCH,))]
    found = eng.qdrant_request(
        "POST", f"/collections/{eng.COLLECTION}/points",
        {"ids": [embedding.point_id(i) for i in ids], "with_payload": True},
    )["result"]
    assert len(found) == len(ids), "لكل كائن في PostgreSQL نقطة في Qdrant"
    assert {p["payload"]["object_id"] for p in found} == set(ids)


# ── 10) إعادة بناء Qdrant من PostgreSQL ───────────────────────────
def test_qdrant_rebuild(workspace):
    inbox, archive, failed = workspace
    result = eng.ingest_file(put_source(inbox, "law.md", LEGISLATION), archive, failed)
    object_id = result["objects"][0]

    # حذف النقطة يحاكي فقد الفهرس. المعرفة في PostgreSQL لا تتأثر.
    eng.qdrant_request("POST", f"/collections/{eng.COLLECTION}/points/delete?wait=true",
                       {"points": [embedding.point_id(object_id)]})
    gone = eng.qdrant_request("POST", f"/collections/{eng.COLLECTION}/points",
                              {"ids": [embedding.point_id(object_id)]})["result"]
    assert not gone

    report = eng.reindex()
    assert report["status"] == "reindexed"
    assert report["consistent"] is True, "بعد إعادة البناء يتطابق العدّان"
    assert report["postgres_objects"] == report["qdrant_points"]

    restored = eng.qdrant_request("POST", f"/collections/{eng.COLLECTION}/points",
                                  {"ids": [embedding.point_id(object_id)], "with_vector": True})["result"]
    assert restored, "النقطة تُستعاد من مصدر الحقيقة"
    assert len(restored[0]["vector"]) == embedding.VECTOR_SIZE


# ── 11) بوابة الصياغة لا تُفتح بلا مصادر كافية ────────────────────
def test_drafting_gate_closed_without_authorities():
    """البوابة تُفتح فقط بتشريع ومبدأ ونموذج معًا. غياب أيها يُبقيها مغلقة."""
    from admin.cases_api import evaluate_drafting_gate

    assert evaluate_drafting_gate(0, 0, 0) == "blocked_missing_authorities"
    assert evaluate_drafting_gate(5, 0, 3) == "blocked_missing_authorities", "بلا مبادئ: مغلقة"
    assert evaluate_drafting_gate(0, 4, 2) == "blocked_missing_authorities", "بلا تشريع: مغلقة"
    assert evaluate_drafting_gate(3, 2, 0) == "blocked_missing_authorities", "بلا نماذج: مغلقة"
    assert evaluate_drafting_gate(3, 2, 1) == "ready_for_grounded_draft"


# ── 12) القاعدة المستنبطة لا يُستشهد بها ──────────────────────────
def test_synthesized_rule_never_citable():
    """حماية على مستوى قاعدة البيانات، لا مجرد عرف تطبيقي."""
    # الاشتقاق في المحرك يمنعها أولًا.
    assert eng.authority_for("synthesized_rule", "source_verified") == ("non_authoritative", False)
    assert eng.authority_for("legislation", "machine_pending_human") == ("non_authoritative", False)

    # وقيد قاعدة البيانات يرفضها حتى لو تحايل عليها كود آخر.
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO sources(source_key, source_type, title, sha256, verification_status)
               VALUES ('SRC-TEST-SYNTH','synthesized_rule','قاعدة اختبار',
                       repeat('0',64),'machine_pending_human')
               ON CONFLICT (source_key) DO NOTHING"""
        )
        conn.commit()
    try:
        for authority, citable, why in [
            ("source_authority", False, "القاعدة المستنبطة لا تكون سلطة"),
            ("non_authoritative", True, "القاعدة المستنبطة لا يُستشهد بها"),
        ]:
            with pytest.raises(psycopg.errors.CheckViolation, match="ko_synthesized_rule"), db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO knowledge_objects(id,object_type,branch,topic,title,
                               original_text,normalized_text,source_key,verification_status,
                               authority_status,usable_as_citation)
                           VALUES (%s,'synthesized_rule',%s,%s,'قاعدة مستنبطة','نص','نص',
                                   'SRC-TEST-SYNTH','machine_pending_human',%s,%s)""",
                        (f"SYN-TEST-{authority}", TEST_BRANCH, TEST_TOPIC, authority, citable),
                    )
    finally:
        with db() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM knowledge_objects WHERE source_key='SRC-TEST-SYNTH'")
            cur.execute("DELETE FROM sources WHERE source_key='SRC-TEST-SYNTH'")
            conn.commit()


# ── أدوات ──────────────────────────────────────────────────────────
def query(sql: str, params: tuple = ()) -> list[tuple]:
    with db() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def count_objects() -> int:
    return query("SELECT COUNT(*) FROM knowledge_objects WHERE branch=%s", (TEST_BRANCH,))[0][0]


def count_sources() -> int:
    return query("SELECT COUNT(*) FROM sources WHERE branch=%s", (TEST_BRANCH,))[0][0]
