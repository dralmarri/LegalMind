#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُدخِل القانون رقم 49 لسنة 2016 بشأن المناقصات العامة — 97 مادة + م62 مكرر + ديباجة = 99 كائنًا.

الفرع «إداري»: القانونُ ينظّم الشراءَ العامّ وعقودَه، وم79 منه تُسند منازعاتِه إلى غرفةٍ من غرف
الدائرة الإدارية بالمحكمة الكلية — فهو في صميم القضاء الإداريّ لا المدنيّ.

النصُّ المُدخَل هو **النافذ**: مستبدَلاتُ 74/2019 و1/2024 تحلّ محلّ نصوص 2016، ويُحفَظ الأصلُ
المستبدَل في `metadata.superseded_text_2016` فلا يضيع. والمعدَّلُ جزئيًّا يبقى متنُه الأصليّ
ويُلحَق به الشقُّ المعدَّل تحت عنوانٍ صريح — لا دمجَ تقديريًّا. معرّفات: legis-49-2016-m{N}.
"""
from __future__ import annotations
import argparse, json, os, re, sys

LAW_ID = "legis-49-2016"
BRANCH = "إداري"
TOPIC = "المناقصات العامة والشراء العام — الجهاز المركزي، إجراءات الطرح والترسية، العقد، التظلّم والاختصاص القضائي"
INSTRUMENT = "القانون رقم 49 لسنة 2016 بشأن المناقصات العامة"

PREAMBLE_SUMMARY = (
    "القانون رقم 49 لسنة 2016 بشأن المناقصات العامة: الشريعةُ العامة للشراء العامّ في الكويت، حلّ "
    "محلّ القانون 37/1964 (م94). صدر في 20/7/2016 عن نائب الأمير، ونُشر في الكويت اليوم ع1299 بتاريخ "
    "31/7/2016، ويُعمل به من 31/1/2017 عدا م5 (تشكيل مجلس الجهاز) وم91 (اللائحة التنفيذية) فبأثرٍ فوريّ "
    "من تاريخ النشر (م96). عُدّل بالقانون 74/2019 (م1، م2، م5، م18، م19، م25، م26، م39، م61، م62 "
    "و62 مكرر، م78، م87) وبالقانون 1/2024 (م31 — إلغاءُ اشتراط الجنسية والوكيل المحلّي). وصدر في شأنه "
    "استدراكان: الأوّل (ع1303 ص32) صحّح م36 وم47 ورقمَ القانون الملغى في م94 إلى «37 لسنة 1964»، "
    "والثاني (ع1307، 25/9/2016، ص40) صحّح ترويسة الباب العاشر. "
    "يُنشئ الجهازَ المركزيَّ للمناقصات العامة ومجلسَ إدارته (م4-م8)، ويرسم نطاقَ السريان والاستثناءات "
    "(م2-م3)، وأساليبَ التعاقد: المناقصة العامة والمحدودة والممارسة والأمر المباشر وحدودَها المالية "
    "(م13-م23)، والتسجيلَ والتصنيفَ والتأهيلَ والتظلّمَ من قرار التصنيف أمام لجنة التصنيف (م24-م32)، "
    "والإعلانَ ووثائقَ المناقصة والعطاءاتِ والتأمينَ الأولي (م33-م47)، وفتحَ المظاريف والتقييمَ "
    "والترسيةَ والعدولَ عن التعاقد (م48-م64)، والتأمينَ النهائيَّ وتوقيعَ العقد والتعاقدَ من الباطن "
    "والأوامرَ التغييرية (م65-م76). ويقيم نظامَ التظلّم: الشكوى أمام الجهاز (م77)، والتظلّمُ أمام لجنة "
    "التظلّمات وقرارُها مُلزِم (م78 بصيغة 74/2019)، ثمّ الدعوى أمام غرفةٍ من الدائرة الإدارية بالمحكمة "
    "الكلية ودائرةٍ متخصصةٍ بالاستئناف حكمُها **باتّ** لا يجوز الطعن فيه (م79)، مع إعلانٍ إلكترونيّ "
    "يترتّب البطلانُ على مخالفته (م80) واستثناءاتٍ من قانون المرافعات (م81). ويقرّر منعَ تضارب المصالح "
    "وجزاءَه قابليةُ العقد للإبطال (م82)، ومساءلةَ الموظفين (م83)، والسلوكَ الواجب وبطلانَ كلّ إجراءٍ "
    "مخالف (م84)، وجزاءاتِ المقاولين: الإنذار وتخفيضَ الفئة والحذفَ من السجل (م85). "
    "يتّصل بقانون إنشاء القضاء الإداري 20/1981 (م2 — ولايةُ القضاء الكامل في العقود الإدارية)، "
    "وبالمرافعات 38/1980 (م79/4 — سريانُها تكميليًّا)، وبالمعاملات الإلكترونية 20/2014، وبديوان "
    "المحاسبة 30/1964، وبحماية الأموال العامة 1/1993، والشراكة 116/2014، والاستثمار المباشر 116/2013."
)


def build_rows(data):
    rows = []
    AM = data.get("amendments", {})

    def meta(extra):
        d = {"instrument": INSTRUMENT, "instrument_rank": "قانون", "law_number": 49,
             "law_year": 2016, "gazette": "الكويت اليوم ع1299 — 31/7/2016",
             "in_force_from": "2017-01-31",
             "amended_by": ["74/2019", "1/2024"],
             "corrigenda": ["الكويت اليوم ع1303 ص32", "الكويت اليوم ع1307 — 25/9/2016 ص40"],
             "upload_origin": "pdf_images_visual_transcription+gazette_amendments"}
        d.update(extra); return d

    pre = (PREAMBLE_SUMMARY + "\n\nـــ ديباجة القانون (سند الإصدار) ـــ\n" + data["preamble_text"]
           + "\n\nـــ بيان الإصدار ـــ\n" + data["issuance"])
    rows.append({"id": f"{LAW_ID}-preamble", "topic": "الديباجة",
                 "title": "ديباجة — قانون المناقصات العامة (49/2016)", "text": pre,
                 "meta": meta({"chunk": "preamble"})})

    for k in data["order"]:
        a = data["articles"][k]
        label = ("%d مكرر" % int(a["num"])) if k.endswith("-mukarrar") else str(int(a["num"]))
        extra = {"article_number": label, "bab": a["bab"], "fasl": a["fasl"]}
        if a["title"]:
            extra["article_title"] = a["title"]
        extra.update(AM.get(k, {"amendment_status": "أصلية (2016) — لم يمسّها تعديل",
                                "in_force_source": "2016"}))
        head = "المادة %s" % label + (" — %s" % a["title"] if a["title"] else "")
        rows.append({"id": f"{LAW_ID}-{k}", "topic": TOPIC,
                     "title": f"{head} — قانون المناقصات العامة (49/2016)",
                     "text": a["text"], "meta": meta(extra)})
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
    print("== تقرير قانون المناقصات العامة (49/2016) ==")
    print(f"الفرع: {BRANCH} | البادئة: {LAW_ID} | إجمالي الكائنات: {len(rows)} (متوقَّع 99)")
    assert len(rows) == 99, len(rows)
    blob = " ".join(r["text"] for r in rows)
    print("محارف بديلة �:", "نعم!" if "�" in blob else "لا",
          "| علاماتُ صفحات:", "نعم!" if "⟦" in blob else "لا")
    assert "�" not in blob and "⟦" not in blob
    empty = [r["id"] for r in rows if len(r["text"].strip()) < 40]
    print("فارغة/قصيرة:", empty or "لا"); assert not empty
    ids = [r["id"] for r in rows]
    dup = {i for i in ids if ids.count(i) > 1}; print("مكرّرة:", dup or "لا"); assert not dup
    st = {}
    for r in rows[1:]:
        st[r["meta"]["amendment_status"]] = st.get(r["meta"]["amendment_status"], 0) + 1
    for k, v in sorted(st.items(), key=lambda x: -x[1]):
        print("   %-46s %d" % (k, v))
    sup = [r["id"] for r in rows if "superseded_text_2016" in r["meta"]]
    print("محفوظٌ فيها نصُّ 2016 المستبدَل:", len(sup), "⇐", ", ".join(x.split("-")[-1] for x in sup))
    for r in rows:
        if r["id"].split("-")[-1] in ("preamble", "m2", "m31", "m62", "m79", "m94"):
            print(f"\n--- {r['id']} | {r['meta'].get('amendment_status','')} ---\n{r['text'][:200]}")
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
                   VALUES (%s,'legislation_article',%s,%s,NULL,NULL,%s,%s,%s,NULL,
                           'source_verified','source_authority',TRUE,%s)
                   ON CONFLICT (id) DO UPDATE SET
                    branch=EXCLUDED.branch,topic=EXCLUDED.topic,title=EXCLUDED.title,
                    original_text=EXCLUDED.original_text,normalized_text=EXCLUDED.normalized_text,
                    verification_status='source_verified',usable_as_citation=TRUE,
                    metadata=EXCLUDED.metadata,updated_at=now()""",
                (r["id"], BRANCH, r["topic"], r["title"], r["text"],
                 normalize_text(r["text"]), Jsonb(r["meta"])))
            ins += 1
        conn.commit()
    print(f"\n✓ أُدخل/حُدّث {ins} كائنًا. شغّل reindex.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
