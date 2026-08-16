#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يستخرج «رسم علاقات الديباجات» من كائنات الديباجة في القاعدة: لكلّ قانونٍ، القوانينُ التي يستند
إليها في ديباجته («بعد الاطلاع على… وعلى القانون رقم N لسنة Y…»)، ثنائيَّ الاتجاه (يستند / يُستنَد إليه).
يستبعد الإطار الشكليّ العامّ (الدستور/المدني/المرافعات/التجارة…) من طبقة «العلاقات الموضوعية».
يحفظ الناتج في /opt/LegalMind/admin/preamble_xref.json. قراءةٌ فقط للقاعدة، لا تعديل بيانات."""
import json, os, re, sys

DSN = os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
# قوانين الإطار الشكليّ العامّ — تُذكَر في كل ديباجة تقريبًا بلا صلةٍ موضوعيةٍ خاصّة:
_FORMAL = {"67/1980", "68/1980", "38/1980", "5/1981", "12/1963", "30/1964", "4/1977",
           "84/2024", "23/1990", "20/1981"}
_AR = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_REF = re.compile(r"(?:القانون|المرسوم بقانون|مرسوم بقانون|قانون)\s+رقم\s*\(?\s*([٠-٩0-9]{1,4})\s*\)?\s*لسنة\s*([٠-٩0-9]{4})")


def norm(n, y):
    return "%s/%s" % (n.translate(_AR), y.translate(_AR))


def self_of(oid):
    m = re.match(r"(?:legis|regl)-(\d+)-(\d+)-", oid)
    return "%s/%s" % (m.group(1), m.group(2)) if m else None


def main():
    import psycopg
    cites, titles = {}, {}
    with psycopg.connect(DSN) as c, c.cursor() as cur:
        cur.execute("""SELECT id,title,original_text FROM knowledge_objects
                       WHERE (id LIKE '%%-preamble' OR id LIKE '%%-iss1' OR topic='الديباجة'
                              OR (metadata->>'chunk')='preamble') AND original_text IS NOT NULL""")
        rows = cur.fetchall()
    for oid, title, txt in rows:
        sid = self_of(oid)
        if not sid:
            continue
        titles.setdefault(sid, (title or "").replace("ديباجة — ", "").strip())
        refs = {norm(n, y) for n, y in _REF.findall(txt)} - {sid}
        cites.setdefault(sid, set()).update(refs)

    # bidirectional graph + subject-only (formal filtered) layer
    graph = {}
    for law, outs in cites.items():
        graph.setdefault(law, {"title": titles.get(law, ""), "cites": [], "cited_by": [], "subject_links": []})
        graph[law]["cites"] = sorted(outs, key=lambda s: (int(s.split("/")[1]), int(s.split("/")[0])))
    for law, outs in cites.items():
        for t in outs:
            graph.setdefault(t, {"title": titles.get(t, ""), "cites": [], "cited_by": [], "subject_links": []})
            graph[t]["cited_by"].append(law)
    for law, g in graph.items():
        g["cited_by"] = sorted(set(g["cited_by"]), key=lambda s: (int(s.split("/")[1]), int(s.split("/")[0])))
        g["subject_links"] = [x for x in g["cites"] if x not in _FORMAL]

    out = "/opt/LegalMind/admin/preamble_xref.json"
    json.dump({"generated_from": "preambles", "laws": graph}, open(out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("== رسم علاقات الديباجات ==")
    print("قوانين لها ديباجة مُحلَّلة:", len([l for l, g in graph.items() if g["cites"]]))
    print("إجماليّ العُقد (قوانين مذكورة أو ذاكرة):", len(graph))
    print("حُفِظ في:", out)
    # print the richest few
    for law, g in sorted(graph.items(), key=lambda kv: -len(kv[1]["cites"]))[:6]:
        if g["cites"]:
            print(f"\n● {law} — {g['title'][:44]}")
            print("   الجرائم/العلاقات الموضوعية:", "، ".join(g["subject_links"]) or "—")
            print("   يُستنَد إليه في:", "، ".join(g["cited_by"]) or "—")
    return 0


if __name__ == "__main__":
    sys.exit(main())
