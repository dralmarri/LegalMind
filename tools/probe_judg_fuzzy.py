#!/usr/bin/env python3
# مسبار قراءة فقط (الجولة الثانية لملفات الوورد 2026-10-10): البنود التي لم تطابقها البصمة الحرفية —
# هل هي غائبة فعلًا، أم موجودة بصياغة مختلفة أو داخل مبدأ أطول أو حكم كامل؟
# المدخل tools/judg_probe/fuzzy_items.json + fuzzy_shingles.bin.gz: لكل بند بصمات مقاطع من 8 أحرف (crc32، لا نص).
# المقياس: نسبة الاحتواء = كم من مقاطع البند موجود في كائن واحد من القاعدة (مبدأ أو حكم كامل).
# المعايرة المحلية: تغيير ربع الكلمات يُنزل الاحتواء إلى نحو 38% — فالحدود: ≥70 موجود، 30–70 صياغة مختلفة، <30 غائب.
# SELECT فقط؛ لا يكتب في القاعدة شيئًا.
import os, re, sys, json, gzip, base64, struct, zlib, time, collections
import psycopg
DIAC = 'ً-ْٰـٓ-ٕ'
def letters(t):
    t = re.sub('[%s]' % DIAC, '', t)
    t = re.sub('[أإآٱ]', 'ا', t).replace('ة', 'ه').replace('ى', 'ي').replace('ؤ', 'و').replace('ئ', 'ي')
    return re.sub(r'[^ء-ي]', '', t)
here = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'judg_probe')
recs = json.load(open(os.path.join(here, 'fuzzy_items.json'), encoding='utf-8'))['items']
raw = gzip.decompress(open(os.path.join(here, 'fuzzy_shingles.bin.gz'), 'rb').read())
allh = struct.unpack('<%dI' % (len(raw) // 4), raw)
qidx = collections.defaultdict(list)
for ri, (gi, kind, st, mod, ap, off, n) in enumerate(recs):
    for h in allh[off:off + n]: qidx[h].append(ri)
COMMON = 150                                   # مقاطع الصياغة المتكررة (كـ«المقرر في قضاء») لا تُحتسب
common = {h for h, v in qidx.items() if len(v) > COMMON}
for h in common: del qidx[h]
den = [max(1, sum(1 for h in allh[off:off + n] if h not in common)) for (gi, kind, st, mod, ap, off, n) in recs]
best = [(0, None, False, None)] * len(recs)    # (إصابات، المعرف، حكم كامل؟، الموضوع)
kb_ap = set(); t0 = time.time(); nobj = collections.Counter()
with psycopg.connect(os.environ['DATABASE_URL']) as c, c.cursor() as cur:
    cur.execute("SELECT id, object_type, topic, original_text, (metadata ? 'taxonomy_source') FROM knowledge_objects "
                "WHERE object_type IN ('judicial_principle', 'full_judgment')")
    for oid, ot, topic, txt, has_tax in cur:
        nobj[ot] += 1
        m = re.match(r'^jprin-(\d+)-(\d{4})-', oid or '')
        if m: kb_ap.add('%d-%s' % (int(m.group(1)), m.group(2)))
        s = letters(txt or '')
        hs = {h for h in (zlib.crc32(s[i:i + 8].encode()) for i in range(len(s) - 7)) if h % 2 == 0}
        hits = collections.Counter()
        for h in hs:
            for ri in qidx.get(h, ()): hits[ri] += 1
        for ri, k in hits.items():
            if k > best[ri][0]: best[ri] = (k, oid, ot == 'full_judgment', bool(has_tax))
print('KB: %s (%.0fs) — مقاطع شائعة مستبعدة %d' % (dict(nobj), time.time() - t0, len(common)))
out = bytearray(); tab = collections.Counter(); per = collections.defaultdict(collections.Counter)
for ri, (gi, kind, st, mod, ap, off, n) in enumerate(recs):
    k, oid, isj, tax = best[ri]
    pct = min(100, round(100.0 * k / den[ri]))
    b = 'present' if pct >= 70 else ('partial' if pct >= 30 else 'absent')
    apok = any(a in kb_ap for a in ap)
    flag = ('appeal_in_kb' if apok else 'appeal_not_in_kb') if b == 'absent' else ('in_judgment' if isj else 'in_principle')
    tab[(kind, st, b, flag)] += 1
    out.append(pct + (128 if isj else 0))
hist = collections.Counter((recs[i][1], min(9, (v & 127) // 10)) for i, v in enumerate(out))
print('\nتوزيع الاحتواء (عُشريات):')
for kind in ('mujaz', 'rule', 'text'): print('  %-6s' % kind, ' '.join('%d0:%d' % (d, hist[(kind, d)]) for d in range(10)))
print('\nالبند/الحالة السابقة/الحكم الجديد → العدد')
for key in sorted(tab): print('  %-6s s=%d %-8s %-16s %6d' % (key[0], key[1], key[2], key[3], tab[key]))
blob = base64.b64encode(gzip.compress(bytes(out))).decode()
print('\nRESULT_B64 %d chars:' % len(blob)); print(blob)
print('PROBE_JUDG_FUZZY_OK')
