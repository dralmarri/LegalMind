#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل المرسوم لسنة 1979 بشأن نظام الخدمة المدنية (اللائحة التنفيذية للمرسوم بالقانون 15/1979).
94 مادة + عناقيد «مكرر» (م30) في عشرة أقسام. معرّفات: legis-nsm-1979-m{key} + preamble.
النوع legislation_article، الفرع «إداري»."""
from __future__ import annotations
import argparse, json, os, re, sys

LAW_ID   = "legis-nsm-1979"
LAW_TAG  = "نظام الخدمة المدنية (مرسوم 1979)"
BRANCH   = "إداري"
INSTRUMENT = "المرسوم الصادر في 4 أبريل 1979 بنظام الخدمة المدنية (اللائحة التنفيذية للمرسوم بالقانون 15/1979)"

PREAMBLE = (
    "المرسوم لسنة 1979 بشأن نظام الخدمة المدنية\n"
    "اللائحة التنفيذية للمرسوم بالقانون رقم 15 لسنة 1979 في شأن الخدمة المدنية، الصادر في "
    "7 جمادى الأولى 1399هـ الموافق 4 أبريل 1979م. ينظّم قواعد التعيين وتقييم الكفاءة "
    "والعلاوات والترقية ولجنة شؤون الموظفين والنقل والندب والإعارة والإجازات والتأديب "
    "وانتهاء الخدمة والأحكام العامة للموظفين الخاضعين لقانون الخدمة المدنية."
)

_DISTNAME = {"1": "مكرر ١", "2": "مكرر ٢", "3": "مكرر ٣",
             "b": "مكرر ب", "c": "مكرر ج", "d": "مكرر د"}

def _label(key):
    m = re.match(r"m(\d+)(mkr)([0-9a-z]*)?$", key)
    if m:
        base = m.group(1)
        suf = m.group(3) or ""
        return base + " " + _DISTNAME.get(suf, "مكرر")
    return re.match(r"m(\d+)", key).group(1)


def build_rows(data):
    arts = data["articles"]
    order = data.get("order") or list(arts.keys())
    rows = []

    def meta(extra=None):
        m = {"instrument": INSTRUMENT, "instrument_rank": "مرسوم (لائحة تنفيذية)",
             "parent_law": "legis-15-1979", "law_year": 1979,
             "upload_origin": "docx_clean_textlayer"}
        if extra:
            m.update(extra)
        return m

    rows.append({
        "id": f"{LAW_ID}-preamble", "object_type": "legislation_article",
        "branch": BRANCH, "topic": "الديباجة", "subtopic": None, "micro_issue": None,
        "title": f"ديباجة — {LAW_TAG}",
        "text": PREAMBLE,
        "meta": meta({"chunk": "preamble"})})

    for key in order:
        a = arts[key]
        sec = (a.get("bab") or "").strip() or "أحكام عامة"
        rows.append({
            "id": f"{LAW_ID}-{key}", "object_type": "legislation_article",
            "branch": BRANCH, "topic": sec, "subtopic": None, "micro_issue": None,
            "title": f"مادة {_label(key)} — {LAW_TAG}",
            "text": a["text"].strip(),
            "meta": meta({"article_number": _label(key), "section": sec})})
    return rows


def normalize_text(text):
    try:
        sys.path.insert(0, "/opt/LegalMind/engine")
        from normalizer.canonical import normalize_text as nt
        return nt(text)
    except Exception:
        import unicodedata
        t = unicodedata.normalize("NFKC", text).replace("ـ", "")
        t = re.sub(r"[ \t]+", " ", t); t = re.sub(r" *\n *", "\n", t)
        return re.sub(r"\n{3,}", "\n\n", t).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    data = json.load(open(args.json, encoding="utf-8"))
    rows = build_rows(data)

    from collections import OrderedDict
    bysec = OrderedDict()
    for r in rows:
        if r["meta"].get("chunk") == "preamble":
            continue
        bysec.setdefault(r["topic"], []).append(r["meta"]["article_number"])
    print("== تقرير نظام الخدمة المدنية (مرسوم 1979) ==")
    print(f"الأداة: {INSTRUMENT}")
    print(f"الفرع: {BRANCH}  | البادئة: {LAW_ID}")
    print(f"إجمالي الكائنات: {len(rows)}  (مواد: {len(rows)-1} + ديباجة)")
    for s in bysec:
        ks = bysec[s]
        print(f"  {s} [{len(ks)}]: {ks[0]}..{ks[-1]}")
    empty = [r["id"] for r in rows if not r["text"].strip()]
    print(f"كائنات فارغة: {empty or 'لا'}")
    ids = [r["id"] for r in rows]
    print(f"معرّفات مكرّرة: { {i for i in ids if ids.count(i)>1} or 'لا'}")
    for r in (rows[1], rows[len(rows)//2], rows[-1]):
        print(f"\n--- {r['id']} (topic={r['topic']}) ---\n{r['text'][:150]}")

    if args.dry_run:
        print("\n[dry-run] لم يُدخَل شيء.")
        return 0

    import psycopg
    from psycopg.types.json import Jsonb
    dsn = os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
    ins = 0
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        for r in rows:
            cur.execute(
                """INSERT INTO knowledge_objects
                   (id,object_type,branch,topic,subtopic,micro_issue,title,original_text,normalized_text,
                    source_key,verification_status,authority_status,usable_as_citation,metadata)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL,'source_verified','source_authority',TRUE,%s)
                   ON CONFLICT (id) DO UPDATE SET
                    object_type=EXCLUDED.object_type,branch=EXCLUDED.branch,topic=EXCLUDED.topic,
                    subtopic=EXCLUDED.subtopic,micro_issue=EXCLUDED.micro_issue,title=EXCLUDED.title,
                    original_text=EXCLUDED.original_text,normalized_text=EXCLUDED.normalized_text,
                    verification_status='source_verified',usable_as_citation=TRUE,
                    metadata=EXCLUDED.metadata,updated_at=now()""",
                (r["id"], r["object_type"], r["branch"], r["topic"], r["subtopic"], r["micro_issue"],
                 r["title"], r["text"], normalize_text(r["text"]), Jsonb(r["meta"])))
            ins += 1
        conn.commit()
    print(f"\n✓ أُدخل/حُدّث {ins} كائنًا. شغّل الآن: reindex")
    return 0


if __name__ == "__main__":
    sys.exit(main())
