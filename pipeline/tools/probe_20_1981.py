#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نصُّ نواة القضاء الإداريّ 20/1981 كاملًا — قراءةٌ فقط.
يُطبع سلفًا كي يُقابَل به جوابُ النموذج على سؤال عقد التوريد فورَ وصوله، بلا جولةٍ ثانية.
ويبحث في القاعدة عن أيّ نصٍّ آخر يذكر «عقد اداري» أو «التوريد» — لئلّا يُنسب لهذا القانون
ما هو في غيره (لائحةُ المناقصات 49/2016 مثلًا إن كانت مُدخَلة)."""
import os, re, sys

CORE = ["m1", "m2", "m5", "m6", "m7", "m8", "m9", "m11", "m12", "m12mkr", "m14", "m14mkr", "m15"]


def main():
    import psycopg
    dsn = os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
    with psycopg.connect(dsn) as cx, cx.cursor() as cur:
        print("=" * 72)
        print("نواةُ القضاء الإداريّ — القانون 20/1981 (النصُّ الكامل)")
        print("=" * 72)
        miss = []
        for k in CORE:
            oid = "legis-20-1981-" + k
            cur.execute("SELECT title,original_text FROM knowledge_objects WHERE id=%s", (oid,))
            r = cur.fetchone()
            if not r:
                miss.append(oid); print("\n### %s — ✗ غيرُ موجود" % k); continue
            print("\n### %s | %s\n%s" % (k, (r[0] or "")[:56], re.sub(r"\s+", " ", r[1] or "").strip()))
        print("\nالمفقود:", ", ".join(miss) or "لا شيء")

        print("\n" + "=" * 72)
        print("من غيرُ 20/1981 يذكر «عقد إداري» أو «التوريد» أو «المناقصات»؟")
        print("=" * 72)
        for needle in ("عقد اداري", "عقد إداري", "التوريد", "المناقصات", "مناقصة"):
            cur.execute("SELECT id FROM knowledge_objects WHERE original_text LIKE %s "
                        "AND id NOT LIKE 'legis-20-1981-%%' LIMIT 14", ("%" + needle + "%",))
            ids = [r[0] for r in cur.fetchall()]
            print(" «%-12s» ⇐ %s" % (needle, ", ".join(ids) or "—"))

        cur.execute("SELECT count(*) FROM knowledge_objects")
        print("\nإجمالي كائنات القاعدة =", cur.fetchone()[0])
    return 0


if __name__ == "__main__":
    sys.exit(main())
