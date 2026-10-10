#!/usr/bin/env python3
# مسبار قراءة فقط: هل مبادئ ملفات الوورد التي أرسلها المالك (2026-10-10) موجودة في القاعدة؟
# المدخل tools/judg_probe/items.json: بصمات فقط (لا نص) — لكل موجز/قاعدة بصمة أول 50 حرفًا عربيًا بعد حذف
# «من المقرر في قضاء هذه المحكمة أن» ونحوها، وسند الطعن (رقم-سنة). يقابلها ببصمات كل سطر من كل مبدأ في القاعدة.
# SELECT فقط؛ لا يكتب في القاعدة شيئًا. التقرير الكامل في /opt/legalmind-data/judg_probe_<ts>.json
import os, re, sys, json, hashlib, collections, time, gzip, base64
import psycopg
DIAC = 'ً-ْٰـٓ-ٕ'
BOIL = re.compile(r'^(?:و)?(?:من)?(?:ال)?(?:مقرر|مستقرعليه|مستقر)(?:ايضا)?(?:فيالفقهوالقضاء)?(?:فيقضاء(?:هذهالمحكمه|محكمهالتمييز|التمييز))?(?:ايضا)?(?:انه|ان)?')
def letters(t):
    t = re.sub('[%s]' % DIAC, '', t)
    t = re.sub('[أإآٱ]', 'ا', t).replace('ة', 'ه').replace('ى', 'ي').replace('ؤ', 'و').replace('ئ', 'ي')
    return re.sub(r'[^ء-ي]', '', t)
def fp(t, n=50):
    s = BOIL.sub('', letters(t))
    if len(s) < 40: return None
    return hashlib.sha1(s[:n].encode()).hexdigest()[:12]

here = os.path.dirname(os.path.abspath(__file__))
data = json.load(open(os.path.join(here, 'judg_probe', 'items.json'), encoding='utf-8'))
files, items = data['files'], data['items']
t0 = time.time()
kb_fp = {}                       # بصمة ← (المعرف، له تبويب مصدر؟، الموضوع)
kb_ap = set()                    # «رقم-سنة» من معرفات المبادئ
with psycopg.connect(os.environ['DATABASE_URL']) as c, c.cursor() as cur:
    cur.execute("SELECT id, topic, original_text, (metadata ? 'taxonomy_source') FROM knowledge_objects "
                "WHERE object_type = 'judicial_principle'")
    n_kb = 0
    for oid, topic, txt, has_tax in cur:
        n_kb += 1
        m = re.match(r'^jprin-(\d+)-(\d{4})-', oid or '')
        if m: kb_ap.add('%d-%s' % (int(m.group(1)), m.group(2)))
        for line in (txt or '').split('\n'):
            f = fp(line)
            if f and f not in kb_fp: kb_fp[f] = (oid, bool(has_tax), topic)
print('KB principles: %d, line fingerprints: %d, appeal keys: %d (%.0fs)' % (n_kb, len(kb_fp), len(kb_ap), time.time() - t0))

per = collections.defaultdict(lambda: collections.Counter())
status = []                      # لكل بند: 1 مطابق بالبصمة، 2 سنده موجود فقط، 0 غائب
tax = collections.Counter()
for fi, kind, f, aps in items:
    c = per[fi]; c[kind] += 1
    if f in kb_fp:
        st = 1; c[kind + '_fp'] += 1; tax['with_source_taxonomy' if kb_fp[f][1] else 'without_source_taxonomy'] += 1
    elif any(a in kb_ap for a in aps):
        st = 2; c[kind + '_ap'] += 1
    else:
        st = 0; c[kind + '_new'] += 1
    status.append(st)

tot = collections.Counter()
print('\n%-26s %18s %26s' % ('الملف', 'موجز: بصمة/الكل', 'قاعدة: بصمة|سند/الكل'))
for fi, name in enumerate(files):
    c = per[fi]; tot.update(c)
    print('%-26s %8d/%-8d %10d|%d/%-8d' % (name[:26], c['mujaz_fp'], c['mujaz'], c['rule_fp'], c['rule_ap'], c['rule']))
print('\nالمجموع: موجز %d — مطابق بالبصمة %d (%.1f%%)، غائب %d' % (
    tot['mujaz'], tot['mujaz_fp'], 100.0 * tot['mujaz_fp'] / max(1, tot['mujaz']), tot['mujaz_new'] + tot['mujaz_ap']))
print('       قاعدة %d — مطابقة بالبصمة %d، سندها موجود %d، غائبة كليًا %d' % (
    tot['rule'], tot['rule_fp'], tot['rule_ap'], tot['rule_new']))
print('       نص بلا سند %d — مطابق %d' % (tot['text'], tot['text_fp']))
print('المطابَق في القاعدة: بتبويب مصدر %d، بلا تبويب مصدر %d' % (tax['with_source_taxonomy'], tax['without_source_taxonomy']))
ts = time.strftime('%Y%m%d_%H%M%S')
out = os.path.join(os.environ.get('JUDG_PROBE_OUT', '/opt/legalmind-data'), 'judg_probe_%s.json' % ts)
json.dump({'files': files, 'status': status, 'per_file': {files[k]: dict(v) for k, v in per.items()}},
          open(out, 'w', encoding='utf-8'), ensure_ascii=False)
blob = base64.b64encode(gzip.compress(bytes(status))).decode()
print('\nREPORT:', out)
print('STATUS_B64 %d chars (لصقه يكفيني لتفصيل الغائب):' % len(blob))
print(blob)
print('PROBE_JUDG_OK')
