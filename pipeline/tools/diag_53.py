import psycopg, os, re
dsn=os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
with psycopg.connect(dsn) as c, c.cursor() as cur:
    cur.execute("""SELECT id,branch,topic,title,left(original_text,110)
                   FROM knowledge_objects
                   WHERE id LIKE 'legis-53-2026-%%' OR id LIKE 'regl-53-2026-%%'
                   ORDER BY id""")
    rows=cur.fetchall()
print("عدد كائنات 53/2026:", len(rows))
def keyn(i):
    m=re.search(r"-m(\d+)",i); return int(m.group(1)) if m else -1
for i,br,tp,ti,tx in rows:
    print("\n[%s] فرع=%s | %s"%(i,br,tp))
    print("   عنوان:",ti)
    print("   نصّ:",(tx or "").replace(chr(10)," "))
# preamble subject
cur=None
