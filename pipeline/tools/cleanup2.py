#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تنظيف متابعة موجَّه (بمفسّر المحرّك): يكمّل ما فات تشغيل v1:
 - حذف عنواني قسمٍ ملحقين (m39 «واجبات الأمين»، m60 «وقف المطالبات») بدآ بواوٍ بنيوية.
 - إصلاح دمجٍ ناتج عن حذف الشرطة في m47: «منهماوامتناعه» → «منهما وامتناعه».
معاينة افتراضيًّا؛ --apply يكتب ثم يفهرس المتغيّرات دفعةً واحدة. كلّ عملية بفحص أمان (تحقّق من المطابقة)."""
import os, re, sys

DSN = os.getenv("DATABASE_URL") or \
    "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"

OPS = [
    {"id": "legis-71-2020-m39", "type": "strip", "line": "واجبات الأمين"},
    {"id": "legis-71-2020-m60", "type": "strip", "line": "وقف المطالبات"},
    {"id": "legis-38-1980-m47", "type": "replace", "find": "منهماوامتناعه", "repl": "منهما وامتناعه"},
]


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
    changed = []
    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        for op in OPS:
            oid = op["id"]
            cur.execute("SELECT original_text FROM knowledge_objects WHERE id=%s", (oid,))
            r = cur.fetchone()
            if not r:
                print(f"⚠ {oid}: غير موجود"); continue
            old = r[0] or ""
            if op["type"] == "strip":
                ne = [l.strip() for l in old.split("\n") if l.strip()]
                if not ne or ne[-1] != op["line"]:
                    print(f"• {oid}: السطر الأخير ليس «{op['line']}» (…{ne[-1] if ne else ''!r}) — تخطّي"); continue
                new = strip_last_line(old)
            else:  # replace
                if op["find"] not in old:
                    print(f"• {oid}: «{op['find']}» غير موجود — تخطّي (قد يكون مُصلَحًا)"); continue
                new = old.replace(op["find"], op["repl"])
            if new == old:
                print(f"• {oid}: لا تغيير"); continue
            print(f"\n=== {oid} ({op['type']}) ===")
            print(f"[قبل] …{old.strip()[-70:]!r}")
            print(f"[بعد] …{new.strip()[-70:]!r}")
            if apply:
                cur.execute("UPDATE knowledge_objects SET original_text=%s, normalized_text=%s, "
                            "updated_at=now() WHERE id=%s", (new, nt(new), oid))
                changed.append(oid)
        if apply:
            conn.commit()
        if not apply:
            print("\n[معاينة] لم يُكتب شيء. أضِف --apply للتطبيق.")
            return 0
        if not changed:
            print("\nلا تغييرات."); return 0
        cur.execute(
            "SELECT id,title,original_text,object_type,branch,topic,subtopic,micro_issue,source_key "
            "FROM knowledge_objects WHERE id = ANY(%s)", (changed,))
        rows = cur.fetchall()

    sys.path.insert(0, "/opt/LegalMind"); sys.path.insert(0, "/opt/LegalMind/engine")
    from engine import embedding
    from engine.legalmind_engine import COLLECTION, qdrant_request
    vecs = embedding.embed_passages([r[2] for r in rows])
    pts = []
    for r, v in zip(rows, vecs):
        oid, title, text, otype, branch, topic, subtopic, micro, skey = r
        pts.append({"id": embedding.point_id(oid), "vector": v,
                    "payload": {"object_type": otype, "branch": branch, "topic": topic,
                                "subtopic": subtopic, "micro_issue": micro, "source_key": skey,
                                "object_id": oid, "title": title or "",
                                **embedding.meta_for(oid, text).as_payload()}})
    qdrant_request("PUT", f"/collections/{COLLECTION}/points?wait=true", {"points": pts})
    print(f"\n✓ حُدِّث وفُهرِس {len(pts)} مادة.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
