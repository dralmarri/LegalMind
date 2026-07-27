#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تصحيح م99 مدني (67/1980): استرداد التكملة المقتطعة من المصدر الرسمي."""
import os,re,sys,json
NEW=json.loads('"تصرفات المعتوه تسري عليها أحكام تصرفات الصغير المميز المنصوص عليها في المادة 87، نصب عليه قيم أو لم ينصب."')
def nt(t):
    try:
        sys.path.insert(0,"/opt/LegalMind/engine"); from normalizer.canonical import normalize_text as f; return f(t)
    except Exception:
        import unicodedata; x=unicodedata.normalize("NFKC",t).replace("ـ",""); x=re.sub(r"[ \t]+"," ",x); x=re.sub(r" *\n *","\n",x); return re.sub(r"\n{3,}","\n\n",x).strip()
def main():
    dry="--dry-run" in sys.argv
    dsn=os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
    import psycopg
    with psycopg.connect(dsn) as c, c.cursor() as cur:
        cur.execute("select original_text from knowledge_objects where id='legis-67-1980-m99'"); r=cur.fetchone()
        print("[قبل] طول",len((r[0] or "").strip()),"…"+repr((r[0] or "").strip()[-45:]))
        print("[بعد] طول",len(NEW.strip()),"…"+repr(NEW.strip()[-45:]))
        if not dry:
            cur.execute("update knowledge_objects set original_text=%s,normalized_text=%s,verification_status=%s,updated_at=now() where id='legis-67-1980-m99'",(NEW,nt(NEW),"source_verified")); c.commit(); print("\n✓ حُدِّث. شغّل reindex.")
        else: print("\n[dry-run]")
if __name__=="__main__": main()
