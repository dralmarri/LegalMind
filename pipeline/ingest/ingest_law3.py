#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل القانون رقم 21 لسنة 2015 في شأن حقوق الطفل. 97 مادة (م1-97)، الفرع «جزائي»
(يتضمّن فصل عقوبات يجرّم الاعتداء على الطفل والإخلال بحقوقه؛ ضمن سلسلة التشريعات الجزائية).
النصّ نظيف؛ صُحِّح تلف ترميزيّ لكلمة «أجَّر» (م90) آليًّا بتأكيد السياق، وطُبِّعت الأقواس المنقلبة.
معرّفات: legis-21-2015-m{N} + preamble."""
from __future__ import annotations
import argparse, json, os, re, sys

LAW_ID = "legis-21-2015"
LAW_NO, LAW_YEAR = 21, 2015
LAW_TAG = "حقوق الطفل (21/2015)"
BRANCH = "جزائي"
INSTRUMENT = "القانون رقم 21 لسنة 2015 في شأن حقوق الطفل"
TOPIC = "حقوق الطفل وحمايته"

PREAMBLE = (
    "القانون رقم 21 لسنة 2015 في شأن حقوق الطفل\n"
    "يكفل للطفل (كل من لم يتجاوز الثامنة عشرة) حقوقه الأساسية: الحياة والنسب والجنسية والصحة "
    "والتعليم والرعاية الاجتماعية والثقافية، ويحميه من كافة أشكال العنف والإساءة والإهمال "
    "والاستغلال، وينظّم الحضانة العائلية ورعاية الطفل مجهول الوالدين والطفل ذي الإعاقة والطفل "
    "في نزاع مع القانون، وينشئ آليات الحماية والإبلاغ ولجان حماية الطفولة. ويقرّر في فصل العقوبات "
    "جزاءاتٍ على الاعتداء على الطفل والإخلال بواجبات حمايته. صدر سنة 2015، ويُعمل به بعد ستة أشهر "
    "من نشره."
)


def _label(key):
    m = re.match(r'm(\d+)(-mukarrar)?', key)
    n = m.group(1)
    return f"مادة {n} مكرر" if m.group(2) else f"مادة {n}"


def build_rows(data):
    arts = data["articles"]
    order = data.get("order") or list(arts.keys())
    rows = []

    def meta(extra=None):
        d = {"instrument": INSTRUMENT, "instrument_rank": "قانون", "law_number": LAW_NO,
             "law_year": LAW_YEAR, "upload_origin": "docx_law3_parser"}
        if extra:
            d.update(extra)
        return d

    rows.append({
        "id": f"{LAW_ID}-preamble", "object_type": "legislation_article",
        "branch": BRANCH, "topic": "الديباجة", "subtopic": None, "micro_issue": None,
        "title": f"ديباجة — {LAW_TAG}", "text": PREAMBLE, "meta": meta({"chunk": "preamble"})})

    for key in order:
        a = arts[key]
        body = (a["text"] if isinstance(a, dict) else a).strip()
        mm = re.match(r'm(\d+)(-mukarrar)?', key)
        extra = {"article_number": mm.group(1) + (" مكرر" if mm.group(2) else "")}
        if isinstance(a, dict) and a.get("sec"):
            extra["fasl_raw"] = a["sec"]
        rows.append({
            "id": f"{LAW_ID}-{key}", "object_type": "legislation_article", "branch": BRANCH,
            "topic": TOPIC, "subtopic": None, "micro_issue": None,
            "title": f"{_label(key)} — {LAW_TAG}", "text": body, "meta": meta(extra)})
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

    print("== تقرير القانون 21/2015 (حقوق الطفل) ==")
    print(f"الفرع: {BRANCH} | البادئة: {LAW_ID} | إجمالي الكائنات: {len(rows)}")
    empty = [r["id"] for r in rows if not r["text"].strip()]
    print(f"فارغة: {empty or 'لا'}")
    ids = [r["id"] for r in rows]
    print(f"مكرّرة: {set(i for i in ids if ids.count(i) > 1) or 'لا'}")
    resid = [r["id"] for r in rows if "�" in r["text"]]
    print(f"محارف بديلة �: {resid or 'لا'}")
    for r in rows:
        if r["id"].endswith(("preamble", "-m1", "-m90", "-m97")):
            print(f"\n--- {r['id']} ({r['title']}) ---\n{r['text'][:170]}")

    if args.dry_run:
        print("\n[dry-run] لم يُدخَل شيء."); return 0

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
    print(f"\n✓ أُدخل/حُدّث {ins} كائنًا. شغّل reindex.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
