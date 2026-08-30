# -*- coding: utf-8 -*-
import json, os, sys
data=json.load(open('/tmp/tpl_data.json', encoding='utf-8'))
dsn=os.environ.get('DATABASE_URL','postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind')
try:
    import psycopg; conn=psycopg.connect(dsn); DRV='psycopg3'
except Exception:
    import psycopg2 as psycopg; conn=psycopg.connect(dsn); DRV='psycopg2'
try:
    sys.path.insert(0,'/opt/LegalMind'); from engine.legalmind_engine import normalize_text
except Exception:
    import re,unicodedata
    def normalize_text(t):
        t=unicodedata.normalize('NFKC',t); t=re.sub(r'[\u064B-\u0652\u0670\u0640]','',t)
        for a,b in [('\u0623','\u0627'),('\u0625','\u0627'),('\u0622','\u0627'),('\u0649','\u064a'),('\u0629','\u0647')]: t=t.replace(a,b)
        return re.sub(r'\s+',' ',t).strip()
SQL="""INSERT INTO knowledge_objects
 (id,object_type,branch,topic,subtopic,micro_issue,title,original_text,normalized_text,
  verification_status,authority_status,temporal_scope,metadata,usable_as_citation)
 VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s)
 ON CONFLICT (id) DO UPDATE SET object_type=EXCLUDED.object_type,branch=EXCLUDED.branch,
  topic=EXCLUDED.topic,subtopic=EXCLUDED.subtopic,micro_issue=EXCLUDED.micro_issue,title=EXCLUDED.title,
  original_text=EXCLUDED.original_text,normalized_text=EXCLUDED.normalized_text,
  verification_status=EXCLUDED.verification_status,authority_status=EXCLUDED.authority_status,
  metadata=EXCLUDED.metadata,usable_as_citation=EXCLUDED.usable_as_citation,updated_at=now()"""
cur=conn.cursor(); n=0
try:
    for r in data:
        cur.execute(SQL,(r['id'],r['object_type'],r['branch'],r['topic'],r['subtopic'],r['micro_issue'],
            r['title'],r['original_text'],normalize_text(r['original_text']),r['verification_status'],
            r['authority_status'],'{}',json.dumps(r['metadata'],ensure_ascii=False),
            bool(r.get('usable_as_citation',True)))); n+=1
    conn.commit()
except Exception as e:
    conn.rollback(); print('ERROR rolled back:',e); sys.exit(1)
cur.execute("SELECT object_type,count(*) FROM knowledge_objects GROUP BY object_type ORDER BY 2 DESC")
print('=== object_type distribution ===')
for ot,c in cur.fetchall(): print('  %-28s %d'%(ot,c))
cur.execute("SELECT count(*) FROM knowledge_objects"); print('TOTAL:',cur.fetchone()[0])
print('upserted:',n,'| driver:',DRV)
conn.close()
