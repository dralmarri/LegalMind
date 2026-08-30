#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""إتمامُ إصلاح 16/1960: «تججاوز» في م81 — سقطت من قائمة المعرّفات في النشر السابق (خطأُ عدٍّ لا تشخيص).
النمطُ مطابقٌ لأخواتها في م127/م132/م136/م176/م184/م253/م268. تحديثٌ في مكانه."""
import os, re, sys
PAIRS = [("legis-16-1960-m81", "تججاوز", "تجاوز")]
def nt(t):
    try:
        sys.path.insert(0, "/opt/LegalMind/engine")
        from normalizer.canonical import normalize_text as f
        return f(t)
    except Exception:
        import unicodedata
        t = unicodedata.normalize("NFKC", t).replace("\u0640", "")
        t = re.sub(r"[ \t]+", " ", t); t = re.sub(r" *\n *", "\n", t)
        return re.sub(r"\n{3,}", "\n\n", t).strip()
def main():
    import psycopg
    dsn = os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
    n = 0
    with psycopg.connect(dsn) as cx, cx.cursor() as cur:
        for oid, old, new in PAIRS:
            cur.execute("SELECT original_text FROM knowledge_objects WHERE id=%s", (oid,))
            r = cur.fetchone()
            if not r:
                print("خطأ: %s غير موجود" % oid); return 1
            t = r[0]
            if old not in t:
                if new in t:
                    print("• %s: مطبَّقٌ سلفًا" % oid); continue
                print("خطأ: لم يُعثر على «%s» ولا بديله في %s" % (old, oid)); return 1
            c = t.count(old)
            t = t.replace(old, new)
            cur.execute("UPDATE knowledge_objects SET original_text=%s, normalized_text=%s, updated_at=now() WHERE id=%s",
                        (t, nt(t), oid))
            print("• %s: «%s» ⇐ «%s» ×%d" % (oid, old, new, c)); n += 1
        cx.commit()
    print("\n✓ حُدّث %d كائنًا. شغّل reindex." % n)
    return 0
if __name__ == "__main__":
    sys.exit(main())
