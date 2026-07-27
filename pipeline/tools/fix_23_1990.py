#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تصحيح نصّي مادتين مجتزأتين في قانون تنظيم القضاء 23/1990 من النصّ الرسمي
(م13: استُكملت «ويتولى رئيس الجلسة ضبط نظامها»؛ م22: «بحب»→«بحسب» + نقطة الختام).
تحديث نصّ فقط — لا يغيّر عدد الكائنات."""
import os, re, sys

FIXES = {
    "legis-23-1990-m13": (
        "جلسات المحاكم علنية ويجوز أن تقرر المحكمة جعل الجلسة سرية إذا اقتضى ذلك "
        "النظام العام أو المحافظة على الآداب. ويكون النطق بالحكم في جميع الأحوال في "
        "جلسة علنية ويتولى رئيس الجلسة ضبط نظامها."
    ),
    "legis-23-1990-m22": (
        "تتقرر أقدمية رجال القضاء والنيابة العامة بحسب تاريخ المرسوم الصادر بتعيينهم "
        "في وظائفهم ما لم يحدد هذا المرسوم تاريخا آخر بناء على موافقة المجلس الأعلى للقضاء.\n"
        "فإذا عين اثنان أو أكثر من رجال القضاء أو النيابة العامة في مرسوم واحد كانت "
        "الأقدمية بينهم بحسب ترتيبهم في المرسوم."
    ),
}

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
    dsn = os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
    import psycopg
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        for oid, newtext in FIXES.items():
            cur.execute("select original_text from knowledge_objects where id=%s", (oid,))
            r = cur.fetchone()
            if not r:
                print(f"✗ غير موجود: {oid}"); continue
            print(f"\n=== {oid} ===")
            print(f"[قبل] …{(r[0] or '').strip()[-60:]!r}")
            print(f"[بعد] …{newtext.strip()[-60:]!r}")
            if dry:
                continue
            cur.execute(
                "update knowledge_objects set original_text=%s, normalized_text=%s, "
                "verification_status='source_verified', updated_at=now() where id=%s",
                (newtext, normalize_text(newtext), oid))
        if not dry:
            conn.commit()
            print("\n✓ حُدِّث النصّ. شغّل reindex.")
        else:
            print("\n[dry-run] لم يُحدَّث شيء.")

if __name__ == "__main__":
    main()
