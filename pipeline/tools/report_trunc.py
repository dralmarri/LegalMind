#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تقرير اجتزاع مُنقّح لقانون واحد: يسرد المواد المنتهية في منتصف الجملة مع نهاياتها،
مرتّبةً بالثقة (المنتهية بحرف جرّ/عطف = اجتزاع شبه مؤكَّد). قراءة فقط."""
import os, re, sys

TERM = set('.؛»):!؟"')
# كلمات وظيفية إذا انتهت بها المادة فالاجتزاع شبه مؤكَّد (يجب أن يتلوها كلام)
FUNC = {"في","من","على","الى","عن","او","و","ثم","مع","بعد","قبل","عند","الا","او","بين",
        "هذا","هذه","حكم","اداره","رئيس","كل","اي","التي","الذي","بشان","وفقا","بما","لا",
        "دون","غير","نفس","احد","تلك","ذلك","وان","بان","لان","حتى","اذا","كان","يكون","تكون"}
def _nz(w): return re.sub(r"[أإآ]","ا", w).replace("ة","ه").replace("ى","ي")

def classify(t):
    t = (t or "").strip()
    if not t: return None
    last = t[-1]
    if last in TERM: return None
    if re.search(r"\d\s*[مه]$", t): return None            # تاريخ هجري/ميلادي
    if re.search(r"[.،:]\s*\d+\s*[ء-ي]+$", t): return None  # عنصر قائمة «3 المهر»
    words = re.findall(r"[ء-ي]+", t)
    lastw = _nz(words[-1]) if words else ""
    if lastw in FUNC:
        return "شبه مؤكَّد"
    if last in "،" or ('ء' <= last <= 'ي'):
        return "محتمل"
    return None

def report(rows, pref):
    items = []
    for oid, t in rows:
        if not oid.startswith(pref): continue
        c = classify(t)
        if c: items.append((0 if c=="شبه مؤكَّد" else 1, oid, (t or "").strip()))
    items.sort(key=lambda x:(x[0], x[1]))
    conf = sum(1 for x in items if x[0]==0)
    print(f"== {pref} : مشتبه اجتزاعها = {len(items)} (شبه مؤكَّد: {conf}) ==\n")
    for rank, oid, t in items:
        tag = "★ شبه مؤكَّد" if rank==0 else "  محتمل"
        print(f"[{oid}] {tag}\n   …{t[-95:]!r}\n")

def main():
    pref = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "legis-38-1980"
    if "--local" in sys.argv:
        import json, glob
        PREF={"adm8":"legis-23-1990"}
        rows=[]
        import json
        d=json.load(open("muraf_parsed.json")); a=d["articles"]
        rows=[("legis-38-1980-"+k, a[k]) for k in d["order"]]
    else:
        import psycopg
        dsn=os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
        with psycopg.connect(dsn) as conn, conn.cursor() as cur:
            cur.execute("select id, coalesce(original_text,'') from knowledge_objects where id like %s", (pref+"-%",))
            rows=cur.fetchall()
    report(rows, pref)

if __name__ == "__main__":
    main()
