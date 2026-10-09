#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مسبار رفوف مكتبة التشريعات — قراءة خالصة (SELECT حصرًا)، لا يكتب في القاعدة شيئًا.

الغرض: قبل مقابلة تصنيف التشريعات بالتصنيف المرجعي (مجموعة التشريعات الكويتية —
إعداد المستشار أول جزاء العتيبي، التعديلات حتى 2026/10/5)، يُرى ما يراه المتصفح فعلًا:
• كل «فرع» يجمع التشريعات اليوم وعدد كائناته
• كل قانون/لائحة كما يجمعه المتصفح (`/api/browse?kind=laws` — مفتاح التجميع نفسه حرفيًا)
  بعدده وأنواع كائناته وتوزيع فروعه واسمه — فالقانون المتشظّي بين فرعين اكتشافٌ بذاته
• الكائنات التي **لا يُظهرها المتصفح أصلًا** (مفتاح تجميعها فارغ — كمعرّفات LEG-*)
  مجمّعةً ببادئة معرّفها، مع مفاتيح الميتاداتا وقيمها حين تكون قليلة التنوّع —
  لأنها الدليل الوحيد على هوية القانون حين لا يحمل المعرّف سنته

المسبار **شامل لا مقتطع** (درس §6: حدّ الاقتطاع يصير صانع «الحقيقة»).
التشغيل (بيئة الأدمن، من /opt/LegalMind):
  set -a; . deploy/.env; set +a
  admin/.venv/bin/python tools/probe_library_shelves.py
"""
import os, sys, json, collections

ROOT = os.environ.get("LM_ROOT", "/opt/LegalMind")
sys.path.insert(0, ROOT)
import kb_types as _kb          # noqa: E402 — المصدر المركزي الواحد لأنواع التشريعات
import psycopg                  # noqa: E402

TYPES = list(_kb.LEGISLATION_TYPES)

# مفتاح التجميع منسوخ حرفيًا من browse_kb في admin/app.py — فالمسبار يرى ما يراه المتصفح
GEXPR = ("COALESCE(metadata->>'library_group', substring(id from '^(legis-[a-z0-9]+-[0-9]+)'), "
         "substring(id from '^(lreg-[0-9]+-[0-9]+-k[0-9]+)'), "
         "substring(id from '^(regl-[0-9]+-[0-9]+)'), "
         "substring(id from '^(reg-[0-9]+-[0-9]+)'))")
NAME = ("COALESCE(min(metadata->>'library_card_name'), CASE WHEN min(g) LIKE 'lreg-%%' "
        "THEN split_part(min(title), ' — ', 2) || COALESCE(' — كتاب ' || min(metadata->>'book_title'), '') "
        "ELSE btrim(substring(min(title) from '[^—]*$')) END)")


def main():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise SystemExit("PROBE_FAIL: DATABASE_URL غير مضبوط — حمّل deploy/.env أولًا")
    out = []
    p = out.append
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        conn.read_only = True
        cur.execute("SELECT count(*) FROM knowledge_objects WHERE object_type = ANY(%s)", (TYPES,))
        total = cur.fetchone()[0]
        p("=== (1) فروع التشريعات اليوم — مجموع الكائنات التشريعية: %d" % total)
        cur.execute("SELECT COALESCE(NULLIF(branch,''),'∅') b, count(*) FROM knowledge_objects "
                    "WHERE object_type = ANY(%s) GROUP BY b ORDER BY count(*) DESC", (TYPES,))
        for b, n in cur.fetchall():
            p("  %-28s %6d" % (b, n))

        cur.execute("SELECT g, COALESCE(NULLIF(branch,''),'∅'), object_type, count(*) FROM "
                    "(SELECT " + GEXPR + " g, branch, object_type FROM knowledge_objects "
                    " WHERE object_type = ANY(%s)) s GROUP BY 1,2,3", (TYPES,))
        br = collections.defaultdict(collections.Counter)
        ty = collections.defaultdict(set)
        for g, b, t, n in cur.fetchall():
            br[g][b] += n
            ty[g].add(t)
        cur.execute("SELECT g, " + NAME + ", min(id), "
                    "string_agg(DISTINCT metadata->>'library_shelf', '/') FROM "
                    "(SELECT " + GEXPR + " g, * FROM knowledge_objects WHERE object_type = ANY(%s)) s "
                    "WHERE g IS NOT NULL GROUP BY g", (TYPES,))
        meta = {g: (nm, mid, sh) for g, nm, mid, sh in cur.fetchall()}

        shown = sorted(k for k in br if k is not None)
        p("")
        p("=== (2) القوانين كما يجمعها المتصفح — %d مجموعة (المفتاح | العدد | الفروع | الأنواع | الاسم)"
          % len(shown))
        split = []
        for g in shown:
            nm, mid, sh = meta.get(g, ("", "", None))
            bd = br[g]
            if len(bd) > 1:
                split.append(g)
            p("  %s | %d | %s | %s | %s%s" % (
                g, sum(bd.values()),
                "، ".join("%s:%d" % kv for kv in bd.most_common()),
                ",".join(sorted(t.replace("legislation", "L") for t in ty[g])),
                (nm or "").strip()[:90],
                (" | رف قائم: " + sh) if sh else ""))
        p("")
        p("  ← قوانين متشظّية بين أكثر من فرع: %d %s" % (len(split), split))

        p("")
        p("=== (3) كائنات تشريعية لا يُظهرها المتصفح (مفتاح التجميع فارغ)")
        cur.execute("SELECT count(*) FROM knowledge_objects WHERE object_type = ANY(%s) AND "
                    + GEXPR + " IS NULL", (TYPES,))
        hidden = cur.fetchone()[0]
        p("  المجموع: %d" % hidden)
        if hidden:
            PFX = "substring(id from '^([A-Za-z]+-[^-]+)')"
            cur.execute("SELECT " + PFX + " pf, count(*), "
                        "string_agg(DISTINCT COALESCE(NULLIF(branch,''),'∅'), '،'), "
                        "string_agg(DISTINCT object_type, ','), min(title), max(title) "
                        "FROM knowledge_objects WHERE object_type = ANY(%s) AND " + GEXPR +
                        " IS NULL GROUP BY pf ORDER BY count(*) DESC", (TYPES,))
            for pf, n, bs, ts, t1, t2 in cur.fetchall():
                p("  %s | %d | %s | %s" % (pf, n, bs, ts))
                p("      أول عنوان: %s" % (t1 or "")[:110])
                if t2 != t1:
                    p("      آخر عنوان: %s" % (t2 or "")[:110])
            cur.execute("SELECT k, count(*), count(DISTINCT metadata->>k) FROM knowledge_objects, "
                        "jsonb_object_keys(metadata) k WHERE object_type = ANY(%s) "
                        "AND jsonb_typeof(metadata) = 'object' AND " + GEXPR +
                        " IS NULL GROUP BY k ORDER BY count(*) DESC", (TYPES,))
            keys = cur.fetchall()
            p("")
            p("  مفاتيح الميتاداتا (المفتاح | الكائنات | القيم المتمايزة):")
            for k, n, d in keys:
                p("    %s | %d | %d" % (k, n, d))
            for k, n, d in keys:
                if 1 <= d <= 40:
                    cur.execute("SELECT metadata->>%s v, count(*) FROM knowledge_objects WHERE "
                                "object_type = ANY(%s) AND " + GEXPR + " IS NULL AND metadata ? %s "
                                "GROUP BY v ORDER BY count(*) DESC", (k, TYPES, k))
                    p("  القيم المتمايزة لـ «%s»:" % k)
                    for v, c in cur.fetchall():
                        p("    %5d  %s" % (c, (v or "")[:110]))

    text = "\n".join(out)
    print(text)
    dest = "/opt/legalmind-data"
    if os.path.isdir(dest):
        import time
        fn = os.path.join(dest, "probe_shelves_%d.txt" % int(time.time()))
        with open(fn, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print("\nحُفظ المخرج في: " + fn)
    print("PROBE_SHELVES_DONE")


if __name__ == "__main__":
    main()
