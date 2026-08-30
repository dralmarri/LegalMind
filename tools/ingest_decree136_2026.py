# -*- coding: utf-8 -*-
"""
مرسوم رقم 136 لسنة 2026 باستبدال الجدول المرافق للمرسوم رقم (126) لسنة 2018 بشأن المدد اللازمة
كحد أدنى للبقاء في درجات القضاة وأعضاء النيابة العامة.
مصدر: الكويت اليوم، العدد 1806، السنة الثانية والسبعون، الأحد 17 ربيع الأول 1448هـ الموافق
2026/8/30م (صورة رسمية) + نشر الأنباء الرقمي (media.alanba.com.kw) للجدول — تحقق مزدوج مطابق
حرفيًا مع نسخة COMPANION_DECREE المُعدَّة سلفًا في tools/ingest_judiciary80_2026.py من قراءة
المسودة الأولى (قبل صدور الرقم الرسمي) — تطابق تام بين ثلاثة مصادر مستقلة.
صدر بقصر بيان في 13 ربيع الأول 1448هـ الموافق 26 أغسطس 2026م.
"""

LAWNUM = 136
YEAR = 2026
GAZETTE_REF = "الكويت اليوم، العدد 1806، السنة الثانية والسبعون، الأحد 17 ربيع الأول 1448هـ الموافق 2026/8/30م"
GAZETTE_DATE = "2026-08-30"
ISSUED_DATE = "2026-08-26"  # صدر بقصر بيان — 13 ربيع الأول 1448هـ
INSTRUMENT = "مرسوم رقم %d لسنة %d" % (LAWNUM, YEAR)
INSTRUMENT_RANK = "مرسوم"  # لا مرسوم بقانون

PREAMBLE = """بعد الاطلاع على الدستور،
وعلى قانون تنظيم القضاء الصادر بالمرسوم بقانون رقم (80) لسنة 2026،
وعلى المرسوم رقم (126) لسنة 2018 بشأن الجدول المرافق للمرسوم رقم (41) لسنة 2009 بشأن المدد اللازمة كحد أدنى للبقاء في درجات القضاة وأعضاء النيابة العامة،
وبناء على عرض وزير العدل،
وبعد موافقة مجلس الوزراء،
رسمنا بالآتي:"""

ARTICLE_1 = """يستبدل بجدول المدد اللازمة كحد أدنى للبقاء في درجات القضاة وأعضاء النيابة العامة، بالجدول المرافق للمرسوم رقم (126) لسنة 2018 المشار إليه، وذلك دون إخلال بالمزايا والعلاوات المخصصة لكل درجة."""

ARTICLE_2 = """على الوزراء - كل فيما يخصه - تنفيذ هذا المرسوم، وينشر في الجريدة الرسمية، ويعمل به من تاريخ نشره."""

SIGNATORIES_TEXT = """أمير الكويت: مشعل الأحمد الجابر الصباح
رئيس مجلس الوزراء: أحمد عبدالله الأحمد الصباح
وزير العدل: المستشار/ يوسف محمد السبيعي
صدر بقصر بيان في: 13 ربيع الأول 1448هـ الموافق 26 أغسطس 2026م"""

TABLE_ROWS = [
    ("رئيس محكمة التمييز", "---"),
    ("نائب رئيس محكمة التمييز / رئيس محكمة الاستئناف / النائب العام / نائب رئيس محكمة الاستئناف / رئيس المحكمة الكلية", "---"),
    ("مستشار أول في محكمة التمييز / مستشار أول في محكمة الاستئناف / نائب رئيس المحكمة الكلية / النائب العام المساعد", "---"),
    ("مستشار بمحكمة الاستئناف / محامي عام", "ثلاث سنوات"),
    ("وكيل محكمة بالمحكمة الكلية / رئيس نيابة (أ)", "ثلاث سنوات"),
    ("قاضي من الدرجة الأولى / رئيس نيابة (ب)", "ثلاث سنوات"),
    ("قاضي من الدرجة الثانية / وكيل نيابة (أ)", "ثلاث سنوات"),
    ("قاضي من الدرجة الثالثة / وكيل نيابة (ب)", "ثلاث سنوات"),
    ("وكيل نيابة (ج)", "أربع سنوات"),
]


def build_table_text():
    lines = ["جدول المدد اللازمة كحد أدنى للبقاء في درجات القضاة وأعضاء النيابة العامة", ""]
    for job, dur in TABLE_ROWS:
        lines.append("الوظيفة: %s — المدة اللازمة كحد أدنى للبقاء: %s" % (job, dur))
    return "\n\n".join(lines)


if __name__ == "__main__":
    print("مواد الديباجة/الإصدار: 2 (أولى/ثانية) + ديباجة + جدول")
    print("صفوف الجدول:", len(TABLE_ROWS), "(المتوقع 9)")
    assert len(TABLE_ROWS) == 9
    print("STRUCTURE_OK")

# ═══ مُشغِّل الإدخال ═══
import sys, os, json
sys.path.insert(0, "/opt/LegalMind")
os.chdir("/opt/LegalMind")

import psycopg
from psycopg.types.json import Jsonb
from engine.normalizer.canonical import normalize_text

BRANCH = "إداري"  # مطابق حرفيًا لتصنيف legis-80-2026 الحي في القاعدة (الموضوع نفسه: القضاة والنيابة)
TOPIC = "المدد اللازمة كحد أدنى للبقاء في درجات القضاة وأعضاء النيابة العامة"


def _row(rid, otype, title, text, extra_meta):
    meta = {
        "law_number": LAWNUM, "law_year": YEAR,
        "instrument": INSTRUMENT, "instrument_rank": INSTRUMENT_RANK,
        "gazette_ref": GAZETTE_REF, "gazette_date": GAZETTE_DATE,
        "issued_date": ISSUED_DATE,
        "amends": "المرسوم رقم (126) لسنة 2018 (غير موجود في القاعدة)",
        "upload_origin": "gazette_official_%s" % GAZETTE_DATE,
        "table_cross_verified": True,
        "extraction_note": "الجدول قُرئ من مصدرين مستقلين متطابقين: صورة الجريدة الرسمية "
                            "(خط زخرفي) ونشر الأنباء الرقمي المطبوع (media.alanba.com.kw)، "
                            "وطابقا معًا نسخة مُعدَّة سلفًا من قراءة مسودة القانون الأصلي.",
    }
    meta.update(extra_meta)
    ntext = normalize_text(text)
    return {
        "id": rid, "object_type": otype, "branch": BRANCH,
        "topic": TOPIC, "subtopic": None, "micro_issue": None,
        "title": title, "original_text": text, "normalized_text": ntext,
        "source_key": None, "verification_status": "source_verified",
        "metadata": meta, "authority_status": "source_authority",
        "usable_as_citation": True,
    }


def build_all_records():
    out = []
    out.append(_row(
        "legis-%d-%d-preamble" % (LAWNUM, YEAR), "legislation_preamble",
        "ديباجة %s باستبدال الجدول المرافق للمرسوم رقم (126) لسنة 2018 بشأن المدد اللازمة "
        "كحد أدنى للبقاء في درجات القضاة وأعضاء النيابة العامة" % INSTRUMENT,
        PREAMBLE, {"issuing": True},
    ))
    out.append(_row(
        "legis-%d-%d-issuing-m1" % (LAWNUM, YEAR), "legislation_issuing_article",
        "المادة الأولى — %s" % INSTRUMENT, ARTICLE_1,
        {"issuing": True, "issuing_seq": 1, "issuing_label": "أولى"},
    ))
    out.append(_row(
        "legis-%d-%d-issuing-m2" % (LAWNUM, YEAR), "legislation_issuing_article",
        "المادة الثانية — %s" % INSTRUMENT, ARTICLE_2,
        {"issuing": True, "issuing_seq": 2, "issuing_label": "ثانية", "signatories_text": SIGNATORIES_TEXT},
    ))
    out.append(_row(
        "legis-%d-%d-annex-1" % (LAWNUM, YEAR), "legislation_article",
        "جدول المدد اللازمة كحد أدنى للبقاء في درجات القضاة وأعضاء النيابة العامة — %s" % INSTRUMENT,
        build_table_text(),
        {"issuing": False, "is_table": True, "table_rows": TABLE_ROWS},
    ))
    return out


def main():
    dsn = os.environ["DATABASE_URL"]

    # فحص وجوبي: لا تصادم بادئة قبل أي إدخال (قاعدة دائمة من حادثة legis-11-2026 §9)
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM knowledge_objects WHERE id LIKE %s", ("legis-%d-%d-%%" % (LAWNUM, YEAR),))
        existing = [r[0] for r in cur.fetchall()]
    if existing:
        print("PREFIX_COLLISION_CHECK: يوجد %d كائن سابق بنفس البادئة:" % len(existing))
        for e in existing:
            print("  -", e)
        print("سيُحدَّث هذا الكائن (ON CONFLICT DO UPDATE) — راجع القائمة أعلاه قبل المتابعة.")
    else:
        print("PREFIX_COLLISION_CHECK: نظيفة — لا تصادم.")

    records = build_all_records()
    assert len(records) == 4, "العدد غير متوقع: %d (المتوقع 4)" % len(records)
    ids = [r["id"] for r in records]
    assert len(ids) == len(set(ids)), "معرفات مكررة!"

    sql = """
        INSERT INTO knowledge_objects
            (id, object_type, branch, topic, subtopic, micro_issue, title,
             original_text, normalized_text, source_key, verification_status,
             metadata, authority_status, usable_as_citation)
        VALUES (%(id)s, %(object_type)s, %(branch)s, %(topic)s, %(subtopic)s,
                %(micro_issue)s, %(title)s, %(original_text)s, %(normalized_text)s,
                %(source_key)s, %(verification_status)s, %(metadata)s,
                %(authority_status)s, %(usable_as_citation)s)
        ON CONFLICT (id) DO UPDATE SET
            object_type = EXCLUDED.object_type, branch = EXCLUDED.branch,
            topic = EXCLUDED.topic, subtopic = EXCLUDED.subtopic,
            micro_issue = EXCLUDED.micro_issue, title = EXCLUDED.title,
            original_text = EXCLUDED.original_text,
            normalized_text = EXCLUDED.normalized_text,
            verification_status = EXCLUDED.verification_status,
            metadata = EXCLUDED.metadata, authority_status = EXCLUDED.authority_status,
            usable_as_citation = EXCLUDED.usable_as_citation,
            updated_at = now()
    """

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            for r in records:
                row = dict(r)
                row["metadata"] = Jsonb(row["metadata"])
                cur.execute(sql, row)
        conn.commit()

    print("INGEST_OK: %d كائنًا أُدخل/حُدِّث" % len(records))

    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM knowledge_objects WHERE id LIKE %s", ("legis-%d-%d-%%" % (LAWNUM, YEAR),))
        n_new = cur.fetchone()[0]
        print("تحقق: legis-%d-%d = %d كائنًا (متوقع 4)" % (LAWNUM, YEAR, n_new))
        assert n_new == 4

    print("VERIFY_OK")


if __name__ == "__main__":
    main()
