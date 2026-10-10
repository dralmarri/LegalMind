# يستخرج من نصوص ملفات الوورد كل موجز وقاعدة (بصمة لا نص) + سند الطعن — للمقارنة بالقاعدة على الخادم
import re, glob, os, json, hashlib, sys
DIAC = 'ً-ْٰـٓ-ٕ'
def clean_raw(t):
    t = re.sub(r'\x13[^\x13\x14\x15]*\x14', '', t)      # تعليمات الحقول (PAGE …) تُحذف ويبقى ناتجها
    t = re.sub(r'\x13[^\x13\x14\x15]*\x15', '', t)
    t = t.replace('\r', '\n').replace('\x0b', '\n').replace('\x07', '\n').replace('\x0c', '\n')
    t = re.sub(r'[\x00-\x08\x0e-\x1f]', '', t)
    return t
BOIL = re.compile(r'^(?:و)?(?:من)?(?:ال)?(?:مقرر|مستقرعليه|مستقر)(?:ايضا)?(?:فيالفقهوالقضاء)?(?:فيقضاء(?:هذهالمحكمه|محكمهالتمييز|التمييز))?(?:ايضا)?(?:انه|ان)?')
def letters(t):
    t = re.sub('[%s]' % DIAC, '', t)
    t = re.sub('[أإآٱ]', 'ا', t).replace('ة', 'ه').replace('ى', 'ي').replace('ؤ', 'و').replace('ئ', 'ي')
    return re.sub(r'[^ء-ي]', '', t)
def fp(t, n=50):
    s = BOIL.sub('', letters(t))
    if len(s) < 40: return None
    return hashlib.sha1(s[:n].encode()).hexdigest()[:12]
CITE = re.compile(r'\(\s*(?:الطعن|الطعنان|الطعون)\b[^()]*?(?:جلسة|بجلسة)[^()]*\)')
def appeal_keys(c):
    m = re.search(r'(?:الطعن|الطعنان|الطعون)\s*(?:رقما|رقم|أرقام|ارقام)?\s*([0-9،,\s\-و—]+?)\s*/\s*(\d{2,4})', c)
    if not m: return []
    yr = int(m.group(2)); yr = yr + (1900 if yr > 50 else 2000) if yr < 100 else yr
    return ['%s-%d' % (int(n), yr) for n in re.findall(r'\d+', m.group(1))]
def items_of(path):
    t = clean_raw(open(path, encoding='utf-8').read())
    lines = [l.strip() for l in t.split('\n') if l.strip()]
    out, state, pend = [], 'text', []
    for l in lines:
        if re.match(r'^(?:موجز القواعد|الموجز\s*\(?\d*)', l): state = 'mujaz'; continue
        if re.match(r'^(?:القواعد القانونية|القاعدة\s*[:(]?\s*\d*)', l): state = 'rule'; continue
        segs, last = [], 0
        for m in CITE.finditer(l):
            segs.append((l[last:m.start()], m.group(0))); last = m.end()
        tail = l[last:]
        for body, cite in segs:
            if body.strip(): pend.append(body)
            keys = appeal_keys(cite)
            for b in pend:
                f = fp(b)
                if f: out.append({'k': 'rule' if state != 'mujaz' else 'mujaz', 'fp': f, 'ap': keys})
            pend = []
        if tail.strip():
            if state == 'mujaz':
                f = fp(tail)
                if f: out.append({'k': 'mujaz', 'fp': f, 'ap': []})
            else:
                pend.append(tail)
    for b in pend:  # فقرات بلا سند في آخر الملف
        f = fp(b)
        if f: out.append({'k': 'text', 'fp': f, 'ap': []})
    return out
if __name__ == '__main__':
    files = sorted(glob.glob(sys.argv[1] + '/*.txt'))
    data = {'files': [], 'items': []}
    for i, p in enumerate(files):
        name = os.path.basename(p)[:-4]
        its = items_of(p)
        data['files'].append(name)
        for it in its: data['items'].append([i, it['k'], it['fp'], it['ap']])
    json.dump(data, open(sys.argv[2], 'w'), ensure_ascii=False, separators=(',', ':'))
    import collections
    print(len(files), 'files', len(data['items']), 'items', collections.Counter(x[1] for x in data['items']))
