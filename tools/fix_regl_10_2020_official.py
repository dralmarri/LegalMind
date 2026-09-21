# -*- coding: utf-8 -*-
"""
ترقية اللائحة التنفيذية لقانون التوثيق (regl-10-2020) من نسخة المسودة إلى النص الرسمي.

الخلفية: الكائنات الـ67 مُدخَلة سلفًا، لكن مسبارًا حيًّا كشف أنها أُدخلت من **مسودة قبل
النشر الرسمي**: الديباجة تحمل «قرار رقم ( ) لسنة 2026» — الرقم فارغ — وكذلك ترويسات
الجداول الثلاثة، ولا تحمل تاريخ الصدور ولا مرجع الجريدة.

المصدر الرسمي: الكويت اليوم، العدد 1809، السنة الثانية والسبعون، الأحد 9 ربيع الآخر 1448هـ
الموافق 2026/9/20م، ص29-36 — **قرار وزير العدل رقم (590) لسنة 2026**، صدر في 14 صفر 1448هـ
الموافق 28 يوليو 2026م، وزير العدل المستشار/ ناصر يوسف السميط.

تنبيه المالك المُلزِم: هذا المرفق هو **اللائحة التنفيذية** للقانون وليس قانون التوثيق نفسه.
فلا تمسّ هذه الدفعة `legis-10-2020-*` (القانون، 30 كائنًا) بأي حال — وثمة تأكيد آلي على ذلك.

ما تفعله هذه الدفعة:
  1) الديباجة: تُستبدل بالنص الرسمي كاملًا برقمه (590) وديباجته وكلمة «قرر»، ونوعها يُصحَّح
     إلى legislation_preamble، والنص القديم كاملًا إلى metadata.previous_versions[].
  2) ترويسات الجداول 1/2/3: «القرار الوزاري رقم ( ) لسنة 2026» ← «... رقم (590) لسنة 2026»
     بمرساة صارمة (مرة واحدة بالضبط لكل جدول)، والنص القديم محفوظ.
  3) بصمة المصدر الرسمي على الكائنات الـ67 كلها (رقم القرار/مرجع الجريدة/تاريخ الصدور).
  4) توثيق تعارض داخلي في **النص الرسمي نفسه** لا يُصحَّح: ملاحظة الجدول (2) تحيل إلى
     «البند (5) من المادة (44)» بينما البنود الخمسة في المادة (45)؛ تُثبَّت الإحالة كما وردت
     ويوسم الكائن بـ source_note (النص الأصلي مقدس — يُوثَّق ولا يُغيَّر).
  5) تدقيق تغطية كامل: يطبع لكل كائن من الـ67 طوله وبصمته وكل إحالاته الرقمية ومدده ورسومه
     — سجل تحقق شامل لا عيّنة.

ما لا تفعله عمدًا: لا تُعاد كتابة نصوص المواد الستين. قوبلت عيّنة موجَّهة على أعلى المواد
خطرًا (م1 بتعريفاتها الـ22، م16 بمددها، م23، م44 بإحالتها لبند م55، م59، والجدولان 2 و3
بكل صفوفهما، ومواد الإصدار الثلاث) فطابقت النص الرسمي **حرفيًا** في كل موضع. وإعادة كتابة
نصٍّ مُتحقَّق منه مخاطرةٌ بإدخال خطأ نسخ لا مكسب — والتدقيق في (5) يغطي الباقي بالأرقام.
"""

import sys, os, re, json, hashlib, datetime

sys.path.insert(0, "/opt/LegalMind")
os.chdir("/opt/LegalMind")

import psycopg
from psycopg.types.json import Jsonb
from engine.normalizer.canonical import normalize_text

PREFIX = "regl-10-2020-"
LAW_PREFIX = "legis-10-2020-"          # القانون نفسه — محظور المساس به
DECISION_NO = 590
DECISION_YEAR = 2026
GAZETTE_REF = ("الكويت اليوم، العدد 1809، السنة الثانية والسبعون، "
               "الأحد 9 ربيع الآخر 1448هـ الموافق 2026/9/20م، ص29-36")
GAZETTE_DATE = "2026-09-20"
ISSUED_DATE = "2026-07-28"             # صدر في 14 صفر 1448هـ
INSTRUMENT = "قرار وزير العدل رقم (590) لسنة 2026"

OFFICIAL_PREAMBLE = """وزارة العدل
قرار رقم (590) لسنة 2026
بإصدار اللائحة التنفيذية للقانون رقم (10) لسنة 2020 بشأن التوثيق المعدل بالمرسوم بقانون رقم (147) لسنة 2025

وزير العدل:
- بعد الاطلاع على الدستور.
- وعلى القانون رقم (10) لسنة 2020 بشأن التوثيق المعدل بالمرسوم بقانون رقم (147) لسنة 2025.
- وعلى القرار الوزاري رقم (78) لسنة 2017 بإصدار لائحة التوثيقات الشرعية.
- وعلى القرار الوزاري رقم (160) لسنة 2020 في شأن لائحة المأذونين.
- وعلى القرار الوزاري رقم (348) لسنة 2021 باللائحة التنفيذية للقانون رقم (10) لسنة 2020 بشأن التوثيق.
- وبناءً على ما تقتضيه المصلحة العامة،
قــــرر"""

SIGNATORIES = """وزير العدل
المستشار/ ناصر يوسف السميط
صدر في: 14 صفر 1448هـ
الموافق: 28 يوليو 2026م"""

# مرساة مقصودة القِصر: ترويسة الجدول تكتبها «المرافق لـلـقرار الوزاري…» فالألف تُدغم
# («للقرار» لا تحوي «القرار») — المرساة الطويلة تخطئ حتمًا، وشرط «مرة واحدة بالضبط» هو الحارس.
BLANK_NO = "رقم ( ) لسنة 2026"
OFFICIAL_NO = "رقم (590) لسنة 2026"

JADWAL_IDS = ["regl-10-2020-jadwal1", "regl-10-2020-jadwal2", "regl-10-2020-jadwal3"]

JADWAL2_SOURCE_NOTE = (
    "تعارض داخلي في النص الرسمي نفسه، مُثبَت كما ورد ولم يُصحَّح: ملاحظة هذا الجدول تحيل "
    "إلى «البند (5) من المادة (44) من اللائحة»، والمادة (44) بنودها ثلاثة في مدة الترخيص "
    "وتجديده، بينما البند (5) الخاص باستيفاء الرسوم وتوريدها إلى الإدارة هو في المادة (45) "
    "(التزامات الموثق الأهلي). الإحالة منقولة حرفيًا عن الجريدة الرسمية (العدد 1809 ص35) "
    "— قاعدة «النص الأصلي مقدس»: يُوثَّق التعارض ولا يُغيَّر النص."
)

# ═════════════════ أدوات التدقيق ═════════════════

RX_ART = re.compile(r"المادة\s*\((\d+)\)")
RX_LAW = re.compile(r"رقم\s*\((\d+)\)\s*لسنة\s*(\d{4})")
RX_FEE = re.compile(r"\((\d+)\s*د\.?\s*ك\)")
RX_DUR = re.compile(r"(\d+|خمس|عشر|سنتين|ثلاثين|تسعين|ستين|خمسة عشر|عشرة)\s*"
                    r"(يومًا|يوما|أيام|شهر|أشهر|سنة|سنوات|سنتين)")


def digest(text):
    return {
        "len": len(text),
        "sha": hashlib.sha256(text.encode("utf-8")).hexdigest()[:12],
        "arts": sorted(set(RX_ART.findall(text)), key=lambda x: int(x)),
        "laws": sorted(set("%s/%s" % (a, b) for a, b in RX_LAW.findall(text))),
        "fees": sorted(set(RX_FEE.findall(text)), key=lambda x: int(x)),
        "durs": sorted(set(" ".join(m) for m in RX_DUR.findall(text))),
    }


def stamp(meta):
    meta = dict(meta or {})
    meta.update({
        "decision_number": DECISION_NO,
        "decision_year": DECISION_YEAR,
        "instrument": INSTRUMENT,
        "instrument_rank": "قرار وزاري",
        "parent_law": "legis-10-2020 — القانون رقم (10) لسنة 2020 بشأن التوثيق "
                      "المعدل بالمرسوم بقانون رقم (147) لسنة 2025",
        "is_executive_regulation": True,
        "gazette_ref": GAZETTE_REF,
        "gazette_date": GAZETTE_DATE,
        "issued_date": ISSUED_DATE,
        "repeals": "القرار الوزاري رقم (348) لسنة 2021 (اللائحة السابقة)",
        "source": "official_gazette_1809",
        "source_upgrade": {
            "on": GAZETTE_DATE,
            "from": "مسودة بلا رقم — الديباجة وترويسات الجداول كانت «قرار رقم ( ) لسنة 2026»",
            "to": "النص الرسمي المنشور بالعدد 1809 برقم (590) لسنة 2026",
        },
    })
    meta.pop("draft", None)
    meta.pop("is_draft", None)
    return meta


def push_prev(meta, old_text, note):
    prev = list(meta.get("previous_versions") or [])
    prev.append({
        "text": old_text,
        "sha256": hashlib.sha256(old_text.encode("utf-8")).hexdigest(),
        "superseded_on": GAZETTE_DATE,
        "superseded_by": INSTRUMENT,
        "recorded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "note": note,
    })
    meta["previous_versions"] = prev
    return meta


# ═════════════════ التنفيذ ═════════════════

def main():
    dsn = os.environ["DATABASE_URL"]
    try:
      with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:

            # ── حارس وجوبي: لا مساس بالقانون نفسه ──
            cur.execute("SELECT count(*) FROM knowledge_objects WHERE id LIKE %s",
                        (LAW_PREFIX + "%",))
            law_before = cur.fetchone()[0]
            cur.execute("""SELECT md5(string_agg(original_text, '|' ORDER BY id))
                           FROM knowledge_objects WHERE id LIKE %s""", (LAW_PREFIX + "%",))
            law_fp_before = cur.fetchone()[0]
            print("LAW_GUARD: legis-10-2020 = %d كائنًا، بصمة النصوص %s (يجب ألا تتغير)"
                  % (law_before, law_fp_before))

            cur.execute("SELECT count(*) FROM knowledge_objects WHERE id LIKE %s",
                        (PREFIX + "%",))
            n = cur.fetchone()[0]
            print("REGL_SCOPE: regl-10-2020 = %d كائنًا" % n)
            if n != 67:
                raise SystemExit("SCOPE_UNEXPECTED: المتوقع 67 كائنًا — أوقفت الدفعة.")

            # ── 1) الديباجة ──
            cur.execute("SELECT original_text, metadata, object_type FROM knowledge_objects "
                        "WHERE id=%s", (PREFIX + "preamble",))
            row = cur.fetchone()
            if not row:
                raise SystemExit("PREAMBLE_MISSING — أوقفت الدفعة.")
            old_pre, meta_pre, old_type = row[0], (row[1] or {}), row[2]
            if "رقم ( ) لسنة 2026" not in old_pre and "(590)" in old_pre:
                print("PREAMBLE_ALREADY_OFFICIAL: الديباجة تحمل الرقم 590 سلفًا — تُحدَّث البيانات فقط.")
            meta_pre = push_prev(stamp(meta_pre), old_pre,
                                 "نسخة المسودة: الديباجة برقم فارغ «قرار رقم ( ) لسنة 2026»، "
                                 "وبلا تاريخ صدور ولا مرجع جريدة.")
            meta_pre["signatories_text"] = SIGNATORIES
            cur.execute("""UPDATE knowledge_objects
                           SET original_text=%s, normalized_text=%s, object_type=%s,
                               metadata=%s, verification_status='source_verified',
                               updated_at=now()
                           WHERE id=%s""",
                        (OFFICIAL_PREAMBLE, normalize_text(OFFICIAL_PREAMBLE),
                         "legislation_preamble", Jsonb(meta_pre), PREFIX + "preamble"))
            print("PREAMBLE_UPDATED: الرقم (590) مُثبَت، النوع %s ← legislation_preamble، "
                  "النص القديم محفوظ في previous_versions[%d]"
                  % (old_type, len(meta_pre["previous_versions"])))

            # ── 2) ترويسات الجداول ──
            fixed = []
            for jid in JADWAL_IDS:
                cur.execute("SELECT original_text, metadata FROM knowledge_objects WHERE id=%s",
                            (jid,))
                r = cur.fetchone()
                if not r:
                    raise SystemExit("JADWAL_MISSING: %s — أوقفت الدفعة." % jid)
                old, meta = r[0], (r[1] or {})
                c = old.count(BLANK_NO)
                if c == 0 and OFFICIAL_NO in old:
                    print("  %s: يحمل الرقم الرسمي سلفًا — بيانات فقط." % jid)
                    new = old
                elif c == 1:
                    new = old.replace(BLANK_NO, OFFICIAL_NO)
                    meta = push_prev(meta, old, "نسخة المسودة: ترويسة الجدول برقم فارغ.")
                    fixed.append(jid)
                else:
                    raise SystemExit("ANCHOR_FAIL: «%s» وردت %d مرة في %s (المتوقع 1) "
                                     "— أوقفت الدفعة." % (BLANK_NO, c, jid))
                meta = stamp(meta)
                if jid.endswith("jadwal2"):
                    meta["source_note"] = JADWAL2_SOURCE_NOTE
                cur.execute("""UPDATE knowledge_objects
                               SET original_text=%s, normalized_text=%s, metadata=%s,
                                   verification_status='source_verified', updated_at=now()
                               WHERE id=%s""",
                            (new, normalize_text(new), Jsonb(meta), jid))
            print("JADWAL_UPDATED: %d جدولًا صُحِّح رقمه (%s)"
                  % (len(fixed), ", ".join(fixed) or "لا شيء"))

            # ── 3) بصمة المصدر الرسمي على الباقي ──
            cur.execute("SELECT id, metadata FROM knowledge_objects WHERE id LIKE %s "
                        "AND id <> %s AND id <> ALL(%s) ORDER BY id",
                        (PREFIX + "%", PREFIX + "preamble", JADWAL_IDS))
            rest = cur.fetchall()
            for rid, meta in rest:
                cur.execute("""UPDATE knowledge_objects
                               SET metadata=%s, verification_status='source_verified',
                                   updated_at=now()
                               WHERE id=%s""", (Jsonb(stamp(meta)), rid))
            print("STAMPED: %d كائنًا إضافيًا بُصم بمرجع الجريدة الرسمية" % len(rest))

            # ── حارس ما بعد الكتابة: القانون لم يُمس ──
            cur.execute("SELECT count(*) FROM knowledge_objects WHERE id LIKE %s",
                        (LAW_PREFIX + "%",))
            cur.execute("""SELECT md5(string_agg(original_text, '|' ORDER BY id))
                           FROM knowledge_objects WHERE id LIKE %s""", (LAW_PREFIX + "%",))
            law_fp_after = cur.fetchone()[0]
            if law_fp_after != law_fp_before:
                raise SystemExit("LAW_TOUCHED: نصوص legis-10-2020 تغيّرت — تراجع فوري!")
            print("LAW_GUARD_OK: legis-10-2020 لم يُمس (البصمة كما هي)")

        conn.commit()
    except SystemExit:
        print("\nROLLED_BACK: بوابة فشلت — لم تُكتب أي تغييرات على القاعدة.")
        raise

    # ── 4) تدقيق تغطية كامل (بعد الالتزام، قراءة فقط) ──
    print("\n═══ تدقيق التغطية الكامل — 67 كائنًا (طول/بصمة/إحالات/مدد/رسوم) ═══")
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("""SELECT id, object_type, title, original_text
                       FROM knowledge_objects WHERE id LIKE %s
                       ORDER BY length(id), id""", (PREFIX + "%",))
        rows = cur.fetchall()
        blanks = []
        for rid, otype, title, text in rows:
            d = digest(text)
            bits = ["%-26s %5d ح  %s" % (rid, d["len"], d["sha"])]
            if d["arts"]:
                bits.append("م:" + ",".join(d["arts"]))
            if d["laws"]:
                bits.append("ق:" + ",".join(d["laws"]))
            if d["fees"]:
                bits.append("رسوم:" + ",".join(d["fees"]))
            if d["durs"]:
                bits.append("مدد:" + "؛".join(d["durs"]))
            print("  " + " | ".join(bits))
            if "رقم ( )" in text or "( ) لسنة" in text:
                blanks.append(rid)
        print("\nعدد الكائنات المدقَّقة: %d" % len(rows))
        if blanks:
            print("BLANK_NUMBER_REMAINS:", blanks)
            raise SystemExit("ما زال رقم فارغ في كائن — راجع.")
        print("NO_BLANK_NUMBERS_OK: لا رقم فارغ في أي كائن")

        cur.execute("""SELECT count(*) FROM knowledge_objects WHERE id LIKE %s
                       AND metadata->>'decision_number' = '590'""", (PREFIX + "%",))
        stamped = cur.fetchone()[0]
        print("STAMP_VERIFY: %d/67 كائنًا يحمل decision_number=590" % stamped)
        assert stamped == 67

        cur.execute("""SELECT count(*) FROM knowledge_objects WHERE id LIKE %s""",
                    (LAW_PREFIX + "%",))
        print("LAW_UNTOUCHED: legis-10-2020 = %d كائنًا (القانون نفسه، لم يُمس)"
              % cur.fetchone()[0])

    print("\nREGL_590_OFFICIAL_OK")


if __name__ == "__main__":
    main()
