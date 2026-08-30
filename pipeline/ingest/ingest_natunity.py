#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل المرسوم بقانون رقم 19 لسنة 2012 في شأن حماية الوحدة الوطنية. 5 مواد + ديباجة، الفرع «جزائي».
نصٌّ نظيفٌ من DOCX ومُتحقَّقٌ من صور الجريدة. معرّفات: legis-19-2012-m{N} / -preamble."""
from __future__ import annotations
import argparse, json, os, re, sys
LAW_ID = "legis-19-2012"; BRANCH = "جزائي"
TOPIC = "حماية الوحدة الوطنية — تجريم خطاب الكراهية وإثارة الفتن والتحريض والعقوبات"
INSTRUMENT = "المرسوم بقانون رقم 19 لسنة 2012 في شأن حماية الوحدة الوطنية"
PREAMBLE_SUMMARY = (
    "المرسوم بقانون رقم 19 لسنة 2012 في شأن حماية الوحدة الوطنية: يجرّم القيام أو الدعوة أو الحض - بأيّ "
    "وسيلةٍ من وسائل التعبير في م29 من القانون 31/1970 (وتشمل الشبكات المعلوماتية والمدونات ووسائل الاتصال "
    "الحديثة) - على كراهية أو ازدراء أيّ فئةٍ من فئات المجتمع، أو إثارة الفتن الطائفية أو القبلية، أو نشر "
    "أفكار تفوّق العرق أو الجماعة أو اللون أو الأصل أو المذهب الديني أو الجنس أو النسب، أو التحريض على العنف "
    "لذلك، أو بثّ الإشاعات الكاذبة المؤدية إليه؛ ويسري خارج الإقليم متى وقعت الجريمة كلًّا أو بعضًا في الكويت "
    "(م1). العقوبة: الحبس ≤7 سنوات وغرامة 10-100 ألف دينار مع المصادرة ومضاعفتها في العَود (م2). الشخص "
    "الاعتباري: غرامة 10-200 ألف وإلغاء الترخيص وإيقافٌ مؤقتٌ مستعجل (م3). الإعفاء بالإبلاغ (م4). يتّصل "
    "بقانون الجزاء 16/1960 والإجراءات 17/1960 والمطبوعات والنشر 3/2006 والإعلام المرئي والمسموع 61/2007. "
    "صدر سنة 2012."
)
def build_rows(data):
    rows = []
    def meta(extra):
        d = {"instrument": INSTRUMENT, "instrument_rank": "مرسوم بقانون", "law_number": 19,
             "law_year": 2012, "upload_origin": "docx_law19_2012_gazette_verified"}
        d.update(extra); return d
    pre = PREAMBLE_SUMMARY + "\n\nـــ ديباجة المرسوم بقانون (سند الإصدار) ـــ\n" + (data.get("preamble_text") or "")
    rows.append({"id": f"{LAW_ID}-preamble", "topic": "الديباجة",
                 "title": "ديباجة — قانون حماية الوحدة الوطنية (19/2012)", "text": pre,
                 "meta": meta({"chunk": "preamble"})})
    for k in data["order"]:
        rows.append({"id": f"{LAW_ID}-{k}", "topic": TOPIC,
                     "title": f"المادة {k[1:]} — قانون حماية الوحدة الوطنية (19/2012)",
                     "text": data["articles"][k], "meta": meta({"article_number": k[1:]})})
    return rows
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
    ap = argparse.ArgumentParser(); ap.add_argument("json"); ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(); data = json.load(open(args.json, encoding="utf-8")); rows = build_rows(data)
    print("== قانون حماية الوحدة الوطنية (19/2012) =="); print(f"الفرع: {BRANCH} | البادئة: {LAW_ID} | كائنات: {len(rows)}")
    blob = " ".join(r["text"] for r in rows); print("� :", "نعم!" if "�" in blob else "لا")
    ids = [r["id"] for r in rows]; print("مكرّرة:", set(i for i in ids if ids.count(i) > 1) or "لا")
    for r in rows:
        if r["id"].endswith(("preamble", "m1", "m2")): print(f"\n--- {r['id']} ---\n{r['text'][:130]}")
    if args.dry_run: print("\n[dry-run]"); return 0
    import psycopg
    from psycopg.types.json import Jsonb
    dsn = os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
    ins = 0
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        for r in rows:
            cur.execute("""INSERT INTO knowledge_objects
                   (id,object_type,branch,topic,subtopic,micro_issue,title,original_text,normalized_text,
                    source_key,verification_status,authority_status,usable_as_citation,metadata)
                   VALUES (%s,'legislation_article',%s,%s,NULL,NULL,%s,%s,%s,NULL,'source_verified','source_authority',TRUE,%s)
                   ON CONFLICT (id) DO UPDATE SET branch=EXCLUDED.branch,topic=EXCLUDED.topic,title=EXCLUDED.title,
                    original_text=EXCLUDED.original_text,normalized_text=EXCLUDED.normalized_text,
                    verification_status='source_verified',usable_as_citation=TRUE,metadata=EXCLUDED.metadata,updated_at=now()""",
                (r["id"], BRANCH, r["topic"], r["title"], r["text"], normalize_text(r["text"]), Jsonb(r["meta"])))
            ins += 1
        conn.commit()
    print(f"\n✓ أُدخل/حُدّث {ins} كائنًا. شغّل reindex."); return 0
if __name__ == "__main__": sys.exit(main())
