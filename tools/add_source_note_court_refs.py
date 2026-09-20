# -*- coding: utf-8 -*-
"""
ملاحظة مرجعية على المواد النافذة التي تحيل إلى «محكمة سوق المال» — **بلا مساس بالنص**.

بقرار المالك بعد عرض الخيارين: المادتان 114 و130 من القانون 7/2010 **نافذتان**
وتحيلان إلى «محكمة سوق المال»، والمرسوم بقانون 91/2026 ألغى بمادته الثالثة المواد
المنشئة لتلك المحكمة والمنظمة لاختصاصها (108-113 و116)، لكن أمر الاستبدال في مادته
الأولى سمّى «محكمة **أسواق** المال» وحدها فلم يبلغ هذه الصيغة. فالنص يبقى كما ورد
في الجريدة الرسمية حرفًا بحرف — والتنبيه يُسجَّل في `metadata` لا في المتن.

**حدٌّ معلن بصراحة:** `metadata.source_note` **لا يظهر اليوم في أي واجهة**: لا في
مخرج أدوات MCP (لا تختار `metadata` أصلًا) ولا في سياق استوديو الصياغة
(`SELECT id, title, original_text` وحدها). فهذه الجولة قيمتها **توثيقية وتدقيقية**،
ولا تجعل المحامي يرى التنبيه عند الاستشهاد — إظهاره يحتاج جولة عرض مستقلة تُقاس
ببطاريتين. (وهو ما ينطبق على كل `source_note` مكتوبة سابقًا: إحالة الجدول (2) إلى
م44 في لائحة التوثيق، وسهو «في أن» في م1 من 90/2026 — كلها غير مرئية اليوم.)

المنهج: اكتشافٌ من البيانات لا قائمةٌ ثابتة — تُمسح كل مواد المتن النافذة تحت
`legis-7-2010-` عن الصيغة (بمطابقة تقبل كسر السطر)، والمكتشَف يُطبع قبل الكتابة.

الضمانات:
  - **لا يُمسّ `original_text` ولا `normalized_text` إطلاقًا** — تُقاس بصمة md5 لنصوص
    القانون كله قبل وبعد، وأي تغيّر يُسقط المعاملة (`TEXT_TOUCHED`).
  - عدد كائنات القاعدة قبل وبعد يجب أن يتطابق (`COUNT_CHANGED`).
  - `source_note` قائمة سلفًا لا تُمحى — يُلحق التنبيه بعدها.
  - إعادة التشغيل بلا أثر (وسم `note_kind` + بصمة نص التنبيه).
  - **لا فهرسة**: لم يتغير نص ولا عنوان، فنقاط Qdrant كما هي (قاعدة §10 تبقى محفوظة).

النجاح = `NOTE_OK` (أو `NOTE_NOOP` إن لم تبقَ مادة تحتاج التنبيه).
"""

import sys, os, re, hashlib as _h, datetime

sys.path.insert(0, "/opt/LegalMind")
os.chdir("/opt/LegalMind")

import psycopg
from psycopg.types.json import Jsonb

LAW_PREFIX = "legis-7-2010-"
VARIANT = "محكمة سوق المال"
VARIANT_RX = re.compile(r"\s+".join(re.escape(w) for w in VARIANT.split()))
NOTE_KIND = "cross_reference_after_repeal"
NOTE_DATE = "2026-09-20"
NOTE_INSTRUMENT = "legis-91-2026-issue-1"
RELATED = ["legis-91-2026-issue-1", "legis-91-2026-issue-2",
           "legis-91-2026-issue-3", "legis-7-2010-m1"]

# كل جملة في التنبيه مسندة إلى كائن قائم في القاعدة — لا اجتهاد في أثر الإلغاء
NOTE = (
    "ملاحظة مرجعية (لا تعديل في النص): يرد في هذه المادة لفظ «محكمة سوق المال». "
    "وقد ألغت المادة الثالثة من المرسوم بقانون رقم (91) لسنة 2026 (الكويت اليوم، "
    "العدد 1809، 2026/9/20) المواد 108 و109 و110 و111 و112 و113 و116 من هذا القانون، "
    "وهي المواد المنشئة لمحكمة أسواق المال والمنظمة لاختصاصها وللطعن على أحكامها. "
    "وعرَّفت المادة الأولى من المرسوم ذاته (المحكمة المختصة) بأنها الدائرة الاقتصادية "
    "المدنية والتجارية أو الإدارية المنشأة بالمرسوم بقانون رقم (88) لسنة 2026، والمحكمة "
    "المختصة وفقًا للقواعد المقررة في قانون الإجراءات والمحاكمات الجزائية بحسب الأحوال. "
    "ونصت مادته الثانية على استمرار محكمة أسواق المال في نظر الدعاوى والطعون المقيدة "
    "لديها قبل تاريخ العمل به لحين الفصل فيها. "
    "ولم يشمل أمرُ الاستبدال الوارد في المادة الأولى عبارةَ «محكمة سوق المال» بهذه الصيغة "
    "— إذ سمّى «محكمة أسواق المال» — فبقي نص هذه المادة كما ورد في الجريدة الرسمية "
    "دون أي تغيير."
)
NOTE_SHA = _h.sha256(NOTE.encode("utf-8")).hexdigest()


def live_body_article(oid, otype, vstatus):
    return ((vstatus or "") != "superseded"
            and otype == "legislation_article"
            and re.match(r"^legis-7-2010-m\d+$", oid) is not None)


def law_fingerprint(cur):
    """بصمة نصوص القانون كله — حارس «لم يُمسّ حرف»."""
    cur.execute("""SELECT md5(string_agg(original_text || '␟' || coalesce(normalized_text,''),
                                         '|' ORDER BY id))
                   FROM knowledge_objects WHERE id LIKE %s""", (LAW_PREFIX + "%",))
    return cur.fetchone()[0]


def main():
    dsn = os.environ["DATABASE_URL"]
    touched = []
    try:
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM knowledge_objects")
                total_before = cur.fetchone()[0]
                fp_before = law_fingerprint(cur)

                cur.execute(
                    """SELECT id, object_type, verification_status, original_text, metadata
                       FROM knowledge_objects WHERE id LIKE %s ORDER BY id""",
                    (LAW_PREFIX + "%",))
                rows = cur.fetchall()
                if not rows:
                    raise SystemExit("LAW_MISSING: لا كائنات تحت %s — أوقفت الدفعة." % LAW_PREFIX)

                print("──── الاكتشاف من البيانات (لا قائمة ثابتة) ────")
                targets = []
                for oid, otype, vstatus, text, meta in rows:
                    n = len(VARIANT_RX.findall(text or ""))
                    if not n:
                        continue
                    live = live_body_article(oid, otype, vstatus)
                    print("  %s — «%s» ×%d — %s" % (
                        oid, VARIANT, n,
                        "مادة نافذة ← تُوسَم" if live else "ملغاة/غير متن ← تُترك"))
                    if live:
                        targets.append((oid, meta or {}))

                if not targets:
                    print("\nNOTE_NOOP: لا مادة نافذة تحمل الصيغة — لا شيء يُكتب.")
                    print("\nNOTE_OK")
                    return

                print("\n──── كتابة التنبيه في metadata وحدها ────")
                for oid, meta in targets:
                    if meta.get("note_kind") == NOTE_KIND and meta.get("note_sha256") == NOTE_SHA:
                        print("  %s — ALREADY_NOTED (إعادة تشغيل بلا أثر)" % oid)
                        continue
                    old_note = (meta.get("source_note") or "").strip()
                    # ملاحظة قائمة سلفًا لا تُمحى — القاعدة الثابتة: لا يُفقد توثيق
                    meta["source_note"] = (old_note + "\n\n" + NOTE) if old_note else NOTE
                    meta["note_kind"] = NOTE_KIND
                    meta["note_sha256"] = NOTE_SHA
                    meta["note_added"] = NOTE_DATE
                    meta["note_instrument"] = NOTE_INSTRUMENT
                    meta["note_related_ids"] = RELATED
                    meta["note_visibility"] = ("غير معروضة في أي واجهة اليوم — "
                                               "توثيقية وتدقيقية حتى تُبنى طبقة العرض")
                    cur.execute("""UPDATE knowledge_objects SET metadata=%s, updated_at=now()
                                   WHERE id=%s""", (Jsonb(meta), oid))
                    touched.append(oid)
                    print("  %s — NOTE_WRITTEN%s" % (
                        oid, " (أُلحق بملاحظة قائمة)" if old_note else ""))

                fp_after = law_fingerprint(cur)
                if fp_after != fp_before:
                    raise SystemExit("TEXT_TOUCHED: نصوص القانون تغيّرت — تراجع فوري! "
                                     "(هذه الجولة لا تمسّ نصًّا إطلاقًا)")
                cur.execute("SELECT count(*) FROM knowledge_objects")
                if cur.fetchone()[0] != total_before:
                    raise SystemExit("COUNT_CHANGED: عدد كائنات القاعدة تغيّر — تراجع فوري!")
            conn.commit()
    except SystemExit:
        print("\nROLLED_BACK: بوابة فشلت — لم تُكتب أي تغييرات على القاعدة.")
        raise

    print("\n──── تحقق بعد الكتابة ────")
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        for oid in touched:
            cur.execute("SELECT original_text, metadata FROM knowledge_objects WHERE id=%s",
                        (oid,))
            t, m = cur.fetchone()
            assert VARIANT_RX.search(t), "%s: النص تغيّر — الصيغة لم تعد فيه!" % oid
            assert m.get("note_sha256") == NOTE_SHA, "%s: التنبيه لم يُكتب" % oid
            print("  %s ✓ النص كما هو، والتنبيه مسجَّل (%d حرفًا)"
                  % (oid, len(m["source_note"])))
        print("  لا فهرسة: لم يتغير نص ولا عنوان — نقاط Qdrant كما هي.")
    print("\nNOTE_OK")


if __name__ == "__main__":
    main()
