#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""إصلاح تعريفات لائحة أسواق المال المشوّهة (OCR): 3 استبدال تعريف من المصدر الرسمي،
إعادة بناء مدخل b28، حذف سطر مشوّه مكرّر في b7، وحذف الزائدة b19 (قاعدة + Qdrant).
يُشغَّل بمفسّر المحرّك. معاينة افتراضيًّا؛ --apply يكتب ثمّ يفهرس المُحدَّث ويحذف نقطة b19."""
import os, re, sys

DSN = os.getenv("DATABASE_URL") or \
    "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"

B28 = (
    "كبار التنفيذيين\n"
    "كبار المساهمين\n"
    "كفيل\n"
    "كفيل عيني\n"
    "كيان مركزي لإيداع الأوراق المالية\n"
    "الأشخاص الذين يشغلون وظائف تنفيذية ويقومون بالأعمال المهمة والأساسية المرتبطة بالأنشطة المرخصة التي يمارسها الشخص المرخص له.\n"
    "أي مساهم يمتلك 5 % أو أكثر من أسهم الشركة المساهمة.\n"
    "شخص غير الملتزم يضمن - بكامل ذمته المالية - الوفاء بالالتزامات الناشئة عن الصكوك مع بقاء ذمة الملتزم مشغولة بالوفاء بهذه الالتزامات.\n"
    "شخص غير المدين يرهن عقارًا أو منقولًا مملوكًا له لضمان الوفاء بالتزام في ذمة المدين.\n"
    "شخص اعتباري مرخص له بمزاولة نشاط وكالة مقاصة لتقديم خدمة إيداع الأوراق المالية ضمن نظام الحفظ المركزي للأوراق المالية، "
    "ونقل ملكيتها وتسجيل المعاملات المتعلقة بها بما فيها البيع والشراء وتحويل الملكية والرهن وغيرها من المعاملات والخدمات الإضافية "
    "التي ترد في قواعد الكيان المركزي لإيداع الأوراق المالية."
)

OPS = [
    {"id": "lreg-7-2010-k1-d16", "type": "replace-def",
     "def": "الشخص الذي يتبع شخصًا آخر أو أشخاصًا آخرين أو يخضع لسلطتهم."},
    {"id": "lreg-7-2010-k1-d22", "type": "replace-def",
     "def": "كل وضع، أو اتفاق، أو ملكية لأسهم، أو حصص أيًّا كانت نسبتها تؤدي إلى التحكم في تعيين "
            "أغلبية أعضاء مجلس الإدارة أو في القرارات الصادرة منه أو من الجمعيات العامة للشركة المعنية."},
    {"id": "lreg-7-2010-k1-d80", "type": "replace-def",
     "def": "الشخص الذي يعرض أو يبيع أوراقًا مالية لصالح مصدرها أو حليفه أو يحصل على أوراق مالية "
            "من المصدر أو حليفه بغرض إعادة التسويق."},
    {"id": "lreg-7-2010-k1-b28", "type": "replace-full", "text": B28,
     "must_have": ["كفيل عيني", "كيان مركزي"]},
    {"id": "lreg-7-2010-k1-b7", "type": "remove-line", "marker": "اختصاالمحمات"},
    {"id": "lreg-7-2010-k1-b19", "type": "delete", "must_have": ["أكتو"]},
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
    updates, deletes = [], []
    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        for op in OPS:
            oid = op["id"]
            cur.execute("SELECT original_text FROM knowledge_objects WHERE id=%s", (oid,))
            r = cur.fetchone()
            if not r:
                print(f"⚠ {oid}: غير موجود — تخطّي"); continue
            old = r[0] or ""
            for kw in op.get("must_have", []):
                if kw not in old:
                    print(f"⚠ {oid}: لا يحوي «{kw}» — تخطّي حرصًا"); op = None; break
            if op is None:
                continue
            t = op["type"]
            if t == "replace-def":
                label = old.split(":", 1)[0].strip() if ":" in old else old.split("\n", 1)[0].strip()
                new = f"{label}:\n{op['def']}"
            elif t == "replace-full":
                new = op["text"]
            elif t == "remove-line":
                lines = old.split("\n")
                keep = [l for l in lines if op["marker"] not in l]
                removed = len(lines) - len(keep)
                if removed != 1:
                    print(f"⚠ {oid}: عدد الأسطر المحذوفة {removed} (متوقّع 1) — تخطّي"); continue
                new = "\n".join(keep).strip()
            elif t == "delete":
                print(f"\n=== {oid} (DELETE) ===\n[سيُحذف] {old.strip()[:60]!r}")
                deletes.append(oid); continue
            else:
                continue
            print(f"\n=== {oid} ({t}) ===")
            print(f"[قبل] {old.strip()[:75]!r}")
            print(f"[بعد] {new.strip()[:75]!r}")
            updates.append((oid, new))

        if not apply:
            print(f"\n[معاينة] تحديث: {len(updates)} | حذف: {len(deletes)}. أضِف --apply للتطبيق.")
            return 0

        for oid, new in updates:
            cur.execute("UPDATE knowledge_objects SET original_text=%s, normalized_text=%s, "
                        "verification_status='source_verified', updated_at=now() WHERE id=%s",
                        (new, nt(new), oid))
        for oid in deletes:
            cur.execute("DELETE FROM knowledge_objects WHERE id=%s", (oid,))
        conn.commit()
        print(f"\n✓ حُدِّث {len(updates)} وحُذف {len(deletes)} من القاعدة. الآن الفهرسة/الحذف في Qdrant…")

        upd_ids = [u[0] for u in updates]
        cur.execute(
            "SELECT id,title,original_text,object_type,branch,topic,subtopic,micro_issue,source_key "
            "FROM knowledge_objects WHERE id = ANY(%s)", (upd_ids,))
        rows = cur.fetchall()

    sys.path.insert(0, "/opt/LegalMind"); sys.path.insert(0, "/opt/LegalMind/engine")
    from engine import embedding
    from engine.legalmind_engine import COLLECTION, qdrant_request
    if rows:
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
        print(f"✓ فُهرِس {len(pts)} مُحدَّثًا.")
    for oid in deletes:
        qdrant_request("POST", f"/collections/{COLLECTION}/points/delete?wait=true",
                       {"points": [embedding.point_id(oid)]})
        print(f"✓ حُذفت نقطة {oid} من Qdrant.")
    print("\n✓ تمّ إصلاح تعريفات لائحة أسواق المال.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
