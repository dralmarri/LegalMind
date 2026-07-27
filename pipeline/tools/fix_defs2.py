#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""إصلاح التعريفات الثلاثة المتبقّية في لائحة أسواق المال (شخص مسجل، مستند العرض المعدل، هيئة التحكيم)
بنصّها الرسمي من صور المستخدم. يُشغَّل بمفسّر المحرّك. معاينة افتراضيًّا؛ --apply يكتب ويفهرس."""
import os, re, sys

DSN = os.getenv("DATABASE_URL") or \
    "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"

D28 = ("أي شخص طبيعي أو اعتباري مسجل لدى الهيئة وفقًا لأحكام المادة (3-1-1) من الفصل الثالث "
       "(الأشخاص المسجلون) من الكتاب الخامس (أنشطة الأوراق المالية والأشخاص المسجلون) من هذه اللائحة وهم:\n"
       "1. شاغلوا المناصب والوظائف واجبة التسجيل لدى الشخص المرخص له.\n"
       "2. مراقبوا الحسابات المسجلين لدى الهيئة.\n"
       "3. مكاتب التدقيق الشرعي الخارجي المسجلة لدى الهيئة.")
D59 = ("مستند العرض الذي يتضمن تعديلًا لصالح مساهمي الشركة محل العرض والمعد وفقًا للضوابط والشروط "
       "المنصوص عليها في المادة (12-3-3) من الكتاب التاسع (الاندماج والاستحواذ).")
D75 = ("هيئة مشكلة وفقًا لنظام التحكيم والمعنية بالفصل في المنازعات الناشئة عن الالتزامات المتعلقة "
       "بالقانون أو أي قانون آخر إذا تعلقت المنازعة بمعاملات أسواق المال.")

OPS = [
    {"id": "lreg-7-2010-k1-d28", "label": "شخص مسجل", "def": D28},
    {"id": "lreg-7-2010-k1-d59", "label": "مستند العرض المعدل", "def": D59},
    {"id": "lreg-7-2010-k1-d75", "label": "هيئة التحكيم", "def": D75},
]


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
    updates = []
    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        for op in OPS:
            oid = op["id"]
            cur.execute("SELECT original_text FROM knowledge_objects WHERE id=%s", (oid,))
            r = cur.fetchone()
            if not r:
                print(f"⚠ {oid}: غير موجود — تخطّي"); continue
            old = r[0] or ""
            cur_label = old.split(":", 1)[0].strip() if ":" in old else ""
            # فحص أمان: تسمية المدخل الحالية تطابق المتوقّعة (حتى لا نستبدل المدخل الخطأ)
            if cur_label != op["label"]:
                print(f"⚠ {oid}: التسمية «{cur_label}» ≠ المتوقّع «{op['label']}» — تخطّي حرصًا"); continue
            new = f"{op['label']}:\n{op['def']}"
            print(f"\n=== {oid} ===")
            print(f"[قبل] {old.strip()[:80]!r}")
            print(f"[بعد] {new.strip()[:80]!r}")
            updates.append((oid, new))
        if not apply:
            print(f"\n[معاينة] تحديث: {len(updates)}. أضِف --apply للتطبيق."); return 0
        for oid, new in updates:
            cur.execute("UPDATE knowledge_objects SET original_text=%s, normalized_text=%s, "
                        "verification_status='source_verified', updated_at=now() WHERE id=%s",
                        (new, nt(new), oid))
        conn.commit()
        print(f"\n✓ حُدِّث {len(updates)}. الآن الفهرسة…")
        ids = [u[0] for u in updates]
        cur.execute("SELECT id,title,original_text,object_type,branch,topic,subtopic,micro_issue,source_key "
                    "FROM knowledge_objects WHERE id = ANY(%s)", (ids,))
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
    print(f"✓ فُهرِس {len(pts)}.\n✓ اكتملت جميع تعريفات لائحة أسواق المال.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
