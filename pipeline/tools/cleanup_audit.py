#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تدقيق شامل (قراءة فقط) لجودة نصوص مواد التشريعات عبر كامل القاعدة.
يصنّف لكلّ مادة: junk (شوائب) / title_pollution (تلوّث عنوان المادة التالية) /
trunc_strong (بترٌ شبه مؤكَّد: تنتهي بكلمة وظيفية) / trunc_maybe (بترٌ محتمل) /
short (قِصر مفرط). لا يكتب شيئًا في القاعدة.
المخرَج: ملخّص لكلّ قانون + عيّنات للفئات القابلة للإصلاح + ملفّ JSON بالمعرّفات في /tmp."""
import re, json, os, sys
from collections import defaultdict

DSN = os.getenv("DATABASE_URL") or \
    "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"

# علامات ختام مشروعة لنهاية مادة (الفاصلة «،» ليست ختامًا)
TERM = set('.؛»)!؟"')
# كلمات وظيفية لا تصحّ نهايةً لمادة (دلالة بترٍ قويّة)
FUNC = {"في","على","من","الى","إلى","عن","أن","ان","التي","الذي","الذين","و","او","أو","ثم",
        "بين","لدى","حتى","اذا","إذا","كل","بعد","قبل","عند","مع","لا","ما","او","إذ","اذ",
        "هذا","هذه","تلك","ذلك","اي","أي","كما","بأن","بان","لكل","بكل","وفي","وعلى","ومن"}
HDR = re.compile(r'^\s*(?:ال)?ماد[ةه]\s*\(?\s*(\d+)')
JUNK = re.compile(r'[�]|\)\)\)|\(\(\(')
PAREN_LINE = re.compile(r'^\s*[)(]+\s*$')
SIG = re.compile(r'\d{4}|أمير الكويت|رئيس مجلس|رئيس الوزراء|وزير|صدر (?:في|بقصر)|بقصر السيف')


def artnum(oid):
    m = re.search(r'-m(\d+)', oid)
    return int(m.group(1)) if m else None


def law_prefix(oid):
    m = re.match(r'(legis-\d+-\d+)', oid)
    return m.group(1) if m else oid.rsplit('-', 1)[0]


def classify(oid, text):
    out = []
    t = text or ""
    lines = t.split("\n")
    ne = [l for l in lines if l.strip()]
    body = t.strip()
    if not body:
        return ["empty"]
    if body == "(ملغاة)" or "ملغاة" in body[:12]:
        return []                                  # مادة ملغاة — لا مشكلة
    if JUNK.search(t) or any(PAREN_LINE.match(l) for l in lines):
        out.append("junk")
    # تلوّث عنوان: آخر سطر غير فارغ رأس مادة برقمٍ مختلف عن رقم المادة الحالية
    if ne:
        last = ne[-1].strip()
        m = HDR.match(last)
        if m and len(last) <= 70:
            n = int(m.group(1)); cur = artnum(oid)
            if cur is None or n != cur:
                out.append("title_pollution")
    # بتر: لا تنتهي بعلامة ختام، وليست توقيعًا/تاريخًا
    if body[-1] not in TERM and not SIG.search(body[-45:]):
        words = re.findall(r'[؀-ۿ]+', body)
        lw = words[-1] if words else ""
        norm = re.sub(r'[أإآ]', 'ا', re.sub(r'[ىي]', 'ي', lw)).replace('ة', 'ه')
        if norm in FUNC:
            out.append("trunc_strong")
        else:
            out.append("trunc_maybe")
    if len(body) < 25:
        out.append("short")
    return out


def main():
    import psycopg
    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute("""SELECT id, coalesce(original_text,''), coalesce(title,'')
                       FROM knowledge_objects
                       WHERE object_type LIKE 'legislation%' OR id LIKE 'legis-%'
                       ORDER BY id""")
        rows = cur.fetchall()

    per_law = defaultdict(lambda: defaultdict(list))
    cats = defaultdict(list)
    for oid, text, title in rows:
        for c in classify(oid, text):
            per_law[law_prefix(oid)][c].append(oid)
            cats[c].append(oid)

    print(f"إجمالي مواد التشريع المفحوصة: {len(rows)}  | قوانين: {len(per_law)}\n")
    order = ["junk", "title_pollution", "trunc_strong", "trunc_maybe", "short", "empty"]
    hdr = "القانون".ljust(20) + "".join(c[:10].rjust(15) for c in order)
    print(hdr); print("-" * len(hdr))
    for lp in sorted(per_law, key=lambda k: -sum(len(v) for v in per_law[k].values())):
        d = per_law[lp]
        if not any(d.values()):
            continue
        row = lp.ljust(20) + "".join((str(len(d.get(c, []))) or "·").rjust(15) for c in order)
        print(row)
    print("\n==== الإجماليات ====")
    for c in order:
        print(f"  {c:16}: {len(cats[c])}")

    def samples(cat, n=8):
        print(f"\n==== عيّنات: {cat} (حتى {n}) ====")
        ids = cats[cat][:n]
        by = {r[0]: (r[1], r[2]) for r in rows if r[0] in set(ids)}
        for oid in ids:
            text, title = by.get(oid, ("", ""))
            body = (text or "").strip()
            tail = body[-120:].replace("\n", " ⏎ ")
            print(f"\n• {oid}  [{title[:40]}]")
            print(f"   …{tail}")

    samples("title_pollution")
    samples("trunc_strong")

    # اكتب المعرّفات كاملةً لخطوة الإصلاح
    outp = "/tmp/cleanup_audit.json"
    with open(outp, "w", encoding="utf-8") as f:
        json.dump({c: cats[c] for c in order}, f, ensure_ascii=False, indent=1)
    print(f"\n✓ كُتبت قوائم المعرّفات الكاملة: {outp}")


if __name__ == "__main__":
    sys.exit(main())
