import psycopg, os, re
dsn=os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
KW=["دعار","بغاء","فجور","الفسق","هتك عرض","فاضح","التحريض على","حرض","اغتصاب","مواقعة","خطف","استغلال"]
with psycopg.connect(dsn) as c, c.cursor() as cur:
    cur.execute("""SELECT id, left(original_text,140) FROM knowledge_objects
                   WHERE id LIKE 'legis-16-1960-m%%' AND original_text IS NOT NULL
                   ORDER BY (regexp_replace(id,'\\D','','g'))::int""")
    rows=cur.fetchall()
hit=[]
for i,tx in rows:
    if any(k in (tx or "") for k in KW): hit.append((i,tx))
print("مواد الآداب/الدعارة/العرض المطابقة في 16/1960:", len(hit))
for i,tx in hit:
    print("\n[%s] %s"%(i,(tx or "").replace(chr(10)," ")))
# also show the range 198-206 explicitly (common location) regardless of keyword
print("\n=== نطاق 195-210 (فحص مباشر) ===")
d={i:tx for i,tx in rows}
for n in range(195,211):
    k="legis-16-1960-m%d"%n
    if k in d: print("[m%d] %s"%(n, (d[k] or "")[:90].replace(chr(10)," ")))
