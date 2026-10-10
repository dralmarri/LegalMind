#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ضمّ 91/2026 وتعليمات كفاية رأس المال القديمة إلى مجموعة قانون أسواق المال + بطاقة 78/2026 (2026-10-09).

بأمر المالك (لقطة رفّ التجارية):
  «تعليمات كفاية رأس المال يضاف للائحة التنفيذية لقانون أسواق المال، ومرسوم رقم 91 يجب أن يفهرس
   بحيث يدخل تلك التعديلات على قانون أسواق المال» + «يجب أن تشير لذلك في البطاقة أنه مؤجَّل».

ما كشفه التقرير الحي قبل البناء (fix_deferred_91_2026.py --report):
  • مجموعة cma-authority-unified فيها **سلفًا** «الكتاب السابع عشر — تعليمات كفاية رأس المال»
    (448 كائنًا، TBL-BATCH-…) — وهو النص الحالي. وبطاقة cap-adequacy-legacy (307، LEG-UNKNOWN-…)
    موسومة «نسخة قديمة (قيد المراجعة)»، ومقابلة عيّنة (م60-4) أثبتت أنها **نسخة سابقة** من الكتاب
    نفسه بفروق صياغة، وكائناتها «غير قابلة للاستشهاد».
  • فالضمّ لا يُذيب القديمة في الكتاب الحالي (ازدواج مضلِّل) ولا يحذفها (ممنوع): تدخل اللائحة
    **جزءًا مستقلًا ملاصقًا للكتاب السابع عشر، موسومًا «نسخة سابقة»** — فيتحقق أمر المالك بلا خلط.
  • 91/2026 (6 كائنات) يدخل المجموعة جزءًا مستقلًا يحمل وسم النفاذ المؤجَّل ⟨يُعمل به من 2027/10/1⟩
    — وتعديلاته على 7/2010 مسجَّلة على موادها سلفًا (FIX91: المتن النافذ + الكتلة المعلَّقة).
  • 78/2026 (مكافحة التستر التجاري): مادته الأخيرة «يعمل به بعد ستة أشهر من تاريخ نشره»،
    وتاريخ نشره **غير مسجَّل في القاعدة** — فتحمل بطاقته القاعدة كما نُصّت بلا ادعاء نفاذٍ أو عدمه
    (نموذج 10/2026 في FIX91)، والعقد كاملًا في metadata.commencement.

لا يُمسّ نصٌّ ولا عنوانٌ ولا تبويب (branch/topic/…) — ميتاداتا العرض وحدها، فلا فهرسة.

الحُرّاس — معاملة واحدة، وأي فشل ⇒ ROLLED_BACK بلا أثر:
  • العدد المتوقع لكل مصدر (LEGACY_COUNT / P91_COUNT) والكتاب السابع عشر يُعثر عليه مرة واحدة
  • اسم بطاقة مجموعة أسواق المال المعروض قبل وبعد متطابق حرفيًا (NAME_CHANGED)
  • بصمة md5 للعناوين والنصوص والتبويب والحالة لكل التشريعات قبل وبعد (TEXT_TOUCHED)
  • بصمة ميتاداتا كل ما خارج الصفوف المستهدفة قبل وبعد (SCOPE_BREACH) وعدّ القاعدة (COUNT_CHANGED)
  • مصدر قاعدة نفاذ 78/2026 يُقرأ من نص مادته الأخيرة (EFFECT_SOURCE_CHANGED)
  • نسخة احتياطية لميتاداتا كل صف سيُمسّ يستردها --restore حرفيًا؛ وإعادة التشغيل بلا أثر

  .venv/bin/python tools/merge_cma_group.py --backup-dir DIR
  .venv/bin/python tools/merge_cma_group.py --restore DIR/metadata_before.jsonl
"""
import os, sys, re, json, argparse, collections

ROOT = os.environ.get("LM_ROOT", "/opt/LegalMind")
sys.path.insert(0, ROOT)
import kb_types as _kb                                      # noqa: E402
import psycopg                                              # noqa: E402
from psycopg.types.json import Jsonb                        # noqa: E402

TYPES = list(_kb.LEGISLATION_TYPES)
TODAY = "2026-10-09"
CMA = "cma-authority-unified"
LEGACY = "cap-adequacy-legacy"
LEGACY_COUNT = 307
P91 = "legis-91-2026"
P91_COUNT = 6
P91_PART = ("المرسوم بقانون 91/2026 بتعديل بعض أحكام القانون — تعديلاته مسجَّلة على المواد "
            "⟨يُعمل به من 2027/10/1⟩")
LEGACY_TAG = "نسخة سابقة (قيد المراجعة)"
LEGACY_TAG_NC = "نسخة سابقة (قيد المراجعة — غير قابلة للاستشهاد)"
BOOK17 = ("السابع عشر", "كفاية")

P78 = "legis-78-2026"
P78_LAST = "legis-78-2026-m14"
P78_NEEDLE = "يعمل به بعد ستة أشهر من تاريخ نشره"
P78_CARD = "قانون مكافحة التستر التجاري ⟨يُعمل به بعد ستة أشهر من نشره⟩"
P78_COMMENCEMENT = {
    "effective_rule": "يعمل به بعد ستة أشهر من تاريخ نشره في الجريدة الرسمية",
    "effective_rule_source": P78_LAST,
    "effective_from": None,
    "effective_from_basis": "تاريخ النشر في الجريدة الرسمية غير مسجَّل في القاعدة — يُحسب حين يُعرف",
    "in_force_today": None,
    "recorded_at": TODAY,
}

GEXPR = ("COALESCE(metadata->>'library_group', substring(id from '^(legis-[a-z0-9]+-[0-9]+)'), "
         "substring(id from '^(lreg-[0-9]+-[0-9]+-k[0-9]+)'), "
         "substring(id from '^(regl-[0-9]+-[0-9]+)'), "
         "substring(id from '^(reg-[0-9]+-[0-9]+)'))")
# الاسم المعروض في المتصفح حرفيًا (browse_kb — المستوى الثاني)
NAME_SQL = ("SELECT COALESCE(min(metadata->>'library_card_name'), CASE WHEN " + GEXPR + " LIKE 'lreg-%%' "
            "THEN split_part(min(title), ' — ', 2) || COALESCE(' — كتاب ' || min(metadata->>'book_title'), '') "
            "ELSE btrim(substring(min(title) from '[^—]*$')) END) FROM knowledge_objects "
            "WHERE object_type = ANY(%s) AND " + GEXPR + " = %s GROUP BY " + GEXPR)
FP_TEXT = ("SELECT md5(string_agg(id || '␟' || coalesce(title,'') || '␟' || coalesce(original_text,'') || '␟' || "
           "coalesce(normalized_text,'') || '␟' || coalesce(branch,'') || '␟' || coalesce(topic,'') || '␟' || "
           "coalesce(subtopic,'') || '␟' || coalesce(micro_issue,'') || '␟' || coalesce(verification_status,'') "
           "|| '␟' || coalesce(usable_as_citation::text,''), '|' ORDER BY id)) FROM knowledge_objects "
           "WHERE object_type = ANY(%s)")
FP_META_OUT = ("SELECT md5(string_agg(id || '␟' || coalesce(metadata::text,''), '|' ORDER BY id)) "
               "FROM knowledge_objects WHERE NOT (id = ANY(%s))")
SHELF_KEYS = ("library_shelf", "library_shelf_order", "library_shelf_basis", "library_shelf_source")
PREV_KEYS = ("library_group", "doc_part", "doc_subpart", "library_card_name") + SHELF_KEYS


def _one(cur, sql, args):
    cur.execute(sql, args)
    r = cur.fetchone()
    return r[0] if r else None


def target_ids(cur):
    """الصفوف المستهدفة — تُعرف قبل الضمّ وبعده (إعادة التشغيل بلا أثر)."""
    cur.execute("SELECT id FROM knowledge_objects WHERE object_type = ANY(%s) AND ("
                "metadata->>'library_group' = %s OR metadata->'merged_from'->>'library_group' = %s)",
                (TYPES, LEGACY, LEGACY))
    legacy = sorted(r[0] for r in cur.fetchall())
    cur.execute("SELECT id FROM knowledge_objects WHERE object_type = ANY(%s) AND id LIKE %s",
                (TYPES, P91 + "-%"))
    p91 = sorted(r[0] for r in cur.fetchall())
    cur.execute("SELECT id FROM knowledge_objects WHERE object_type = ANY(%s) AND " + GEXPR + " = %s",
                (TYPES, P78))
    p78 = sorted(r[0] for r in cur.fetchall())
    return legacy, p91, p78


def apply(a):
    conn = psycopg.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM knowledge_objects WHERE object_type = ANY(%s) AND "
                        "metadata IS NOT NULL AND jsonb_typeof(metadata) <> 'object'", (TYPES,))
            if cur.fetchone()[0]:
                raise SystemExit("NONOBJECT_METADATA")
            legacy, p91, p78 = target_ids(cur)
            if len(legacy) != LEGACY_COUNT:
                raise SystemExit("LEGACY_COUNT: %d لا %d" % (len(legacy), LEGACY_COUNT))
            if len(p91) != P91_COUNT:
                raise SystemExit("P91_COUNT: %d لا %d" % (len(p91), P91_COUNT))
            if not p78:
                raise SystemExit("P78_MISSING")
            last = _one(cur, "SELECT original_text FROM knowledge_objects WHERE id=%s", (P78_LAST,))
            if not last or P78_NEEDLE not in re.sub(r"\s+", " ", last):
                raise SystemExit("EFFECT_SOURCE_CHANGED: %s لا يحمل «%s»" % (P78_LAST, P78_NEEDLE))
            ids = legacy + p91 + p78

            # حالة ما قبل
            fp_text = _one(cur, FP_TEXT, (TYPES,))
            fp_out = _one(cur, FP_META_OUT, (ids,))
            n_before = _one(cur, "SELECT count(*) FROM knowledge_objects", ())
            cma_name = _one(cur, NAME_SQL, (TYPES, CMA))
            if not cma_name:
                raise SystemExit("CMA_MISSING")
            print("CMA_NAME: %s" % cma_name)

            cur.execute("SELECT id, metadata FROM knowledge_objects WHERE id = ANY(%s) ORDER BY id", (ids,))
            rows = cur.fetchall()
            bpath = os.path.join(a.backup_dir, "metadata_before.jsonl")
            with open(bpath, "w", encoding="utf-8") as f:
                for i, m in rows:
                    f.write(json.dumps({"id": i, "metadata": m}, ensure_ascii=False) + "\n")
            if os.path.getsize(bpath) == 0:
                raise SystemExit("BACKUP_EMPTY")
            print("BACKUP_OK: %d صفًّا ← %s" % (len(rows), bpath))
            meta = {i: dict(m or {}) for i, m in rows}

            # رفّ مجموعة أسواق المال (الغالب) — يُنسخ للصفوف المنضمّة
            cur.execute("SELECT " + ", ".join("metadata->>'%s'" % k for k in SHELF_KEYS) + ", count(*) "
                        "FROM knowledge_objects WHERE object_type = ANY(%s) AND " + GEXPR + " = %s "
                        "AND NOT (id = ANY(%s)) GROUP BY 1,2,3,4 ORDER BY count(*) DESC",
                        (TYPES, CMA, ids))
            sh = cur.fetchone()
            if not sh or not sh[0]:
                raise SystemExit("CMA_SHELF_MISSING")
            shelf = dict(zip(SHELF_KEYS, sh[:4]))

            # الكتاب السابع عشر الحالي — يُعثر عليه في الجزء أو الفرعي، مرة واحدة بالضبط
            cur.execute("SELECT metadata->>'doc_part', metadata->>'doc_subpart', count(*) FROM knowledge_objects "
                        "WHERE object_type = ANY(%s) AND " + GEXPR + " = %s AND NOT (id = ANY(%s)) AND "
                        "((coalesce(metadata->>'doc_part','') LIKE %s AND coalesce(metadata->>'doc_part','') LIKE %s) OR "
                        " (coalesce(metadata->>'doc_subpart','') LIKE %s AND coalesce(metadata->>'doc_subpart','') LIKE %s)) "
                        "GROUP BY 1,2",
                        (TYPES, CMA, ids, "%" + BOOK17[0] + "%", "%" + BOOK17[1] + "%",
                         "%" + BOOK17[0] + "%", "%" + BOOK17[1] + "%"))
            b17 = cur.fetchall()
            levels = {("part" if (p and BOOK17[0] in p) else "sub") for p, s, n in b17}
            if not b17 or len(levels) != 1 or len({(p if "part" in levels else (p, s)) for p, s, n in b17}) != 1:
                raise SystemExit("BOOK17_NOT_UNIQUE: %s" % b17)
            b17_part, b17_sub = b17[0][0], b17[0][1]
            print("BOOK17: %s | %s | %d" % (b17_part, b17_sub or "—", sum(r[2] for r in b17)))
            n_cit = _one(cur, "SELECT count(*) FROM knowledge_objects WHERE id = ANY(%s) AND usable_as_citation",
                         (legacy,))
            tag = LEGACY_TAG_NC if n_cit == 0 else LEGACY_TAG
            print("LEGACY_CITABLE: %d من %d" % (n_cit, len(legacy)))

            def move(oid, part, sub, card):
                m = meta[oid]
                if "merged_from" not in m:
                    m["merged_from"] = {k: m.get(k) for k in PREV_KEYS}
                    m["merged_from"]["merged_at"] = TODAY
                m["library_group"] = CMA
                m["doc_part"] = part
                if sub is None:
                    m.pop("doc_subpart", None)
                else:
                    m["doc_subpart"] = sub
                m["library_card_name"] = card
                for k, v in shelf.items():
                    if v is None:
                        m.pop(k, None)
                    else:
                        m[k] = int(v) if k == "library_shelf_order" else v

            # 1) تعليمات كفاية رأس المال القديمة ← جزء ملاصق للكتاب السابع عشر
            if "part" in levels:
                lp, ls = b17_part + " — " + tag, None
            else:
                lp, ls = b17_part, b17_sub + " — " + tag
            for oid in legacy:
                move(oid, lp, ls, cma_name)
            print("LEGACY_MERGED: %d ← %s%s" % (len(legacy), lp, (" | " + ls) if ls else ""))

            # 2) 91/2026 ← جزء مستقل بوسم النفاذ المؤجَّل
            for oid in p91:
                move(oid, P91_PART, None, cma_name)
            print("P91_MERGED: %d ← %s" % (len(p91), P91_PART))

            # 3) 78/2026 — البطاقة تحمل قاعدة النفاذ، والعقد في الميتاداتا
            for oid in p78:
                m = meta[oid]
                if m.get("library_card_name") != P78_CARD and "prev_library_card_name" not in m:
                    m["prev_library_card_name"] = m.get("library_card_name")
                m["library_card_name"] = P78_CARD
                m["commencement"] = P78_COMMENCEMENT
            print("P78_CARD: %d كائنًا ← %s" % (len(p78), P78_CARD))

            n_upd = 0
            for i, old in rows:
                if meta[i] != (old or {}):
                    cur.execute("UPDATE knowledge_objects SET metadata=%s WHERE id=%s", (Jsonb(meta[i]), i))
                    n_upd += 1
            print("ROWS_UPDATED: %d (0 = مطبَّق سلفًا)" % n_upd)

            # التحقق
            if _one(cur, FP_TEXT, (TYPES,)) != fp_text:
                raise SystemExit("TEXT_TOUCHED: تغيّر نصٌّ أو عنوانٌ أو تبويب — تراجع فوري!")
            if _one(cur, FP_META_OUT, (ids,)) != fp_out:
                raise SystemExit("SCOPE_BREACH: تغيّرت ميتاداتا صفٍّ خارج النطاق")
            if _one(cur, "SELECT count(*) FROM knowledge_objects", ()) != n_before:
                raise SystemExit("COUNT_CHANGED")
            after = _one(cur, NAME_SQL, (TYPES, CMA))
            if after != cma_name:
                raise SystemExit("NAME_CHANGED: «%s» ← «%s»" % (cma_name, after))
            for gone in (LEGACY, P91):
                if _one(cur, "SELECT count(*) FROM knowledge_objects WHERE object_type = ANY(%s) AND "
                             + GEXPR + " = %s", (TYPES, gone)):
                    raise SystemExit("GROUP_REMAINS: %s" % gone)
            cur.execute("SELECT COALESCE(NULLIF(metadata->>'doc_part',''),'النص الأصلي'), "
                        "NULLIF(metadata->>'doc_subpart',''), count(*), min(id) FROM knowledge_objects "
                        "WHERE object_type = ANY(%s) AND " + GEXPR + " = %s GROUP BY 1,2 ORDER BY min(id)",
                        (TYPES, CMA))
            print("== أجزاء مجموعة أسواق المال بعد الضمّ (بترتيب المتصفح):")
            for p, s, n, i in cur.fetchall():
                print("  %-70s %-30s %5d  %s" % (p[:70], (s or "")[:30], n, i))
        conn.commit()
        print("MERGE_CMA_APPLIED")
    except BaseException as e:
        conn.rollback()
        print("ROLLED_BACK: %s" % e)
        raise
    finally:
        conn.close()


def restore(path):
    recs = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn, conn.cursor() as cur:
        for r in recs:
            cur.execute("UPDATE knowledge_objects SET metadata=%s WHERE id=%s",
                        (Jsonb(r["metadata"]) if r["metadata"] is not None else None, r["id"]))
        conn.commit()
    print("RESTORED: %d صفًّا أُعيدت ميتاداتاها حرفيًا" % len(recs))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backup-dir")
    ap.add_argument("--restore")
    a = ap.parse_args()
    if a.restore:
        return restore(a.restore)
    if not a.backup_dir or not os.path.isdir(a.backup_dir):
        raise SystemExit("BACKUP_DIR_MISSING")
    apply(a)


if __name__ == "__main__":
    main()
