#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُصلِحُ تلفِ النقل في قانون الجزاء 16/1960 — الآمنُ وحده.
يقتصر على ما لا يحتمل قراءةً ثانية: حروفٌ مضاعفة، وأقواسٌ معكوسةٌ اتجاهيًّا، وعنوانُ فرعٍ ابتلعه المتن.
ولا يمسّ تفكيكَ موادّ «مكرر» المدفونة — فترقيمُها غيرُ مؤكّد (علامةُ الحاشية «1» قد تكون التُقطت لاحقةً
للمادة)، وذلك مؤجَّلٌ حتى تصل صورُ الجريدة. تحديثٌ في مكانه: لا يتغيّر عددُ الكائنات.
يتحقّق من وجود النصّ القديم قبل كلّ استبدال ويرفض التنفيذ إن لم يجده."""
from __future__ import annotations
import os, re, sys

# (المعرّف، القديم، الجديد، السند)
FIXES = [
    # ــ حروفٌ/حركاتٌ مضاعفة (لا وجهَ لها في العربية) ــ
    ("legis-16-1960-m127", "تججاوز", "تجاوز", "جيمٌ مضاعفة"),
    ("legis-16-1960-m132", "تججاوز", "تجاوز", "جيمٌ مضاعفة"),
    ("legis-16-1960-m136", "تججاوز", "تجاوز", "جيمٌ مضاعفة"),
    ("legis-16-1960-m176", "تججاوز", "تجاوز", "جيمٌ مضاعفة"),
    ("legis-16-1960-m184", "تججاوز", "تجاوز", "جيمٌ مضاعفة"),
    ("legis-16-1960-m253", "تججاوز", "تجاوز", "جيمٌ مضاعفة"),
    ("legis-16-1960-m268", "تججاوز", "تجاوز", "جيمٌ مضاعفة"),
    ("legis-16-1960-m268", "ويججوز", "ويجوز", "جيمٌ مضاعفة"),
    ("legis-16-1960-m259-mukarrar", "يُُعاقب", "يُعاقب", "ضمّةٌ مضاعفة"),
    # ــ أقواسٌ معكوسةٌ اتجاهيًّا (bidi) ــ
    ("legis-16-1960-m135", "المادتين ) 134 ، 135 (", "المادتين (134، 135)",
     "أقواسٌ معكوسةٌ اتجاهيًّا — الرقمان مؤكَّدان"),
    ("legis-16-1960-m135", "المواد\n) 240،110 ، ) 241 (", "المواد (110، 240، 241)",
     "أقواسٌ معكوسة وقائمةٌ مبعثرة — الأرقامُ الثلاثة (110 و240 و241) مؤكَّدةٌ حضورًا، "
     "ورُتّبت تصاعديًّا وفق الاصطلاح؛ ولا أثرَ للترتيب على الحكم إذ العبرةُ بمجموع المواد المُحال إليها"),
    ("legis-16-1960-m135", "رقم ) 17 ( لسنة\n.1960", "رقم (17) لسنة 1960.",
     "أقواسٌ معكوسة، ونقطةٌ سبقت السنةَ بأثر ترتيب الاتجاهين"),
    ("legis-16-1960-m285", "المادة ) 283 (", "المادة (283)", "أقواسٌ معكوسةٌ اتجاهيًّا"),
    # ــ عنوانُ فرعٍ ابتلعه متنُ المادة ــ
    ("legis-16-1960-m145", "\n-5 التأثير في جهات القضاء والإساءة إلى سمعتها", "",
     "عنوانُ الفرع الخامس التُقط ذيلًا لمتن المادة — يُنزَع فلا يختلط بالنصّ العقابيّ"),
]

# مؤجَّلٌ عمدًا (توثيقٌ فقط):
DEFERRED = [
    ("تفكيك موادّ «مكرر» المدفونة (10 مواد في 6 كائنات)",
     "ترويسةُ «مادة 237 مكرر « 1 أ (((» تُظهر أنّ الرقم «1» علامةُ حاشيةٍ لا لاحقةَ مادة — وهو نفسُ "
     "النمط الذي رأيناه في 3/2006 («المادة 2 )))»). فقد تكون «135 مكرر 1» في الحقيقة «135 مكرر»، "
     "و«145 مكرر 1» و«149 مكرر 1» كذلك. التفكيك على هذا الشكّ يُنتج معرّفاتٍ لموادَّ لا وجودَ لها، "
     "فيؤجَّل حتى تُقرأ الترويساتُ من الجريدة."),
    ("legis-16-1960-m149 و legis-16-1960-m259-mukarrar",
     "فيهما عبارةُ «مادة N مكرر» في وسط السطر لا في أوّله — فقد تكون ترويسةً التصقت بما قبلها، وقد "
     "تكون إحالةً مرجعية. يلزم فحصُهما نصًّا قبل أيّ قرار."),
]


def normalize_text(text):
    try:
        sys.path.insert(0, "/opt/LegalMind/engine")
        from normalizer.canonical import normalize_text as nt
        return nt(text)
    except Exception:
        import unicodedata
        t = unicodedata.normalize("NFKC", text).replace("ـ", "")
        t = re.sub(r"[ \t]+", " ", t); t = re.sub(r" *\n *", "\n", t)
        return re.sub(r"\n{3,}", "\n\n", t).strip()


def main():
    dry = "--dry-run" in sys.argv
    import psycopg
    dsn = os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
    ids = sorted({f for f, _, _, _ in FIXES})
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("SELECT id,original_text FROM knowledge_objects WHERE id = ANY(%s)", (ids,))
        cur_texts = dict(cur.fetchall())
        missing = [i for i in ids if i not in cur_texts]
        if missing:
            print("خطأ: كائنات غائبة:", missing); return 1

        applied, skipped = [], []
        for oid, old, new, why in FIXES:
            t = cur_texts[oid]
            if old in t:
                cur_texts[oid] = t.replace(old, new)
                applied.append((oid, old, new, why, t.count(old)))
            elif new and new in t:
                skipped.append((oid, old, "مطبَّقٌ سلفًا"))
            elif not new and old not in t:
                skipped.append((oid, old[:32], "منزوعٌ سلفًا"))
            else:
                print("خطأ: لم يُعثر على «%s» ولا على بديله في %s — أُوقف التنفيذ صيانةً للنصّ."
                      % (old[:40].replace("\n", "⏎"), oid))
                return 1

        print("== تصحيحاتُ قانون الجزاء 16/1960 (الآمنُ وحده) ==")
        for oid, old, new, why, n in applied:
            print("\n• %s  ×%d\n   «%s»  ⇐  «%s»\n   السند: %s"
                  % (oid, n, old.replace("\n", "⏎"), new.replace("\n", "⏎") or "(نزع)", why))
        for oid, old, note in skipped:
            print("\n• %s: «%s» — %s" % (oid, old.replace("\n", "⏎"), note))
        print("\nالمطبَّق: %d | المتخطَّى: %d" % (len(applied), len(skipped)))
        print("\n== مؤجَّلٌ عمدًا حتى يصل السند ==")
        for what, why in DEFERRED:
            print("• %s\n  %s" % (what, why))

        if dry:
            print("\n[dry-run] لم يُكتب شيء."); return 0

        n = 0
        for oid in ids:
            cur.execute(
                "UPDATE knowledge_objects SET original_text=%s, normalized_text=%s, updated_at=now() WHERE id=%s",
                (cur_texts[oid].strip(), normalize_text(cur_texts[oid]), oid))
            n += cur.rowcount
        conn.commit()
    print("\n✓ حُدّث %d كائنًا في مكانه (لا تغيّر في العدد الإجماليّ). شغّل reindex." % n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
