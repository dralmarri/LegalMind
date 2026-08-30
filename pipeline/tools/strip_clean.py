#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تنظيف آمن (يُشغَّل بمفسّر المحرّك): حذف «عنوان القسم المُلحق» من ذيل المواد + إزالة '__' +
تصحيح «ملغا ة»→«(ملغاة)». معاينة افتراضيًّا؛ --apply يكتب ثمّ يفهرس كلّ المتغيّرات دفعةً واحدة
(تحميل النموذج مرّة واحدة). استثناءات أمان تلقائية: لا يُحذف سطرٌ يبدأ بعطف (و/ف) أو ببندٍ (حرف مفرد)."""
import os, re, sys, json

DSN = os.getenv("DATABASE_URL") or \
    "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
TERM = set('.؛!؟')
# استثناءات يدوية إضافية (إن لزم)
EXCLUDE = set()
# عناوين أقسام مؤكَّدة يدويًّا تبدأ بواوٍ من بنية الكلمة لا عطفًا (يتجاوز فحص الواو/الفاء)
INCLUDE = {"legis-71-2020-m39", "legis-71-2020-m60"}


def is_strippable(last):
    toks = last.split()
    if not toks:
        return False
    first = toks[0]
    core = re.sub(r'[^؀-ۿ]', '', first)
    if len(core) <= 1:          # حرف بندٍ مفرد (ب، ج-…) ⇒ ليس عنوانًا
        return False
    if last[0] in ("و", "ف"):    # بادئة عطف ⇒ استكمال جملة لا عنوان
        return False
    return True


def strip_last_line(text):
    lines = text.split("\n")
    idxs = [i for i, l in enumerate(lines) if l.strip()]
    if not idxs:
        return text
    del lines[idxs[-1]:]
    return "\n".join(lines).rstrip()


def nt(text):
    try:
        sys.path.insert(0, "/opt/LegalMind/engine")
        from normalizer.canonical import normalize_text as f
        return f(text)
    except Exception:
        import unicodedata
        t = unicodedata.normalize("NFKC", text).replace("ـ", "")
        t = re.sub(r"[ \t]+", " ", t); t = re.sub(r" *\n *", "\n", t)
        return re.sub(r"\n{3,}", "\n\n", t).strip()


def main():
    apply = "--apply" in sys.argv
    import psycopg
    ra = json.load(open("/tmp/refined_audit.json", encoding="utf-8"))
    th = ra.get("trailing_heading", {})
    junk = ra.get("junk_underscore", [])

    changes = []   # (oid, action, new_text)
    skipped = []   # (oid, line, سبب)

    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        # 1) حذف عناوين الأقسام الملحقة
        for lp, items in th.items():
            for oid, line in items:
                if oid in EXCLUDE:
                    skipped.append((oid, line, "استثناء يدوي")); continue
                if oid not in INCLUDE and not is_strippable(line):
                    skipped.append((oid, line, "بند/عطف — تُرك حرصًا")); continue
                cur.execute("SELECT original_text FROM knowledge_objects WHERE id=%s", (oid,))
                r = cur.fetchone()
                if not r:
                    continue
                old = r[0] or ""
                ne = [l.strip() for l in old.split("\n") if l.strip()]
                if not ne or ne[-1] != line:
                    skipped.append((oid, line, "تغيّر النصّ منذ التدقيق")); continue
                new = strip_last_line(old)
                if len(new.strip()) < 15:
                    skipped.append((oid, line, "الناتج قصير جدًّا")); continue
                changes.append((oid, "strip-heading", new))

        # 2) إزالة '__' (وأيّ تتابع شرطات سفلية)
        for oid in junk:
            cur.execute("SELECT original_text FROM knowledge_objects WHERE id=%s", (oid,))
            r = cur.fetchone()
            if not r:
                continue
            old = r[0] or ""
            new = re.sub(r'_+', ' ', old)          # شرطات → مسافة (حفظ حدود الكلمات)
            new = re.sub(r'[^\S\n]{2,}', ' ', new)  # ضغط المسافات الأفقية فقط (حفظ الأسطر)
            new = re.sub(r'[^\S\n]+\n', '\n', new).strip()
            if new != old:
                changes.append((oid, "drop-underscore", new))

        # 3) «ملغا ة» → «(ملغاة)»
        cur.execute("SELECT original_text FROM knowledge_objects WHERE id='legis-35-1978-m3'")
        r = cur.fetchone()
        if r and re.sub(r'\s', '', r[0] or '') == "ملغاة":
            changes.append(("legis-35-1978-m3", "fix-repealed", "(ملغاة)"))

        # ---- تقرير ----
        print(f"===== سيُغيَّر: {len(changes)} مادة | متروك حرصًا: {len(skipped)} =====")
        for oid, act, new in changes:
            tail = new.strip().replace("\n", " ⏎ ")[-70:]
            print(f"  [{act:14}] {oid}\n      ⟶ …{tail}")
        if skipped:
            print("\n----- متروك للمراجعة اليدوية -----")
            for oid, line, why in skipped:
                print(f"  {oid}: {line!r}  ({why})")

        if not apply:
            print("\n[معاينة] لم يُكتب شيء. أضِف --apply للتطبيق.")
            return 0

        for oid, act, new in changes:
            cur.execute("UPDATE knowledge_objects SET original_text=%s, normalized_text=%s, "
                        "updated_at=now() WHERE id=%s", (new, nt(new), oid))
        conn.commit()
        print(f"\n✓ حُدِّث {len(changes)} مادة في القاعدة. الآن الفهرسة الدفعية…")

        # ---- فهرسة دفعية داخل العملية (تحميل النموذج مرّة واحدة) ----
        ids = [c[0] for c in changes]
        cur.execute(
            "SELECT id,title,original_text,object_type,branch,topic,subtopic,micro_issue,source_key "
            "FROM knowledge_objects WHERE id = ANY(%s)", (ids,))
        rows = cur.fetchall()

    sys.path.insert(0, "/opt/LegalMind"); sys.path.insert(0, "/opt/LegalMind/engine")
    from engine import embedding
    from engine.legalmind_engine import COLLECTION, qdrant_request
    vectors = embedding.embed_passages([r[2] for r in rows])
    points = []
    for r, vec in zip(rows, vectors):
        oid, title, text, otype, branch, topic, subtopic, micro, skey = r
        points.append({"id": embedding.point_id(oid), "vector": vec,
                       "payload": {"object_type": otype, "branch": branch, "topic": topic,
                                   "subtopic": subtopic, "micro_issue": micro,
                                   "source_key": skey, "object_id": oid, "title": title or "",
                                   **embedding.meta_for(oid, text).as_payload()}})
    qdrant_request("PUT", f"/collections/{COLLECTION}/points?wait=true", {"points": points})
    print(f"✓ فُهرِست {len(points)} نقطة (تحميل النموذج مرّة واحدة). تمّ التنظيف.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
