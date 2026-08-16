#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل القانون رقم 19 لسنة 2000 بشأن دعم العمالة الوطنية وتشجيعها للعمل في الجهات غير الحكومية.
المصدر: DOCX رسمي بطبقة نصّ سليمة. 18 مادة + ديباجة. الفرع «عمل».
معرّفات: legis-19-2000-m{N} + legis-19-2000-preamble."""
from __future__ import annotations
import argparse, json, os, re, sys

LAW_ID="legis-19-2000"; LAW_NO=19; LAW_YEAR=2000
LAW_TAG="قانون دعم العمالة الوطنية (19/2000)"; BRANCH="عمل"
INSTRUMENT="القانون رقم 19 لسنة 2000 بشأن دعم العمالة الوطنية وتشجيعها للعمل في الجهات غير الحكومية"
TOPIC="دعم العمالة الوطنية وتشجيعها"
PREAMBLE=("القانون رقم 19 لسنة 2000 بشأن دعم العمالة الوطنية وتشجيعها للعمل في الجهات غير الحكومية. "
          "ينظّم هذا القانون سياسات دعم وتشجيع تشغيل العمالة الوطنية في القطاعات غير الحكومية، "
          "والعلاوات الاجتماعية وعلاوة الأولاد، ونسب العمالة الوطنية، وحوافز الإحلال.")

def build_rows(data):
    arts=data["articles"]; order=data.get("order") or sorted(arts,key=int); rows=[]
    def meta(x=None):
        m={"instrument":INSTRUMENT,"instrument_rank":"قانون","law_number":LAW_NO,
           "law_year":LAW_YEAR,"upload_origin":"docx_clean_textlayer"}
        if x: m.update(x)
        return m
    rows.append({"id":f"{LAW_ID}-preamble","object_type":"legislation_article","branch":BRANCH,
                 "topic":"الديباجة","subtopic":None,"micro_issue":None,
                 "title":f"ديباجة — {LAW_TAG}","text":PREAMBLE,"meta":meta({"chunk":"preamble"})})
    for n in order:
        rows.append({"id":f"{LAW_ID}-m{n}","object_type":"legislation_article","branch":BRANCH,
                     "topic":TOPIC,"subtopic":None,"micro_issue":None,
                     "title":f"مادة {n} — {LAW_TAG}","text":(arts[n]["text"] if isinstance(arts[n],dict) else arts[n]).strip(),
                     "meta":meta({"article_number":n})})
    return rows

def normalize_text(t):
    try:
        sys.path.insert(0,"/opt/LegalMind/engine")
        from normalizer.canonical import normalize_text as nt
        return nt(t)
    except Exception:
        import unicodedata
        t=unicodedata.normalize("NFKC",t).replace("ـ","")
        t=re.sub(r"[ \t]+"," ",t); t=re.sub(r" *\n *","\n",t)
        return re.sub(r"\n{3,}","\n\n",t).strip()

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("json"); ap.add_argument("--dry-run",action="store_true")
    a=ap.parse_args(); data=json.load(open(a.json,encoding="utf-8")); rows=build_rows(data)
    print("== تقرير قانون دعم العمالة الوطنية (19/2000) ==")
    print(f"القانون: {INSTRUMENT} | الفرع: {BRANCH} | البادئة: {LAW_ID}")
    print(f"إجمالي الكائنات: {len(rows)} (مواد: {len(rows)-1} + ديباجة)")
    empty=[r['id'] for r in rows if not r['text'].strip()]; print("فارغة:",empty or "لا")
    ids=[r['id'] for r in rows]; print("مكرّرة:",{i for i in ids if ids.count(i)>1} or "لا")
    for r in (rows[1],rows[len(rows)//2],rows[-1]):
        print(f"  {r['id']}: {r['text'][:80]}")
    if a.dry_run: print("[dry-run]"); return 0
    import psycopg; from psycopg.types.json import Jsonb
    dsn=os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
    ins=0
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        for r in rows:
            cur.execute("""INSERT INTO knowledge_objects
                (id,object_type,branch,topic,subtopic,micro_issue,title,original_text,normalized_text,
                 source_key,verification_status,authority_status,usable_as_citation,metadata)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL,'source_verified','source_authority',TRUE,%s)
                ON CONFLICT (id) DO UPDATE SET object_type=EXCLUDED.object_type,branch=EXCLUDED.branch,
                 topic=EXCLUDED.topic,subtopic=EXCLUDED.subtopic,micro_issue=EXCLUDED.micro_issue,
                 title=EXCLUDED.title,original_text=EXCLUDED.original_text,normalized_text=EXCLUDED.normalized_text,
                 verification_status='source_verified',usable_as_citation=TRUE,metadata=EXCLUDED.metadata,updated_at=now()""",
                (r["id"],r["object_type"],r["branch"],r["topic"],r["subtopic"],r["micro_issue"],
                 r["title"],r["text"],normalize_text(r["text"]),Jsonb(r["meta"])))
            ins+=1
        conn.commit()
    print(f"✓ أُدخل/حُدّث {ins} كائنًا. شغّل reindex.")
    return 0
if __name__=="__main__": sys.exit(main())
