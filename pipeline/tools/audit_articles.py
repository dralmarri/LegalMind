#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""فحص سلامة نصوص مواد التشريع في القاعدة: يكشف المواد المجتزأة/الملوّثة بالشوائب.
قراءة فقط — لا يغيّر البيانات. يطبع تقريرًا لكل قانون + عيّنات من المواد المشبوهة."""
import re, os, sys, argparse, json, glob

import re as _re
TERM = set('.؛»):!؟"')            # علامات نهاية مقبولة (بلا الفاصلة العادية «،»)
JUNK = (")))", "(((", "�")
SIG = ("امير الكويت", "صدر بقصر", "صدر في", "الموافق", "رئيس مجلس الوزراء", "نائب امير", "وزير العدل")
def _nz(t): return _re.sub(r'[أإآ]','ا',t).replace('ة','ه')

def flags(oid, text):
    f = []
    t = (text or "").strip()
    if not t:
        return ["فارغ"]
    if any(j in t for j in JUNK):
        f.append("شوائب")
    if len(t) < 30 and "ملغا" not in t:
        f.append("قصير-جدًّا")
    is_sig = ("iss" in oid) or any(_nz(s) in _nz(t) for s in SIG)
    date_end = bool(_re.search(r'\d\s*[مه]$', t))
    if (not is_sig) and (not date_end) and (t[-1] not in TERM):
        f.append("اجتزاع؟")
    return f

def audit(rows):
    laws = {}
    for oid, text in rows:
        m = re.match(r"(legis-[^-]+-\d+)", oid) or re.match(r"(legis-\d+-\d+)", oid)
        pre = m.group(1) if m else "?"
        laws.setdefault(pre, []).append((oid, text or ""))
    print(f"{'القانون':<22}{'مواد':>6}{'مجتزأ؟':>8}{'شوائب':>8}{'قصير':>7}{'مِن':>7}{'وسطي':>7}{'إلى':>7}")
    total_flag = {}
    worst = []
    for pre in sorted(laws):
        arts = laws[pre]
        lens = [len(t.strip()) for _, t in arts]
        cj = ct = cs = 0
        for oid, t in arts:
            fl = flags(oid, t)
            if "شوائب" in fl: cj += 1
            if "اجتزاع؟" in fl: ct += 1; worst.append((oid, t))
            if "قصير-جدًّا" in fl: cs += 1
        total_flag[pre] = (ct, cj, cs)
        print(f"{pre:<22}{len(arts):>6}{ct:>8}{cj:>8}{cs:>7}{min(lens):>7}{sum(lens)//len(lens):>7}{max(lens):>7}")
    print(f"\nإجمالي: مواد مجتزأة محتملة = {sum(v[0] for v in total_flag.values())} | ملوّثة بالشوائب = {sum(v[1] for v in total_flag.values())}")
    print("\n=== عيّنات من المواد المجتزأة المحتملة (أوّل 12) ===")
    for oid, t in worst[:12]:
        ts = t.strip()
        print(f"\n[{oid}] (طول {len(ts)}) ينتهي بـ: …{ts[-45:]!r}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", action="store_true")
    ap.add_argument("--id", help="اطبع النصّ الكامل لمعرّف واحد")
    args = ap.parse_args()
    if args.local:
        PREF = {"adm8":"legis-23-1990","adm10":"legis-10-2020","adm11":"legis-42-1964","adm12":"legis-40-1980"}
        rows = []
        for f in glob.glob("*_parsed.json"):
            pre = PREF.get(f.replace("_parsed.json",""))
            if not pre: continue
            d = json.load(open(f, encoding="utf-8")); a = d["articles"]
            for k in d.get("order", list(a)):
                rows.append((f"{pre}-{k}", a[k]["text"] if isinstance(a[k], dict) else a[k]))
        audit(rows); return
    import psycopg
    dsn = os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        if args.id:
            cur.execute("select id, original_text from knowledge_objects where id=%s", (args.id,))
            r = cur.fetchone()
            print(f"=== {r[0]} (طول {len(r[1] or '')}) ===\n{r[1]}"); return
        cur.execute("select id, coalesce(original_text,'') from knowledge_objects where object_type in ('legislation_article','legislation_issuing_article') or id like 'legis-%'")
        rows = cur.fetchall()
    audit(rows)

if __name__ == "__main__":
    main()
