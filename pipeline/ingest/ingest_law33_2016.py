#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل القانون رقم 33 لسنة 2016 بشأن بلدية الكويت. 53 مادة + ديباجة، أربعةُ أبواب، الفرع «إداري»
(تنظيمٌ إداريٌّ بلديّ: البلدية والمجلس البلدي والجهاز التنفيذي واختصاصاتهما، والتراخيص، والمخالفات
والعقوبات). نصٌّ منقولٌ برمجيًّا من DOCX نظيفٍ ومُصوَّبٍ من تلفٍ حتميّ. معرّفات: legis-33-2016-m{N}."""
from __future__ import annotations
import argparse, json, os, re, sys

LAW_ID = "legis-33-2016"
BRANCH = "إداري"
TOPIC = "بلدية الكويت — المجلس البلدي والجهاز التنفيذي والاختصاصات والتراخيص والمخالفات"
INSTRUMENT = "القانون رقم 33 لسنة 2016 بشأن بلدية الكويت"

PREAMBLE_SUMMARY = (
    "القانون رقم 33 لسنة 2016 بشأن بلدية الكويت: ينظّم بلديةَ الكويت باعتبارها هيئةً عامةً مستقلةً ذات "
    "شخصيةٍ اعتبارية تخضع لإشراف الوزير المختص، وتتكوّن من المجلس البلدي والجهاز التنفيذي (م1-م3). الباب "
    "الأول (م4-م30): المجلس البلدي — تكوينه وعضويته وانتخاب أعضائه والتعيين وشروط العضوية وإسقاطها "
    "ونظام جلساته واختصاصاته (التخطيط العمراني، تقسيم المناطق، اشتراطات البناء، الأملاك العامة، الإعلانات، "
    "المحال). الباب الثاني (م31-م37): الجهاز التنفيذي — المدير العام واختصاصاته وإصدار التراخيص وتنفيذ "
    "قرارات المجلس. الباب الثالث (م38-م44): المخالفات والعقوبات — الغرامات وإزالة المخالفات على نفقة "
    "المخالف والتنفيذ الإداري والتظلّم. الباب الرابع (م45-م53): أحكام ختامية — التراخيص القائمة وأملاك "
    "الدولة واللائحة التنفيذية والإلغاء. صدر مستنِدًا إلى الدستور وقوانينَ عديدة (نزع الملكية 33/1964، "
    "أنظمة السلامة 18/1978، الخدمة المدنية 15/1979، أملاك الدولة 105/1980، التنظيم الإداري 116/1992 وغيرها). "
    "صدر في 4 يوليو 2016، ويختصّ بتنفيذه رئيس مجلس الوزراء والوزراء."
)


def build_rows(data):
    rows = []
    secs = data.get("sections", {})

    def meta(extra):
        d = {"instrument": INSTRUMENT, "instrument_rank": "قانون", "law_number": 33,
             "law_year": 2016, "upload_origin": "docx_law33_2016_autocleaned"}
        d.update(extra); return d

    pre = PREAMBLE_SUMMARY + "\n\nـــ ديباجة القانون (سند الإصدار) ـــ\n" + (data.get("preamble_text") or "") + \
        (("  " + data["issue_tail"]) if data.get("issue_tail") else "")
    rows.append({"id": f"{LAW_ID}-preamble", "topic": "الديباجة", "sub": None,
                 "title": "ديباجة — قانون بلدية الكويت (33/2016)", "text": pre,
                 "meta": meta({"chunk": "preamble"})})
    for k in data["order"]:
        num = re.match(r"m(\d+)", k).group(1)
        sec = secs.get(k, "") or None
        rows.append({"id": f"{LAW_ID}-{k}", "topic": TOPIC, "sub": sec,
                     "title": f"المادة {num} — قانون بلدية الكويت (33/2016)" + (f" [{sec}]" if sec else ""),
                     "text": data["articles"][k], "meta": meta({"article_number": num, "section": sec or ""})})
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
    print("== تقرير قانون بلدية الكويت (33/2016) ==")
    print(f"الفرع: {BRANCH} | البادئة: {LAW_ID} | إجمالي الكائنات: {len(rows)}")
    blob = " ".join(r["text"] for r in rows)
    print("محارف بديلة �:", "نعم!" if "�" in blob else "لا", "| شرطات _:", blob.count("_"))
    empty = [r["id"] for r in rows if not r["text"].strip()]
    print("فارغة:", empty or "لا")
    ids = [r["id"] for r in rows]; print("مكرّرة:", set(i for i in ids if ids.count(i) > 1) or "لا")
    for r in rows:
        if r["id"].endswith(("preamble", "m1", "m38", "m53")):
            print(f"\n--- {r['id']} (قسم={r['sub']}) ---\n{r['text'][:130]}")
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
                   VALUES (%s,'legislation_article',%s,%s,%s,NULL,%s,%s,%s,NULL,
                           'source_verified','source_authority',TRUE,%s)
                   ON CONFLICT (id) DO UPDATE SET
                    branch=EXCLUDED.branch,topic=EXCLUDED.topic,subtopic=EXCLUDED.subtopic,title=EXCLUDED.title,
                    original_text=EXCLUDED.original_text,normalized_text=EXCLUDED.normalized_text,
                    verification_status='source_verified',usable_as_citation=TRUE,
                    metadata=EXCLUDED.metadata,updated_at=now()""",
                (r["id"], BRANCH, r["topic"], r["sub"], r["title"], r["text"],
                 normalize_text(r["text"]), Jsonb(r["meta"])))
            ins += 1
        conn.commit()
    print(f"\n✓ أُدخل/حُدّث {ins} كائنًا. شغّل reindex.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
