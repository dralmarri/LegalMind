#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل المرسوم بالقانون رقم 46 لسنة 1987 بشأن إنشاء دائرة عمالية بالمحكمة الكلية.
المصدر: DOCX رسمي بطبقة نصّ سليمة. 5 مواد + ديباجة. الفرع «عمل».
معرّفات: legis-46-1987-m{N} + legis-46-1987-preamble."""
from __future__ import annotations
import argparse, json, os, re, sys

LAW_ID="legis-46-1987"; LAW_NO=46; LAW_YEAR=1987
LAW_TAG="مرسوم بقانون إنشاء الدائرة العمالية (46/1987)"; BRANCH="عمل"
INSTRUMENT="مرسوم بالقانون رقم 46 لسنة 1987 بشأن إنشاء دائرة عمالية بالمحكمة الكلية"
PREAMBLE=("مرسوم بالقانون رقم 46 لسنة 1987 بشأن إنشاء دائرة عمالية بالمحكمة الكلية. "
          "ينشئ هذا المرسوم بقانون دائرة عمالية بالمحكمة الكلية تختص دون غيرها بالفصل في "
          "المنازعات العمالية أياً كانت قيمتها، وينظّم استئناف أحكامها والإحالة إليها.")

def build_rows(data):
    arts=data["articles"]; order=data.get("order") or sorted(arts,key=int); rows=[]
    def meta(x=None):
        m={"instrument":INSTRUMENT,"instrument_rank":"مرسوم بقانون","law_number":LAW_NO,
           "law_year":LAW_YEAR,"upload_origin":"docx_clean_textlayer"}
        if x: m.update(x)
        return m
    rows.append({"id":f"{LAW_ID}-preamble","object_type":"legislation_article","branch":BRANCH,
                 "topic":"الديباجة","subtopic":None,"micro_issue":None,
                 "title":f"ديباجة — {LAW_TAG}","text":PREAMBLE,"meta":meta({"chunk":"preamble"})})
    for n in order:
        rows.append({"id":f"{LAW_ID}-m{n}","object_type":"legislation_article","branch":BRANCH,
                     "topic":"إنشاء الدائرة العمالية واختصاصها","subtopic":None,"micro_issue":None,
                     "title":f"مادة {n} — {LAW_TAG}","text":arts[n].strip(),
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
    print("== تقرير المرسوم بقانون 46/1987 (إنشاء الدائرة العمالية) ==")
    print(f"القانون: {INSTRUMENT} | الفرع: {BRANCH} | البادئة: {LAW_ID}")
    print(f"إجمالي الكائنات: {len(rows)} (مواد: {len(rows)-1} + ديباجة)")
    empty=[r['id'] for r in rows if not r['text'].strip()]; print("فارغة:",empty or "لا")
    ids=[r['id'] for r in rows]; print("مكرّرة:",{i for i in ids if ids.count(i)>1} or "لا")
    for r in rows: print(f"  {r['id']}: {r['text'][:70]}")
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
