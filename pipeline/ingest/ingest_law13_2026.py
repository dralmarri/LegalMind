#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل المرسوم بقانون رقم 13 لسنة 2026 بشأن تأمين وحماية المصالح العليا للجهات العسكرية. 34 مادة +
6 فصول + ديباجة، الفرع «جزائي». نصٌّ نظيفٌ من DOCX (أقواسٌ معكوسةٌ حول أرقام + «__» صُوّبت) ومُتحقَّقٌ من
صور الجريدة. معرّفات: legis-13-2026-m{N} / -preamble."""
from __future__ import annotations
import argparse, json, os, re, sys
LAW_ID = "legis-13-2026"; BRANCH = "جزائي"
TOPIC = "تأمين وحماية المصالح العليا للجهات العسكرية — التأمين والمناطق المحمية والأسرار والعقوبات"
INSTRUMENT = "المرسوم بقانون رقم 13 لسنة 2026 بشأن تأمين وحماية المصالح العليا للجهات العسكرية"
PREAMBLE_SUMMARY = (
    "المرسوم بقانون رقم 13 لسنة 2026 بشأن تأمين وحماية المصالح العليا للجهات العسكرية (الجيش والشرطة "
    "والحرس الوطني): يعرّف السلطةَ المختصة (وزير الدفاع/الداخلية/رئيس الحرس الوطني) والمصالحَ العليا "
    "والمناطقَ المحمية والتنقلاتِ والمواكب والأرتال العسكرية والنشاطَ المعادي وأوضاعَ عدم العادية (م1). "
    "ينظّم طبيعةَ التأمين (منع التهديد والاعتداء والإضرار وإضعاف الروح المعنوية — م2-م5 ومنها سرية الوثائق "
    "العسكرية)، والتحركاتِ والتنقلاتِ العسكرية والتنسيق مع المرور وإطلاقَ النار (م6-م8)، وإجراءاتِ التأمين "
    "والحماية والمناطقَ المحمية ونقاطَ التفتيش والضبط العسكريّ (م9-م24). العقوبات في الفصل الخامس (م25-م32): "
    "تجرّم الاعتداء على الجهات العسكرية وإفشاءَ الأسرار والتصويرَ والتخابرَ والنشاطَ المعادي بعقوباتٍ مشدَّدة. "
    "يتّصل بقانون الجزاء 16/1960 والإجراءات 17/1960 والجيش 32/1967 والتعبئة العامة 65/1980 والدفاع المدني "
    "21/1979 وجرائم تقنية المعلومات 63/2015 وتنظيم القضاء 23/1990. صدر سنة 2026."
)
def build_rows(data):
    rows = []; secs = data.get("sections", {})
    def meta(extra):
        d = {"instrument": INSTRUMENT, "instrument_rank": "مرسوم بقانون", "law_number": 13,
             "law_year": 2026, "upload_origin": "docx_law13_2026_gazette_verified"}
        d.update(extra); return d
    pre = PREAMBLE_SUMMARY + "\n\nـــ ديباجة المرسوم بقانون (سند الإصدار) ـــ\n" + (data.get("preamble_text") or "")
    rows.append({"id": f"{LAW_ID}-preamble", "topic": "الديباجة",
                 "title": "ديباجة — تأمين وحماية المصالح العليا للجهات العسكرية (13/2026)", "text": pre,
                 "meta": meta({"chunk": "preamble"})})
    for k in data["order"]:
        extra = {"article_number": k[1:]}
        if secs.get(k): extra["fasl_raw"] = secs[k]
        rows.append({"id": f"{LAW_ID}-{k}", "topic": TOPIC,
                     "title": f"المادة {k[1:]} — تأمين المصالح العليا للجهات العسكرية (13/2026)",
                     "text": data["articles"][k], "meta": meta(extra)})
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
    args = ap.parse_args(); data = json.load(open(args.json, encoding="utf-8")); rows = build_rows(data)
    print("== تأمين المصالح العليا للجهات العسكرية (13/2026) =="); print(f"الفرع: {BRANCH} | البادئة: {LAW_ID} | كائنات: {len(rows)}")
    blob = " ".join(r["text"] for r in rows); print("� :", "نعم!" if "�" in blob else "لا")
    ids = [r["id"] for r in rows]; print("مكرّرة:", set(i for i in ids if ids.count(i) > 1) or "لا")
    for r in rows:
        if r["id"].endswith(("preamble", "m1", "m25")): print(f"\n--- {r['id']} ---\n{r['text'][:130]}")
    if args.dry_run: print("\n[dry-run]"); return 0
    import psycopg
    from psycopg.types.json import Jsonb
    dsn = os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
    ins = 0
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        for r in rows:
            cur.execute("""INSERT INTO knowledge_objects
                   (id,object_type,branch,topic,subtopic,micro_issue,title,original_text,normalized_text,
                    source_key,verification_status,authority_status,usable_as_citation,metadata)
                   VALUES (%s,'legislation_article',%s,%s,NULL,NULL,%s,%s,%s,NULL,'source_verified','source_authority',TRUE,%s)
                   ON CONFLICT (id) DO UPDATE SET branch=EXCLUDED.branch,topic=EXCLUDED.topic,title=EXCLUDED.title,
                    original_text=EXCLUDED.original_text,normalized_text=EXCLUDED.normalized_text,
                    verification_status='source_verified',usable_as_citation=TRUE,metadata=EXCLUDED.metadata,updated_at=now()""",
                (r["id"], BRANCH, r["topic"], r["title"], r["text"], normalize_text(r["text"]), Jsonb(r["meta"])))
            ins += 1
        conn.commit()
    print(f"\n✓ أُدخل/حُدّث {ins} كائنًا. شغّل reindex."); return 0
if __name__ == "__main__": sys.exit(main())
