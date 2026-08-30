#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل اللائحة التنفيذية لقانون مكافحة غسل الأموال (القرار الوزاري 37/2013). 26 مادة + ديباجة،
الفرع «جزائي» (لاحقة لـ 106/2013). منقولة بصريًّا من صور PDF رسمية. معرّفات: regl-106-2013-m{N}."""
from __future__ import annotations
import argparse, json, os, re, sys

LAW_ID = "regl-106-2013"
LAW_TAG = "اللائحة التنفيذية لمكافحة غسل الأموال (قرار وزاري 37/2013)"
BRANCH = "جزائي"
INSTRUMENT = "القرار الوزاري رقم 37 لسنة 2013 بإصدار اللائحة التنفيذية لقانون مكافحة غسل الأموال وتمويل الإرهاب رقم 106 لسنة 2013"
TOPIC = "اللائحة التنفيذية لغسل الأموال — العناية الواجبة والإخطار والرقابة واللجنة الوطنية"


def build_rows(data):
    arts, order = data["articles"], data.get("order") or list(data["articles"])
    rows = []

    def meta(extra=None):
        d = {"instrument": INSTRUMENT, "instrument_rank": "قرار وزاري (لائحة تنفيذية)",
             "law_number": 37, "law_year": 2013, "implements": "legis-106-2013",
             "upload_origin": "image_pdf_amlreg_transcription"}
        if extra: d.update(extra)
        return d

    rows.append({"id": f"{LAW_ID}-preamble", "object_type": "legislation_article", "branch": BRANCH,
                 "topic": "الديباجة", "subtopic": None, "micro_issue": None,
                 "title": f"ديباجة — {LAW_TAG}", "text": data["preamble_text"], "meta": meta({"chunk": "preamble"})})
    for key in order:
        a = arts[key]; mm = re.match(r'm(\d+)', key)
        extra = {"article_number": mm.group(1)}
        if a.get("sec"): extra["fasl_raw"] = a["sec"]
        rows.append({"id": f"{LAW_ID}-{key}", "object_type": "legislation_article", "branch": BRANCH,
                     "topic": TOPIC, "subtopic": None, "micro_issue": None,
                     "title": f"مادة {mm.group(1)} — {LAW_TAG}", "text": a["text"].strip(), "meta": meta(extra)})
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
    ap = argparse.ArgumentParser(); ap.add_argument("json"); ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    data = json.load(open(args.json, encoding="utf-8"))
    rows = build_rows(data)
    print("== تقرير اللائحة التنفيذية لغسل الأموال (37/2013) ==")
    print(f"الفرع: {BRANCH} | البادئة: {LAW_ID} | الكائنات: {len(rows)}")
    print("فارغة:", [r["id"] for r in rows if not r["text"].strip()] or "لا")
    print("محارف بديلة �:", [r["id"] for r in rows if "�" in r["text"]] or "لا")
    for r in rows:
        if r["id"].endswith(("preamble", "-m6", "-m7", "-m16", "-m19")):
            print(f"\n--- {r['id']} ---\n{r['text'][:140]}")
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
                   ON CONFLICT (id) DO UPDATE SET object_type=EXCLUDED.object_type,branch=EXCLUDED.branch,
                    topic=EXCLUDED.topic,title=EXCLUDED.title,original_text=EXCLUDED.original_text,
                    normalized_text=EXCLUDED.normalized_text,verification_status='source_verified',
                    usable_as_citation=TRUE,metadata=EXCLUDED.metadata,updated_at=now()""",
                (r["id"], r["object_type"], r["branch"], r["topic"], r["subtopic"], r["micro_issue"],
                 r["title"], r["text"], normalize_text(r["text"]), Jsonb(r["meta"])))
            ins += 1
        conn.commit()
    print(f"\n✓ أُدخل/حُدّث {ins} كائنًا. شغّل reindex.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
