#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تحقّقٌ من استشهادات جواب «بيع الحصّة العقارية بتوقيعٍ إلكترونيّ» — قراءةٌ فقط.
كلُّ مادةٍ استشهد بها النموذجُ تُطبَع بنصّها ليُقابَل بما نُسب إليها؛ والمفقودُ يُعلَن مفقودًا.
ويُبحَث في المرافعات 38/1980 عن نصّ الاختصاص العقاريّ لأنّ النموذج بلغه قياسًا — والاختصاصُ لا يُقاس."""
import os, re, sys

CITED = [
    ("legis-5-1959-m%s", ["7", "12", "17", "29", "30"], "التسجيل العقاري 5/1959"),
    ("legis-20-2014-m%s", ["2", "3", "18", "19", "20"], "المعاملات الإلكترونية 20/2014"),
    ("legis-39-1980-m%s", ["13", "14", "16"], "الإثبات 39/1980"),
    ("legis-67-1980-m%s", ["189", "196", "209", "211", "213", "219", "280", "284", "289",
                           "463", "466", "471", "500", "815", "816", "817", "819", "829", "833"],
     "المدني 67/1980"),
]
CUT = 300


def main():
    import psycopg
    dsn = os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
    with psycopg.connect(dsn) as cx, cx.cursor() as cur:
        missing, total = [], 0
        for pat, nums, lbl in CITED:
            print("\n" + "=" * 72)
            print("== %s ==" % lbl)
            print("=" * 72)
            for n in nums:
                oid = pat % n
                total += 1
                cur.execute("SELECT original_text FROM knowledge_objects WHERE id=%s", (oid,))
                r = cur.fetchone()
                if not r or not (r[0] or "").strip():
                    missing.append(oid)
                    print("\n### %s — ✗ غيرُ موجود في القاعدة" % oid)
                    continue
                t = re.sub(r"\s+", " ", r[0]).strip()
                print("\n### %s (%d حرفًا)\n%s%s" % (oid, len(r[0]), t[:CUT], "…" if len(t) > CUT else ""))

        print("\n" + "=" * 72)
        print("== نصُّ الاختصاص: بحثٌ في المرافعات 38/1980 عن الدعاوى العقارية ==")
        print("=" * 72)
        cur.execute("SELECT id,original_text FROM knowledge_objects WHERE id LIKE 'legis-38-1980-%' "
                    "AND (original_text LIKE '%%العقار%%' OR original_text LIKE '%%عقاري%%')")
        rows = cur.fetchall()
        rows.sort(key=lambda r: int(re.search(r"m(\d+)", r[0]).group(1)) if re.search(r"m(\d+)", r[0]) else 10**6)
        print("عددُ موادّ المرافعات التي تذكر العقار: %d" % len(rows))
        for oid, t in rows[:14]:
            print("\n### %s\n%s" % (oid, re.sub(r"\s+", " ", t).strip()[:260]))

        print("\n" + "=" * 72)
        print("== قسمةُ المال الشائع في المدنيّ: أينَ موضعُها فعلًا؟ ==")
        print("=" * 72)
        cur.execute("SELECT id,left(original_text,140) FROM knowledge_objects "
                    "WHERE id LIKE 'legis-67-1980-%' AND original_text LIKE '%%القسمة%%'")
        rows = cur.fetchall()
        rows.sort(key=lambda r: int(re.search(r"m(\d+)", r[0]).group(1)) if re.search(r"m(\d+)", r[0]) else 10**6)
        print("عددُ الموادّ: %d ⇐ %s" % (len(rows), ", ".join(r[0].replace("legis-67-1980-", "") for r in rows[:30])))
        for oid, t in rows[:8]:
            print("  %s :: %s" % (oid.replace("legis-67-1980-", ""), re.sub(r"\s+", " ", t).strip()[:110]))

    print("\n" + "=" * 72)
    print("الخلاصة: فُحص %d استشهادًا | المفقود: %s" % (total, ", ".join(missing) or "لا شيء"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
