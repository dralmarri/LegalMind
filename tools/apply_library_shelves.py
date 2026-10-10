#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""رفوف مكتبة التشريعات — تسجيل رفّ كل قانون في الميتاداتا وحدها (2026-10-09).

بأمر المالك: مقابلة تصنيف التشريعات بالتصنيف المرجعي (مجموعة التشريعات الكويتية —
إعداد المستشار أول جزاء العتيبي، التعديلات حتى 2026/10/5) ووضع كل قانون في رفّه.

لماذا الميتاداتا لا حقل `branch`: مجلدات المتصفح اليوم هي `branch` نفسه، وهو حقلٌ
يقرؤه غير المتصفح أيضًا — وسم «فرع» في سياق الاستوديو، ومرشّح البحث، وتصفّح المبادئ
التي تشاركه مفرداته، وبوابة تغطية القضايا. والمرجع ترتيبٌ مكتبي (يضع البلدية والبيئة
تحت «الجزائية»، ومزاولة الطب تحت «القضاء والمحاماة»، وفيه ثلاثة رفوف لا مقابل لها
بين الفروع) — فحقل العرض المستقل يحقق المقابلة كاملة بلا أثر على شيء سواه.

يكتب لكل كائن تشريعي: library_shelf / library_shelf_order / library_shelf_basis /
library_shelf_source. ويمنح المرسوم بقانون 75/2026 (LEG-75 — كان خارج المتصفح كليًا)
مفتاح تجميع واسمًا، محتفظًا بالاسم القديم في prev_library_card_name.

الحُرّاس — كلها في معاملة واحدة، وأي فشل ⇒ ROLLED_BACK بلا أثر:
  • التغطية الكاملة: كل قانون يُظهره المتصفح له رفّ في الخريطة (UNSHELVED)، وكل مفتاح
    في الخريطة موجود حيًّا (SHELF_KEY_MISSING) — فلا يسقط قانون ولا يُكتب رفٌّ لشبح
  • لا مساس بنص ولا عنوان ولا تبويب: بصمة md5 لـ(العنوان، النص، النص المطبَّع، الفرع،
    الموضوع، الفرعي، الدقيق) لكل التشريعات قبل وبعد (TEXT_TOUCHED)
  • ميتاداتا غير كائنية تُوقف الدفعة بدل دمجٍ يُفسدها (NONOBJECT_METADATA)
  • نسخة احتياطية لميتاداتا كل صف سيُمسّ تُكتب قبل الكتابة، و--restore يعيدها حرفيًا
لا فهرسة: لا نص يتغير، والمتصفح يقرأ PostgreSQL وحده.

  admin/.venv/bin/python tools/apply_library_shelves.py --backup-dir DIR
  admin/.venv/bin/python tools/apply_library_shelves.py --restore DIR/metadata_before.jsonl
"""
import os, sys, json, argparse, collections

ROOT = os.environ.get("LM_ROOT", "/opt/LegalMind")
sys.path.insert(0, ROOT)
import kb_types as _kb          # noqa: E402
import psycopg                  # noqa: E402
from psycopg.types.json import Jsonb  # noqa: E402

TYPES = list(_kb.LEGISLATION_TYPES)
MAP_PATH = os.path.join(ROOT, "taxonomy", "library_shelves.json")

# مفتاح التجميع منسوخ حرفيًا من browse_kb في admin/app.py — الرفّ يُكتب لما يجمعه المتصفح
GEXPR = ("COALESCE(metadata->>'library_group', substring(id from '^(legis-[a-z0-9]+-[0-9]+)'), "
         "substring(id from '^(lreg-[0-9]+-[0-9]+-k[0-9]+)'), "
         "substring(id from '^(regl-[0-9]+-[0-9]+)'), "
         "substring(id from '^(reg-[0-9]+-[0-9]+)'))")
FPRINT = ("SELECT md5(string_agg(id || '␟' || coalesce(title,'') || '␟' || coalesce(original_text,'') "
          "|| '␟' || coalesce(normalized_text,'') || '␟' || coalesce(branch,'') || '␟' || "
          "coalesce(topic,'') || '␟' || coalesce(subtopic,'') || '␟' || coalesce(micro_issue,''), "
          "'|' ORDER BY id)) FROM knowledge_objects WHERE object_type = ANY(%s)")
SHELF_KEYS = ("library_shelf", "library_shelf_order", "library_shelf_basis", "library_shelf_source")


def load_map():
    d = json.load(open(MAP_PATH, encoding="utf-8"))
    orders = [s["order"] for s in d["shelves"]]
    if sorted(orders) != list(range(1, len(orders) + 1)):
        raise SystemExit("MAP_INVALID: ترتيب الرفوف ليس 1..N")
    seen, rows = set(), []
    for s in d["shelves"]:
        for key, basis in s["groups"]:
            if key in seen:
                raise SystemExit("MAP_INVALID: المفتاح %s مكرر في الخريطة" % key)
            if not (basis in ("ref", "subject") or basis.startswith("follows:")):
                raise SystemExit("MAP_INVALID: أساس غير معروف %s لـ %s" % (basis, key))
            seen.add(key)
            rows.append((key, s["name"], s["order"], basis))
    return d, rows


def live_groups(cur):
    cur.execute("SELECT g, count(*) FROM (SELECT " + GEXPR + " g FROM knowledge_objects "
                "WHERE object_type = ANY(%s)) s WHERE g IS NOT NULL GROUP BY g", (TYPES,))
    return dict(cur.fetchall())


def restore(path):
    recs = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn, conn.cursor() as cur:
        for r in recs:
            cur.execute("UPDATE knowledge_objects SET metadata = %s WHERE id = %s",
                        (Jsonb(r["metadata"]) if r["metadata"] is not None else None, r["id"]))
        conn.commit()
    print("RESTORED: %d صفًّا أُعيدت ميتاداتاها كما كانت حرفيًا" % len(recs))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backup-dir")
    ap.add_argument("--restore")
    a = ap.parse_args()
    if a.restore:
        return restore(a.restore)
    if not a.backup_dir or not os.path.isdir(a.backup_dir):
        raise SystemExit("BACKUP_DIR_MISSING: مرّر --backup-dir لمجلد موجود")
    d, rows = load_map()
    src = d["source"]
    conn = psycopg.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM knowledge_objects WHERE object_type = ANY(%s) AND "
                        "metadata IS NOT NULL AND jsonb_typeof(metadata) <> 'object'", (TYPES,))
            bad = cur.fetchone()[0]
            if bad:
                raise SystemExit("NONOBJECT_METADATA: %d كائنًا تشريعيًا ميتاداتاه ليست كائنًا" % bad)

            cur.execute("SELECT count(*) FROM knowledge_objects")
            total_before = cur.fetchone()[0]
            cur.execute(FPRINT, (TYPES,))
            fp_before = cur.fetchone()[0]

            # نسخة احتياطية لكل صف تشريعي قبل أي كتابة — فالاسترداد حرفي لا تقريبي
            cur.execute("SELECT id, metadata FROM knowledge_objects WHERE object_type = ANY(%s) "
                        "ORDER BY id", (TYPES,))
            snap = cur.fetchall()
            bpath = os.path.join(a.backup_dir, "metadata_before.jsonl")
            with open(bpath, "w", encoding="utf-8") as f:
                for i, m in snap:
                    f.write(json.dumps({"id": i, "metadata": m}, ensure_ascii=False) + "\n")
            if os.path.getsize(bpath) == 0:
                raise SystemExit("BACKUP_EMPTY: النسخة الاحتياطية فارغة — توقف")
            print("BACKUP_OK: %d صفًّا ← %s" % (len(snap), bpath))

            # المجلد الذي كان كل قانون يظهر فيه — للتقرير وحده
            cur.execute("SELECT g, string_agg(DISTINCT CASE WHEN branch LIKE 'أحوال شخصية%%' "
                        "THEN 'أحوال شخصية' ELSE coalesce(nullif(branch,''),'غير مصنّف') END, '/') "
                        "FROM (SELECT " + GEXPR + " g, branch FROM knowledge_objects "
                        "WHERE object_type = ANY(%s)) s WHERE g IS NOT NULL GROUP BY g", (TYPES,))
            was = dict(cur.fetchall())

            # (أ) مجموعات جديدة لكائنات كانت خارج المتصفح
            for gkey, spec in d.get("new_groups", {}).items():
                cur.execute("SELECT id, " + GEXPR + " FROM knowledge_objects WHERE "
                            "object_type = ANY(%s) AND id LIKE %s", (TYPES, spec["id_like"]))
                got = cur.fetchall()
                if len(got) != spec["expect_rows"]:
                    raise SystemExit("NEWGROUP_COUNT: %s وُجد %d والمتوقع %d"
                                     % (gkey, len(got), spec["expect_rows"]))
                foreign = [i for i, g in got if g not in (None, gkey)]
                if foreign:
                    raise SystemExit("NEWGROUP_CLASH: %s تنتمي سلفًا لمجموعة أخرى %s" % (gkey, foreign[:3]))
                cur.execute(
                    "UPDATE knowledge_objects SET metadata = coalesce(metadata,'{}'::jsonb) "
                    "|| CASE WHEN metadata ? 'library_card_name' AND NOT metadata ? 'prev_library_card_name' "
                    "        AND metadata->>'library_card_name' IS DISTINCT FROM %s::text "
                    "        THEN jsonb_build_object('prev_library_card_name', metadata->'library_card_name') "
                    "        ELSE '{}'::jsonb END "
                    "|| jsonb_build_object('library_group', %s::text, 'library_card_name', %s::text) "
                    "WHERE object_type = ANY(%s) AND id LIKE %s",
                    (spec["card_name"], gkey, spec["card_name"], TYPES, spec["id_like"]))
                print("NEWGROUP_OK: %s ← %d كائنًا صار ظاهرًا في المتصفح" % (gkey, cur.rowcount))

            # (ب) التغطية الكاملة في الاتجاهين
            live = live_groups(cur)
            mapped = {k for k, _, _, _ in rows}
            unshelved = sorted(set(live) - mapped)
            ghosts = sorted(mapped - set(live))
            if unshelved:
                raise SystemExit("UNSHELVED: قوانين ظاهرة بلا رفّ في الخريطة: %s" % unshelved)
            if ghosts:
                raise SystemExit("SHELF_KEY_MISSING: مفاتيح في الخريطة لا وجود لها حيًّا: %s" % ghosts)

            # (ج) الكتابة
            n_rows = 0
            for key, name, order, basis in rows:
                cur.execute("UPDATE knowledge_objects SET metadata = coalesce(metadata,'{}'::jsonb) || "
                            "jsonb_build_object('library_shelf', %s::text, 'library_shelf_order', %s::int, "
                            "'library_shelf_basis', %s::text, 'library_shelf_source', %s::text) "
                            "WHERE object_type = ANY(%s) AND " + GEXPR + " = %s",
                            (name, order, basis, src, TYPES, key))
                if cur.rowcount != live[key]:
                    raise SystemExit("ROWCOUNT_MISMATCH: %s كُتب %d والمتوقع %d" % (key, cur.rowcount, live[key]))
                n_rows += cur.rowcount

            # (د) التحقق
            cur.execute(FPRINT, (TYPES,))
            if cur.fetchone()[0] != fp_before:
                raise SystemExit("TEXT_TOUCHED: تغيّر نصٌّ أو عنوانٌ أو تبويب — تراجع فوري!")
            cur.execute("SELECT count(*) FROM knowledge_objects")
            if cur.fetchone()[0] != total_before:
                raise SystemExit("COUNT_CHANGED: تغيّر عدد كائنات القاعدة")
            cur.execute("SELECT count(*) FROM knowledge_objects WHERE object_type = ANY(%s) AND "
                        + GEXPR + " IS NOT NULL AND NOT (metadata ? 'library_shelf')", (TYPES,))
            left = cur.fetchone()[0]
            if left:
                raise SystemExit("SHELF_GAP: %d كائنًا ظاهرًا بقي بلا رفّ" % left)

            # (هـ) التقرير — كل رفّ بقوانينه، ومن أين جاء كلٌّ منها
            BASIS = {"ref": "المرجع", "subject": "اقتراح بالموضوع"}
            print("")
            for s in d["shelves"]:
                print("■ %d. %s" % (s["order"], s["name"]))
                for key, basis in s["groups"]:
                    b = BASIS.get(basis) or ("يتبع " + basis.split(":", 1)[1])
                    print("    %-22s %5d | كان في: %-12s | %s" % (key, live[key], was.get(key, "خارج المتصفح"), b))
            print("")
            print("SHELVES_SUMMARY: %d رفوف | %d قانونًا | %d كائنًا تشريعيًا"
                  % (len(d["shelves"]), len(rows), n_rows))
        conn.commit()
        print("SHELVES_APPLIED")
    except BaseException as e:
        conn.rollback()
        print("ROLLED_BACK: %s" % e)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
