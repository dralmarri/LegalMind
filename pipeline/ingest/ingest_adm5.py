#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل الأمر الأميري بالقانون رقم 61 لسنة 1976 بإصدار قانون التأمينات الاجتماعية.
7 مواد إصدار + القانون المرافق (132 مادة + 15 مكرر) في تسعة أبواب.
معرّفات: legis-61-1976-{key} (issN لمواد الإصدار) + preamble. الفرع «إداري»."""
from __future__ import annotations
import argparse, json, os, re, sys

LAW_ID   = "legis-61-1976"
LAW_TAG  = "قانون التأمينات الاجتماعية (61/1976)"
BRANCH   = "إداري"
INSTRUMENT = "الأمر الأميري بالقانون رقم 61 لسنة 1976 بإصدار قانون التأمينات الاجتماعية"

PREAMBLE = (
    "الأمر الأميري بالقانون رقم 61 لسنة 1976 بإصدار قانون التأمينات الاجتماعية\n"
    "نحن صباح السالم الصباح أمير الكويت، بعد الاطلاع على الدستور، وعلى المرسوم الأميري رقم "
    "3 لسنة 1960 بقانون معاشات ومكافآت التقاعد للموظفين المدنيين، والقانون رقم 18 لسنة 1960 "
    "بشأن العمل في القطاع الحكومي، وقانون معاشات ومكافآت التقاعد للعسكريين، وغيرها، أمرنا "
    "بالقانون الآتي نصه. ينشئ القانون المؤسسة العامة للتأمينات الاجتماعية وينظّم تأمين "
    "الشيخوخة والعجز والمرض والوفاة وإصابات العمل والمعاشات والمكافآت والاستبدال."
)

_DISTNAME = {"a": "(أ)", "b": "(ب)", "c": "(ج)", "d": "(د)",
             "1": "١", "2": "٢", "3": "٣"}

def _label(key):
    m = re.match(r"iss(\d+)$", key)
    if m:
        return "مادة إصدار " + m.group(1)
    m = re.match(r"m(\d+)mkr([0-9a-z]*)$", key)
    if m:
        suf = m.group(2) or ""
        return m.group(1) + " مكرر" + ((" " + _DISTNAME.get(suf, suf)) if suf else "")
    return re.match(r"m(\d+)", key).group(1)


def build_rows(data):
    arts = data["articles"]
    order = data.get("order") or list(arts.keys())
    rows = []

    def meta(extra=None):
        m = {"instrument": INSTRUMENT, "instrument_rank": "قانون (أمر أميري)",
             "law_number": 61, "law_year": 1976, "upload_origin": "docx_clean_textlayer"}
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
        is_iss = key.startswith("iss")
        otype = "legislation_issuing_article" if is_iss else "legislation_article"
        if is_iss:
            topic, sub = "مواد الإصدار", None
        else:
            topic = (a.get("bab") or "").strip() or "أحكام عامة"
            sub = (a.get("fasl") or None)
        rows.append({
            "id": f"{LAW_ID}-{key}", "object_type": otype,
            "branch": BRANCH, "topic": topic, "subtopic": sub, "micro_issue": None,
            "title": f"مادة {_label(key)} — {LAW_TAG}",
            "text": a["text"].strip(),
            "meta": meta({"article_number": _label(key), "bab": a.get("bab"),
                          "fasl": a.get("fasl"), "issuing": is_iss})})
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
    bybab = OrderedDict()
    for r in rows:
        if r["meta"].get("chunk") == "preamble":
            continue
        bybab.setdefault(r["topic"], []).append(r["meta"]["article_number"])
    n_iss = sum(1 for r in rows if r["object_type"] == "legislation_issuing_article")
    print("== تقرير قانون التأمينات الاجتماعية (61/1976) ==")
    print(f"الأداة: {INSTRUMENT}")
    print(f"الفرع: {BRANCH}  | البادئة: {LAW_ID}")
    print(f"إجمالي الكائنات: {len(rows)}  (إصدار: {n_iss} | مواد القانون: {len(rows)-1-n_iss} | ديباجة)")
    for b in bybab:
        ks = bybab[b]
        print(f"  {b[:60]} [{len(ks)}]: {ks[0]}..{ks[-1]}")
    empty = [r["id"] for r in rows if not r["text"].strip()]
    print(f"كائنات فارغة: {empty or 'لا'}")
    ids = [r["id"] for r in rows]
    print(f"معرّفات مكرّرة: { {i for i in ids if ids.count(i)>1} or 'لا'}")
    for r in (rows[8], rows[len(rows)//2], rows[-1]):
        print(f"\n--- {r['id']} ({r['object_type']}; topic={r['topic'][:30]}) ---\n{r['text'][:140]}")

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
