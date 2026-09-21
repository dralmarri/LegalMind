# -*- coding: utf-8 -*-
"""
الاستبدال اللفظي الشامل الذي أمرت به الفقرة الثانية من المادة الأولى من المرسوم
بقانون رقم (91) لسنة 2026 (الكويت اليوم ع1809، 2026/9/20):

    «وتستبدل عبارتا "الوزير المختص" و "المحكمة المختصة"، بعبارتي "وزير التجارة
     والصناعة" و "محكمة أسواق المال" أينما وردتا في القانون رقم (7) لسنة 2010
     المشار إليه.»

هذا البند كان **مقيسًا ومؤجَّلًا بقرار** في دفعة العدد 1809 (§13): أمرُ استبدالٍ
صريحٌ لكنه كاسح في نصٍّ موثَّق عبر عشرات الكائنات، فطُبع «نصف قطر الانفجار» ولم
يُطبَّق آليًا. هذه الجولة تُنهيه بانضباط كامل.

المنهج — قياسٌ شاملٌ أولًا، ثم تطبيقٌ ضيّق:
  (1) مسح كل كائنات `legis-7-2010-%` بلا استثناء، وتصنيف كل ورود بفئته، وطباعة
      تقرير مفصَّل بسياق كل ورود (±60 حرفًا) **قبل أي كتابة**.
  (2) لا يُستبدل إلا ما اجتمع فيه شرطان:
        أ- العبارة **حرفيًا** كما سمّاها المرسوم (لا بمرادف ولا بصيغة أخرى)،
           وأي فراغ بين كلماتها يقبل كسر سطر — فكسر السطر خاصية نقلٍ عندنا لا
           صيغةٌ في الجريدة (أثبتته م2 حيًّا: «وزير التجارة\nوالصناعة»)؛
        ب- والكائن **مادةٌ نافذةٌ من متن القانون** (`legis-7-2010-mN`،
           `legislation_article`، وليست موسومة `superseded`).
  (3) وكل ما عدا ذلك **لا يُمسّ** ويُدرَج في التقرير باسمه لقرار المالك:
        - **المواد الملغاة** (108-113 و116، ألغاها هذا المرسوم نفسه بمادته
          الثالثة): نصها مُجمَّد عند لحظة الإلغاء، وإدخال مصطلح جديد فيها يفسد
          شهادتها التاريخية — والقاعدة الثابتة: لا يُمحى نص قط ولا يُحدَّث ملغى.
        - **مواد الإصدار والديباجة والمذكرة الإيضاحية**: ليست «القانون» الذي
          انصرف إليه أمر الاستبدال، ونسبتها إليه اجتهاد لا نقل.
        - **الصيغ المغايرة** («محكمة سوق المال» الواردة فعلًا في م114 وم116):
          لم يسمِّها المرسوم، فاستبدالها توسيعٌ لأمر المشرّع لا تنفيذ له.
        - **المطابقات الإملائية** (فرق همزة/ألف فقط عن العبارة المسمّاة): تُرصد
          وتُعرض ولا تُستبدل آليًا.

الضمانات:
  - كل الكتابات في معاملة واحدة؛ أي بوابة تفشل ترجع بالقاعدة كما كانت (`ROLLED_BACK`).
  - النص القديم كاملًا إلى `metadata.previous_versions[]` ببصمة sha256 وسند التعديل
    — ومنعُ التكرار بالبصمة لا بالعدّ، فإعادة التشغيل بلا أثر.
  - حارس نطاق: عدد كائنات القاعدة كلها قبل وبعد يجب أن يتطابق (لا إدراج ولا حذف)،
    وبصمة نصوص كل ما هو خارج المجموعة المستهدفة لا تتغير.
  - حارس استبدال: لكل كائن يُتحقق أن النص الجديد = النص القديم بالاستبدالين حرفيًا،
    وأن فرق الطول مساوٍ للمحسوب من عدد الورودات — لا رقعة عمياء.
  - معرفات ما تغيّر تُكتب في ملف ليفهرسها `reindex_delta.py` وحدها (لا فهرسة كاملة).

النجاح = `TERMSUB_OK` (أو `TERMSUB_NOOP` إن لم يبقَ ورودٌ واجب الاستبدال).
"""

import sys, os, re, hashlib as _h, datetime

sys.path.insert(0, "/opt/LegalMind")
os.chdir("/opt/LegalMind")

import psycopg
from psycopg.types.json import Jsonb
from engine.normalizer.canonical import normalize_text

LAW_PREFIX = "legis-7-2010-"
INSTRUMENT = "legis-91-2026-issue-1"
INSTRUMENT_LABEL = ("مرسوم بقانون رقم 91 لسنة 2026 — الفقرة الثانية من المادة الأولى "
                    "(legis-91-2026-issue-1)")
GAZETTE_DATE = "2026-09-20"
CHANGED_IDS_FILE = "/opt/legalmind-data/termsub_7_2010_changed_ids.txt"

# العبارتان كما سمّاهما المرسوم حرفيًا — لا يُزاد عليهما
SUBS = [
    ("وزير التجارة والصناعة", "الوزير المختص"),
    ("محكمة أسواق المال", "المحكمة المختصة"),
]

# صيغ واردة فعلًا في القانون لكن المرسوم لم يسمِّها — تُرصد ولا تُستبدل
UNNAMED_VARIANTS = ["محكمة سوق المال"]


def phrase_rx(phrase):
    """العبارة نفسها حرفيًا، لكن **أي فراغ بين كلماتها يقبل سطرًا جديدًا**.

    الجولة الأولى الحية أثبتت لزوم هذا: م2 (نافذة) تقول «يشرف عليها وزير التجارة\n
    والصناعة» — العبارة التي سمّاها المرسوم بعينها، لكن نقلنا نحن كسر السطر في
    منتصفها، فأخطأتها `str.count` وكادت تُفلت. كسر السطر خاصيةُ نقلٍ عندنا لا
    صيغةٌ في الجريدة، فتجاهله تنفيذٌ للأمر لا توسيعٌ له — بخلاف الهمزة والمرادف.
    """
    return re.compile(r"\s+".join(re.escape(w) for w in phrase.split()))


SUBS_RX = [(old, new, phrase_rx(old)) for old, new in SUBS]
VARIANT_RX = [(v, phrase_rx(v)) for v in UNNAMED_VARIANTS]


def _norm_ortho(s):
    """تطبيع إملائي للكشف فقط (همزات/ألفات/تاء مربوطة/مسافات) — لا يُكتب به شيء."""
    s = re.sub(r"[ـً-ْ]", "", s)
    s = s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    s = s.replace("ة", "ه").replace("ى", "ي").replace("ؤ", "و").replace("ئ", "ي")
    return re.sub(r"\s+", " ", s).strip()


def _push_prev(meta, old_text, note):
    """يضيف النص القديم إلى previous_versions[] ما لم يكن مضافًا ببصمته سلفًا."""
    sha = _h.sha256(old_text.encode("utf-8")).hexdigest()
    prev = list(meta.get("previous_versions") or [])
    if any(pv.get("sha256") == sha for pv in prev):
        return meta, False
    prev.append({
        "text": old_text,
        "sha256": sha,
        "superseded_on": GAZETTE_DATE,
        "superseded_by": note,
        "archived_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    })
    meta["previous_versions"] = prev
    return meta, True


def classify(oid, otype, vstatus):
    """فئة الكائن — هي وحدها التي تقرر: يُستبدل فيه أم يُعرض للقرار."""
    if (vstatus or "") == "superseded":
        return "ملغاة"
    if "-memo-" in oid:
        return "مذكرة"
    if otype == "legislation_preamble" or oid.endswith("-preamble"):
        return "ديباجة"
    if otype == "legislation_issuing_article" or "-issue" in oid:
        return "مواد الإصدار"
    if otype == "legislation_article" and re.match(r"^legis-7-2010-m\d+$", oid):
        return "مادة نافذة"
    return "أخرى"


APPLY_CLASS = "مادة نافذة"


def context_of(text, rx, width=60):
    """كل مواضع العبارة بسياقها — التقرير يُقرأ لا يُصدَّق على عمياء."""
    out = []
    for m in rx.finditer(text):
        a = max(0, m.start() - width)
        b = min(len(text), m.end() + width)
        snippet = re.sub(r"\s+", " ", text[a:b]).strip()
        out.append(("…" if a > 0 else "") + snippet + ("…" if b < len(text) else ""))
    return out


def scan(cur):
    """قياس شامل بلا أي كتابة. يعيد (صفوف_القانون، الورودات_المصنَّفة)."""
    cur.execute(
        """SELECT id, object_type, verification_status, original_text, metadata
           FROM knowledge_objects WHERE id LIKE %s ORDER BY id""",
        (LAW_PREFIX + "%",))
    rows = cur.fetchall()
    if not rows:
        raise SystemExit("LAW_MISSING: لا كائنات تحت %s — أوقفت الدفعة." % LAW_PREFIX)

    hits = []          # ورود حرفي للعبارتين المسمّاتين
    variant_hits = []  # صيغ لم يسمِّها المرسوم
    ortho_hits = []    # مطابقة إملائية فقط

    for oid, otype, vstatus, text, meta in rows:
        text = text or ""
        cls = classify(oid, otype, vstatus)
        ntext = _norm_ortho(text)
        for old, new, rx in SUBS_RX:
            n = len(rx.findall(text))
            if n:
                hits.append({"id": oid, "cls": cls, "old": old, "new": new,
                             "n": n, "ctx": context_of(text, rx)})
            # مطابقة إملائية بلا مطابقة حرفية = فرق همزة/ألف في نقلنا نحن
            n_norm = ntext.count(_norm_ortho(old))
            if n_norm > n:
                ortho_hits.append({"id": oid, "cls": cls, "old": old,
                                   "n": n_norm - n})
        for v, vrx in VARIANT_RX:
            n = len(vrx.findall(text))
            if n:
                variant_hits.append({"id": oid, "cls": cls, "phrase": v, "n": n,
                                     "ctx": context_of(text, vrx)})

    print("TERM_BLAST_RADIUS — القياس الشامل (لم يُكتب شيء بعد):")
    print("  كائنات القانون 7/2010 = %d" % len(rows))
    by_cls = {}
    for h in hits:
        by_cls.setdefault((h["old"], h["cls"]), [0, 0])
        by_cls[(h["old"], h["cls"])][0] += 1
        by_cls[(h["old"], h["cls"])][1] += h["n"]
    if by_cls:
        print("\n  العبارتان المسمّاتان في المرسوم — بالفئة:")
        for (old, cls), (nobj, nocc) in sorted(by_cls.items()):
            mark = "← تُستبدل" if cls == APPLY_CLASS else "← لا تُمسّ (تُعرض للقرار)"
            print("    «%s» / %-12s : %d كائنًا، %d ورودًا  %s" % (old, cls, nobj, nocc, mark))
    else:
        print("\n  العبارتان المسمّاتان: صفر ورود في القانون كله.")

    if hits:
        print("\n  تفصيل كل ورود بسياقه:")
        for h in sorted(hits, key=lambda x: (x["cls"], x["id"])):
            print("    [%s] %s — «%s» ×%d" % (h["cls"], h["id"], h["old"], h["n"]))
            for c in h["ctx"][:3]:
                print("        %s" % c)

    if variant_hits:
        print("\n  صيغ واردة في القانون لكن المرسوم لم يسمِّها — لا تُستبدل:")
        for v in sorted(variant_hits, key=lambda x: x["id"]):
            print("    [%s] %s — «%s» ×%d" % (v["cls"], v["id"], v["phrase"], v["n"]))
            for c in v["ctx"][:2]:
                print("        %s" % c)

    if ortho_hits:
        print("\n  ⚠ مطابقات إملائية (فرق همزة/ألف عن العبارة المسمّاة) — لا تُستبدل آليًا:")
        for o in sorted(ortho_hits, key=lambda x: x["id"]):
            print("    [%s] %s — قريبة من «%s» ×%d" % (o["cls"], o["id"], o["old"], o["n"]))
    return rows, hits


def apply_subs(cur, rows):
    """الاستبدال على مواد المتن النافذة وحدها. يعيد قائمة المعرفات التي تغيّرت."""
    changed = []
    for oid, otype, vstatus, text, meta in rows:
        if classify(oid, otype, vstatus) != APPLY_CLASS:
            continue
        old_text = text or ""
        matches = {old: rx.findall(old_text) for old, _, rx in SUBS_RX}
        if not any(matches.values()):
            continue

        new_text = old_text
        delta = 0
        applied = []
        for old, new, rx in SUBS_RX:
            got = matches[old]
            if got:
                new_text = rx.sub(new, new_text)
                # المقيس هو طول ما طابق فعلًا (قد يحمل كسر سطر)، لا طول العبارة المجردة
                delta += len(got) * len(new) - sum(len(g) for g in got)
                applied.append({"from": old, "to": new, "count": len(got),
                                "matched": sorted(set(g for g in got if g != old))})

        # حارس استبدال: لا رقعة عمياء — الطول الجديد محسوبٌ سلفًا، وأي انحراف يوقف الدفعة
        if len(new_text) != len(old_text) + delta:
            raise SystemExit("SUBST_LEN_MISMATCH: %s — الطول المتوقع %d والفعلي %d."
                             % (oid, len(old_text) + delta, len(new_text)))
        for old, _, rx in SUBS_RX:
            if rx.search(new_text):
                raise SystemExit("SUBST_RESIDUE: %s — «%s» باقية بعد الاستبدال." % (oid, old))
        if new_text == old_text:
            raise SystemExit("SUBST_NOCHANGE: %s — لا تغيير رغم وجود ورود." % oid)

        meta = meta or {}
        meta, _added = _push_prev(meta, old_text, INSTRUMENT_LABEL)
        meta["amended_by"] = INSTRUMENT
        meta["amendment_date"] = GAZETTE_DATE
        meta["amendment_scope"] = (
            "استبدال لفظي بأمر الفقرة الثانية من المادة الأولى من المرسوم بقانون 91/2026 "
            "(«أينما وردتا») — لم يُمسّ من النص سوى العبارتين المسمّاتين، والنص السابق "
            "كاملًا في previous_versions.")
        meta["term_substitution"] = applied

        cur.execute("""UPDATE knowledge_objects
                       SET original_text=%s, normalized_text=%s, metadata=%s, updated_at=now()
                       WHERE id=%s""",
                    (new_text, normalize_text(new_text), Jsonb(meta), oid))
        changed.append(oid)
        print("  TERMSUB: %s — %s" % (
            oid, "، ".join("«%s»×%d" % (a["from"], a["count"]) for a in applied)))
    return changed


def fingerprint_outside(cur, exclude_ids):
    """بصمة نصوص كل ما هو خارج المجموعة المستهدفة — حارس «لم يُمسّ شيء آخر»."""
    if exclude_ids:
        cur.execute("""SELECT md5(string_agg(original_text, '|' ORDER BY id))
                       FROM knowledge_objects WHERE NOT (id = ANY(%s))""", (list(exclude_ids),))
    else:
        cur.execute("SELECT md5(string_agg(original_text, '|' ORDER BY id)) FROM knowledge_objects")
    return cur.fetchone()[0]


def _write_changed(ids):
    with open(CHANGED_IDS_FILE, "w", encoding="utf-8") as fh:
        fh.write("\n".join(ids) + ("\n" if ids else ""))


def main():
    dsn = os.environ["DATABASE_URL"]
    changed = []
    try:
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM knowledge_objects")
                total_before = cur.fetchone()[0]

                print("──── القياس ────")
                rows, hits = scan(cur)

                targets = [r[0] for r in rows
                           if classify(r[0], r[1], r[2]) == APPLY_CLASS
                           and any(rx.search(r[3] or "") for _, _, rx in SUBS_RX)]
                fp_before = fingerprint_outside(cur, targets)

                if not targets:
                    # يُفرَّغ الملف دائمًا: ملفٌ متخلف من تشغيل سابق يجعل الفهرسة
                    # التفاضلية تعمل على معرفات لا علاقة لها بهذه الجولة.
                    _write_changed([])
                    print("\nTERMSUB_NOOP: لا ورود حرفيًا في مواد المتن النافذة — "
                          "أمر الاستبدال مستوفًى فعلًا بتعديل تعريفَي م1 وبإلغاء "
                          "مواد الفصل القضائي. لم تُكتب أي تغييرات.")
                    print("\nTERMSUB_OK")
                    return

                print("\n──── الاستبدال (مواد المتن النافذة وحدها) ────")
                changed = apply_subs(cur, rows)

                fp_after = fingerprint_outside(cur, targets)
                if fp_after != fp_before:
                    raise SystemExit("SCOPE_BREACH: نصوص خارج المجموعة المستهدفة تغيّرت — "
                                     "تراجع فوري!")
                cur.execute("SELECT count(*) FROM knowledge_objects")
                if cur.fetchone()[0] != total_before:
                    raise SystemExit("COUNT_CHANGED: عدد كائنات القاعدة تغيّر — تراجع فوري!")
            conn.commit()
    except SystemExit:
        print("\nROLLED_BACK: بوابة فشلت — لم تُكتب أي تغييرات على القاعدة.")
        raise

    print("\n──── تحقق بعد الكتابة ────")
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        for oid in changed:
            cur.execute("""SELECT original_text, metadata FROM knowledge_objects
                           WHERE id=%s""", (oid,))
            t, m = cur.fetchone()
            for old, _, rx in SUBS_RX:
                assert not rx.search(t), "%s: «%s» باقية!" % (oid, old)
            assert len(m.get("previous_versions") or []) >= 1, "%s: النص السابق لم يُحفظ!" % oid
            print("  %s ✓ (previous_versions=%d)" % (oid, len(m["previous_versions"])))

        # المواد الملغاة لم تُمسّ — تحقق صريح لا افتراض
        cur.execute("""SELECT count(*) FROM knowledge_objects
                       WHERE id LIKE %s AND verification_status='superseded'""",
                    (LAW_PREFIX + "%",))
        print("  مواد 7/2010 الموسومة بالإلغاء (لم تُمسّ) = %d" % cur.fetchone()[0])

    _write_changed(changed)
    print("  معرفات ما تغيّر (%d) في: %s" % (len(changed), CHANGED_IDS_FILE))
    print("\nTERMSUB_OK")


if __name__ == "__main__":
    main()
