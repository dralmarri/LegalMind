#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تحقّقٌ من استشهادات جواب «عقد التوريد مع الوزارة» + كشفُ فجوة عدم سماع الدعوى — قراءةٌ فقط.
(1) نصُّ الموادّ المستشهَد بها خارج نواة 20/1981، (2) خريطةُ نصوص عدم سماع الدعوى في المدنيّ
67/1980 — لأنّ النموذج أعلن أنّها «غيرُ مرفقة» وم15 من 20/1981 تُحيل إليها بحكم القانون."""
import os, re, sys

CITED = [("legis-67-1980-m197", "تنفيذُ العقد بحسن نيّة"),
         ("legis-67-1980-m448", "انقطاعُ المدّة بالمطالبة القضائية"),
         ("legis-38-1980-m10", "إعلانُ الجهات الحكومية عبر الفتوى والتشريع"),
         ("legis-38-1980-m45", "رفعُ الدعوى بصحيفة"),
         ("legis-38-1980-m46", "صورُ الصحيفة والمستندات")]
NEEDLES = ["لا تسمع الدعوى", "عدم سماع", "لا تُسمع", "تسقط بالتقادم", "بانقضاء خمس عشرة",
           "خمس عشرة سنة", "تنقضي مدة عدم السماع", "مدة عدم السماع", "انقطاع المدة",
           "يقف سريان", "وقف سريان"]


def main():
    import psycopg
    dsn = os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
    with psycopg.connect(dsn) as cx, cx.cursor() as cur:
        print("=" * 72); print("أوّلًا: الاستشهاداتُ المعلَّقة"); print("=" * 72)
        miss = []
        for oid, lbl in CITED:
            cur.execute("SELECT original_text FROM knowledge_objects WHERE id=%s", (oid,))
            r = cur.fetchone()
            if not r:
                miss.append(oid); print("\n### %s (%s) — ✗ غيرُ موجود" % (oid, lbl)); continue
            print("\n### %s — %s\n%s" % (oid, lbl, re.sub(r"\s+", " ", r[0]).strip()[:520]))
        print("\nالمفقود:", ", ".join(miss) or "لا شيء")

        print("\n" + "=" * 72)
        print("ثانيًا: عدمُ سماع الدعوى في المدنيّ 67/1980 — أين نصوصُه؟")
        print("=" * 72)
        num = lambda i: int(re.search(r"m(\d+)", i).group(1)) if re.search(r"m(\d+)", i) else 10**6
        seen = {}
        for nd in NEEDLES:
            cur.execute("SELECT id FROM knowledge_objects WHERE id LIKE 'legis-67-1980-%%' "
                        "AND original_text LIKE %s", ("%" + nd + "%",))
            ids = sorted({r[0] for r in cur.fetchall()}, key=num)
            print(" «%-22s» ⇐ %2d : %s" % (nd, len(ids),
                  ", ".join(i.replace("legis-67-1980-", "") for i in ids[:16]) or "—"))
            for i in ids:
                seen[i] = True
        rng = sorted(seen, key=num)
        print("\nمجموعُ الموادّ المرشَّحة: %d | المدى: %s .. %s"
              % (len(rng), rng[0].replace("legis-67-1980-", "") if rng else "—",
                 rng[-1].replace("legis-67-1980-", "") if rng else "—"))
        for oid in rng[:14]:
            cur.execute("SELECT left(original_text,150) FROM knowledge_objects WHERE id=%s", (oid,))
            print("  %-8s %s" % (oid.replace("legis-67-1980-", ""),
                                 re.sub(r"\s+", " ", cur.fetchone()[0]).strip()[:130]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
