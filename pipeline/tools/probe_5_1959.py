#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""معاينةُ قانون التسجيل العقاري 5/1959 — قراءةٌ فقط، لا تكتب شيئًا.
(1) فهرسٌ كاملٌ لكلّ الكائنات، (2) النصُّ الكاملُ للموادّ التي تحكم أثرَ التسجيل ونقلَ الملكية
والتصديقَ على التوقيع، (3) بحثٌ حرفيٌّ عن ألفاظ «لا تنتقل الملكية / إلا بالتسجيل / التوقيع /
الإلكترون» في كامل القانون — لأنّ الجسرَ مع 20/2014 لا يُبنى إلّا على معرّفاتٍ محقَّقة."""
import os, re, sys

FULL = ["m3", "m4", "m5", "m6", "m7", "m8", "m9", "m10", "m13", "m14", "m29", "m30"]
NEEDLES = ["لا تنتقل", "إلا بالتسجيل", "الا بالتسجيل", "أثر التسجيل", "التوقيع",
           "الكترون", "إلكترون", "الملكية", "حجة على", "الغير"]


def main():
    import psycopg
    dsn = os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
    with psycopg.connect(dsn) as cx, cx.cursor() as cur:
        cur.execute("SELECT id,title,original_text,branch,topic FROM knowledge_objects "
                    "WHERE id LIKE 'legis-5-1959-%'")
        rows = cur.fetchall()

    def key(r):
        m = re.match(r"legis-5-1959-m(\d+)(?:-mukarrar-(\d+))?", r[0])
        return (int(m.group(1)), int(m.group(2) or 0)) if m else (10**6, 0)

    rows.sort(key=key)
    print("كائنات 5/1959 =", len(rows))
    print("الفرع:", rows[0][3] if rows else "—", "| الموضوع:", (rows[0][4] or "")[:60] if rows else "—")

    print("\n" + "=" * 70)
    print("أوّلًا: الفهرسُ الكامل (المعرّف | أوّلُ 60 حرفًا)")
    print("=" * 70)
    for i, t, x, _, _ in rows:
        print(" %-32s %s" % (i.replace("legis-5-1959-", ""), (x or "").replace(chr(10), " ")[:60]))

    print("\n" + "=" * 70)
    print("ثانيًا: النصُّ الكاملُ للموادّ الحاكمة")
    print("=" * 70)
    by = {r[0]: r for r in rows}
    for k in FULL:
        r = by.get("legis-5-1959-" + k)
        if not r:
            print("\n### %s — غيرُ موجود" % k)
            continue
        print("\n### %s | %s" % (k, (r[1] or "")[:50]))
        print(r[2])

    print("\n" + "=" * 70)
    print("ثالثًا: مواضعُ الألفاظ المفتاحية")
    print("=" * 70)
    for n in NEEDLES:
        hits = [r[0].replace("legis-5-1959-", "") for r in rows if n in (r[2] or "")]
        print(" «%s» ⇐ %d مادة: %s" % (n, len(hits), ", ".join(hits[:14]) or "—"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
