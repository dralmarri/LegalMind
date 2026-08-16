#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تصحيحاتٌ نصّيةٌ مستهدَفة — بلا وسيط: معاينةٌ فقط؛ مع `--apply` تُكتب.

كلُّ تصحيحٍ أدناه إمّا **لا-كلمة** في العربية (سقوطُ حرفٍ يقينيّ) وإمّا رسمٌ مهموزٌ ناقص. ولا يُمَسّ
موضعٌ يحتمل قراءتين، ولا يُخمَّن رقمٌ ولا تاريخ. ويرفض السكربتُ التنفيذَ إن لم يجد النصَّ القديم ولا
الجديد (دليلَ أنّ المادة ليست ما نظنّ)، ويمرّ صامتًا إن وجد الجديدَ وحده (تصحيحٌ سابق).

المؤجَّلُ عمدًا في legis-5-1959-m14: تاريخا البندين الثاني والثالث (26/4/1960 و26/4/1959) — اختلافُ
السنة بين بندين متجاورين مريب، ولا يُقرَّر إلّا بصورة الجريدة الرسمية. وكذلك «-01» و«)الكشف النظري(»
في م3: عيبُ اتّجاهٍ في العرض لا في التخزين على الأرجح، ولا يُصلَح بلا معاينةٍ بايتية.
"""
from __future__ import annotations
import os, re, sys

FIXES = [
    ("legis-5-1959-m14",
     "مضافا إلى ما بعد اموت",
     "مضافا إلى ما بعد الموت",
     "«اموت» لا-كلمة؛ سقوطُ لامٍ من «الموت». والسياقُ قاطع: تصرّفٌ مضافٌ إلى ما بعد الموت."),
    ("legis-20-1981-m2",
     "الأخر",
     "الآخر",
     "رسمُ المدّة ناقص؛ «الأخر» لا-كلمة في هذا السياق، وصوابُها «الآخر»."),
]


def main():
    apply = "--apply" in sys.argv
    import psycopg
    dsn = os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
    changed = []
    with psycopg.connect(dsn) as cx, cx.cursor() as cur:
        print("== تصحيحاتٌ نصّيةٌ مستهدَفة ==")
        print("الوضع: %s\n" % ("تطبيقٌ فعليّ" if apply else "معاينةٌ فقط — لن يُكتب شيء"))
        for oid, old, new, sanad in FIXES:
            cur.execute("SELECT original_text FROM knowledge_objects WHERE id=%s", (oid,))
            r = cur.fetchone()
            if not r:
                print("خطأ: %s غيرُ موجود — أُوقف التنفيذ." % oid)
                return 1
            txt = r[0] or ""
            n_old, n_new = txt.count(old), txt.count(new)
            print("### %s" % oid)
            print("    السند: %s" % sanad)
            print("    «%s» ×%d  |  «%s» ×%d" % (old, n_old, new, n_new))
            if n_old == 0 and n_new == 0:
                print("خطأ: لا القديمُ ولا الجديدُ موجود في %s — المادةُ ليست ما نظنّ. أُوقف." % oid)
                return 1
            if n_old == 0:
                print("    ⇐ مُصحَّحٌ سلفًا، لا عمل.\n")
                continue
            i = txt.find(old)
            print("    قبل: …%s…" % txt[max(0, i - 60):i + len(old) + 60].replace("\n", " "))
            print("    بعد: …%s…\n" % (txt[max(0, i - 60):i] + new +
                                       txt[i + len(old):i + len(old) + 60]).replace("\n", " "))
            changed.append((oid, txt.replace(old, new)))

        if not changed:
            print("لا تصحيحاتٍ معلَّقة.")
            return 0
        print("عددُ الكائنات التي ستُعدَّل: %d ⇐ %s" % (len(changed), ", ".join(c[0] for c in changed)))
        if not apply:
            print("\n[معاينة] لم يُكتب شيء. للتطبيق: أضف --apply")
            return 0

        sys.path.insert(0, "/opt/LegalMind/engine")
        try:
            from normalizer.canonical import normalize_text as nt
        except Exception:
            import unicodedata

            def nt(t):
                t = unicodedata.normalize("NFKC", t).replace("ـ", "")
                t = re.sub(r"[ \t]+", " ", t); t = re.sub(r" *\n *", "\n", t)
                return re.sub(r"\n{3,}", "\n\n", t).strip()

        for oid, new_txt in changed:
            cur.execute("UPDATE knowledge_objects SET original_text=%s, normalized_text=%s, "
                        "updated_at=now() WHERE id=%s", (new_txt, nt(new_txt), oid))
        cx.commit()
    print("\n✓ عُدِّل %d كائنًا. تُعاد فهرسةُ كلٍّ منها موضعيًّا (لا reindex كامل)." % len(changed))
    print("IDS=" + " ".join(c[0] for c in changed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
