#!/bin/bash
# أمر آلي 62ب: إدخال الكتاب العاشر (الإفصاح والشفافية) إلى بطاقة هيئة أسواق المال — 73 كائناً مدققاً بصرياً
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
PY=/opt/LegalMind/.venv/bin/python

curl -fsSL -H 'Cache-Control: no-cache' "https://raw.githubusercontent.com/dralmarri/LegalMind/main/ops/autorun/data-book10.json?nc=$(date +%s)" -o /tmp/book10.json
echo "حجم ملف البيانات: $(stat -c%s /tmp/book10.json) بايت"

$PY - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys, json
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng
from psycopg.types.json import Json

def adapt(v):
    return Json(v) if isinstance(v, (dict, list)) else v

DOC_PART = 'اللائحة التنفيذية — الكتاب العاشر — الإفصاح والشفافية'
SHA = '1ef7a6674bc54175c6c4455a3512d82d5696f17af31977619eca0012c4a6d749'
SRC = 'SRC-BOOK10-DISCLOSURE-2015'

objects = json.load(open('/tmp/book10.json', encoding='utf-8'))
print("كائنات في الملف:", len(objects), flush=True)

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()

    # قالب من مادة شقيقة (كتاب 12) لضمان توافق كل الأعمدة الإلزامية
    cur.execute("SELECT * FROM knowledge_objects WHERE metadata->>'library_group'='cma-authority-unified' AND object_type='legislation' LIMIT 1")
    cols = [d[0] for d in cur.description]
    tpl = dict(zip(cols, cur.fetchone()))
    print("قالب:", tpl['id'][:40], flush=True)

    cur.execute("""SELECT min(metadata->>'library_card_name') FROM knowledge_objects
                   WHERE metadata->>'library_group'='cma-authority-unified'""")
    card = cur.fetchone()[0] or 'هيئة أسواق المال'
    print("اسم البطاقة:", card, flush=True)

    # سجل المصدر (وراثة بنية سطر مصدر القالب إن أمكن)
    src_key = SRC
    try:
        cur.execute("SELECT * FROM sources WHERE source_key=%s", (tpl['source_key'],))
        srow = cur.fetchone()
        if srow:
            scols = [d[0] for d in cur.description]
            sdict = dict(zip(scols, srow))
            for k in ('source_key',):
                sdict[k] = SRC
            if 'sha256' in sdict:
                sdict['sha256'] = SHA
            for k in ('title', 'filename', 'file_name', 'name'):
                if k in sdict:
                    sdict[k] = 'اللائحة التنفيذية — الكتاب العاشر — الإفصاح والشفافية (نوفمبر 2015 وتحديثاته)'
            if 'id' in sdict:
                del sdict['id']
            cur.execute("SELECT count(*) FROM sources WHERE source_key=%s", (SRC,))
            if cur.fetchone()[0] == 0:
                ks = list(sdict.keys())
                cur.execute("INSERT INTO sources (" + ",".join(ks) + ") VALUES (" + ",".join(["%s"] * len(ks)) + ")",
                            [adapt(sdict[k]) for k in ks])
            print("سجل المصدر جاهز ✓", flush=True)
    except Exception as e:
        src_key = tpl['source_key']
        print("(تعذر إنشاء سجل مصدر مستقل — سيستخدم مصدر القالب: %s)" % str(e)[:90], flush=True)

    cur.execute("DELETE FROM knowledge_objects WHERE id LIKE 'legis-b10-cma-%%'")
    if cur.rowcount:
        print("حذف إدخال سابق:", cur.rowcount, flush=True)

    inserted = 0
    for i, o in enumerate(objects):
        labels = o.get('labels') or []
        text = o['text']
        section = o.get('section') or ''
        if labels:
            first_line = text.split('\n')[0].strip()
            heading = first_line if (len(first_line) < 60 and '.' not in first_line and not first_line[0].isdigit()) else ''
            title = 'مادة ' + ' / '.join(labels) + ((' — ' + heading) if heading else '')
            oid = 'legis-b10-cma-%03d-m%s' % (i, labels[-1])
        else:
            title = (section[:90] if section else 'الكتاب العاشر — تمهيد') 
            oid = 'legis-b10-cma-%03d-intro' % i
        row = dict(tpl)
        row['id'] = oid
        row['title'] = title
        row['original_text'] = text
        row['normalized_text'] = text
        row['branch'] = 'تجاري'
        row['object_type'] = 'legislation'
        row['source_key'] = src_key
        row['usable_as_citation'] = True
        meta = {
            'library_group': 'cma-authority-unified',
            'library_card_name': card,
            'doc_part': DOC_PART,
            'title': 'اللائحة التنفيذية — الكتاب العاشر — الإفصاح والشفافية',
            'section': section,
            'page': o.get('page'),
            'source_sha256': SHA,
            'ingest': 'book10-local-extraction-verified',
        }
        if labels:
            meta['article_number'] = labels[-1]
            meta['article_numbers'] = labels
        row['metadata'] = Json(meta)
        for tcol in ('created_at', 'updated_at'):
            if tcol in row:
                del row[tcol]
        ks = list(row.keys())
        cur.execute("INSERT INTO knowledge_objects (" + ",".join(ks) + ",created_at,updated_at) VALUES ("
                    + ",".join(["%s"] * len(ks)) + ",now(),now())", [adapt(row[k]) for k in ks])
        inserted += 1
    print("أُدخل:", inserted, "كائناً ✓", flush=True)

    print("\n== مجلدات بطاقة هيئة أسواق المال الآن ==", flush=True)
    cur.execute("""SELECT coalesce(metadata->>'doc_part','؟'), count(*) FROM knowledge_objects
                   WHERE metadata->>'library_group'='cma-authority-unified' GROUP BY 1 ORDER BY 1""")
    total = 0
    for p, c in cur.fetchall():
        total += c
        print("  %s : %d" % (p, c), flush=True)
    print("الإجمالي:", total, flush=True)
PYEOF
echo "===== اكتمل الأمر 62ب ====="
