#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تنظيف شوائب الاستخراج من نصوص كل المواد: «)))», «(((», «�», أسطر الأقواس الشاردة.
لا يمسّ المحتوى المشروع — يزيل شوائب لا تظهر في نصّ قانوني سليم. تحديث نصّ فقط."""
import os, re, sys

def clean(t):
    if not t:
        return t
    t = t.replace("�", "")                        # �
    lines = [ln for ln in t.split("\n") if not re.fullmatch(r"\s*[)(]+\s*", ln or "")]
    t = "\n".join(lines)
    t = t.replace(")))", "").replace("(((", "")
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()

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
    changed = {}
    samples = []
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("select id, original_text from knowledge_objects "
                    "where original_text ~ '[)][)][)]|[(][(][(]|�' "
                    "or original_text ~ '(^|\n)\\s*[)(]+\\s*($|\n)'")
        rows = cur.fetchall()
        for oid, txt in rows:
            nt = clean(txt)
            if nt != (txt or ""):
                pre = re.match(r"([a-z]+-[^-]+-\d+|[a-z]+-\d+-\d+)", oid)
                pre = pre.group(1) if pre else oid.rsplit("-", 1)[0]
                changed[pre] = changed.get(pre, 0) + 1
                if len(samples) < 8:
                    samples.append((oid, (txt or "")[:40], nt[:40]))
                if not dry:
                    cur.execute("update knowledge_objects set original_text=%s, normalized_text=%s, "
                                "updated_at=now() where id=%s", (nt, normalize_text(nt), oid))
        if not dry:
            conn.commit()
    print(f"مواد فيها شوائب: {len(rows)} | ستُنظَّف: {sum(changed.values())}")
    print("لكل قانون:")
    for pre, c in sorted(changed.items(), key=lambda x: -x[1]):
        print(f"  {pre}: {c}")
    print("\nعيّنات (قبل → بعد):")
    for oid, a, b in samples:
        print(f"  [{oid}]\n    قبل: {a!r}\n    بعد: {b!r}")
    print("\n[dry-run] لم يُحدَّث شيء." if dry else "\n✓ نُظِّفت الشوائب. شغّل reindex.")

if __name__ == "__main__":
    main()
