#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تصحيح النفاذ المؤجَّل للمرسوم بقانون 91/2026 + وسم البطاقات المؤجَّلة (2026-10-09).

العلّة (اكتُشفت اليوم عند طلب المالك ضمّ 91/2026 لقانون أسواق المال): المرسوم بقانون
91/2026 «يعمل به اعتباراً من تاريخ العمل بالمرسوم بقانون رقم (88) لسنة 2026»
(legis-91-2026-issue-4)، و88/2026 «يعمل به من تاريخ 1/10/2027» (legis-88-2026-issuing-m7).
لكن دفعة العدد 1809 (2026-09-20) طبّقت تعديلاته على 7/2010 فورًا — قبل أن تُرسى قاعدة
النفاذ المؤجَّل في §14 (2026-09-27) — فصارت القاعدة تعرض تعريفَي م1 الجديدين نصًّا نافذًا،
وم2 بعبارة «الوزير المختص»، **وتمنع الاستشهاد بالمواد 108–113 و116 وهي نافذة حتى 2027/10/1**.
وهذا بالضبط ما تحذّر منه §14: «الاستبدال المبكّر يُخفي نفسه».

العلاج — قاعدة §14 حرفيًا، والهدف يُكتشف من البيانات لا من قائمة:
  • المواد المعدَّلة (كل صف في 7/2010 له نسخة سابقة سندها 91/2026): المتن يعود للنص
    النافذ اليوم (المحفوظ في previous_versions) ويُلحق به النص القادم في كتلة موسومة،
    والعنوان يحمل التاريخ، والنص المعدَّل كاملًا في pending_amendment — لا يضيع حرف.
  • المواد الملغاة إلغاءً مؤجَّلًا (repeal_instrument = legis-91-2026-issue-3): تعود قابلة
    للاستشهاد بحالة التحقق الغالبة على شقيقاتها النافذة (من البيانات)، وتُلحق بها كتلة
    «إلغاءٌ مُعلَّق»، وتنتقل مفاتيح الإلغاء إلى pending_repeal.
  • ملاحظتا م114 وم130 المرجعيتان: يُلحق بهما تنبيه التاريخ (لا يُمحى منهما شيء).
  • بأمر المالك («يجب أن تشير في البطاقة أنه مؤجَّل»): بطاقات الصكوك المؤجَّلة وعناوين
    كائناتها تحمل تاريخ العمل بها — 88/2026 و91/2026 و94/2026؛ وبطاقة 10/2026 تحمل
    قاعدة نفاذها (بعد شهر من نشر لائحته التنفيذية) دون ادعاء نفاذها أو عدمه.
  • بأمر المالك: بطاقة 90/2026 اسمها «قانون الصكوك الحكومية».

الحُرّاس — معاملة واحدة، وأي فشل ⇒ ROLLED_BACK بلا أثر:
  • مصدر التاريخ يُقرأ من القاعدة: نص legis-88-2026-issuing-m7 يجب أن يحمل «1/10/2027»
    ونص legis-91-2026-issue-4 يجب أن يحيل إلى 88/2026 (EFFECT_SOURCE_CHANGED)
  • مجموعتا المعدَّل والملغى المكتشفتان من البيانات يجب أن تطابقا المتوقع (SET_UNEXPECTED)
  • النص الحالي يجب أن يساوي النص النافذ بعد الاستبدال حرفيًا قبل الرجوع عنه (STATE_UNEXPECTED)
  • بصمة md5 لنصوص كل التشريعات **خارج** الصفوف المستهدفة قبل وبعد (SCOPE_BREACH)
  • نسخة احتياطية لكل صف سيُمسّ (العنوان والنص والحالة والميتاداتا) يستردها --restore
  • إعادة التشغيل بلا أثر (كل خطوة تفحص إن كانت مطبَّقة سلفًا)

  .venv/bin/python tools/fix_deferred_91_2026.py --backup-dir DIR [--ids-out FILE]
  .venv/bin/python tools/fix_deferred_91_2026.py --restore DIR/rows_before.jsonl
  .venv/bin/python tools/fix_deferred_91_2026.py --report        (قراءة خالصة للجولة التالية)
"""
import os, sys, re, json, argparse, datetime, collections

ROOT = os.environ.get("LM_ROOT", "/opt/LegalMind")
sys.path.insert(0, ROOT)
import kb_types as _kb                                      # noqa: E402
import psycopg                                              # noqa: E402
from psycopg.types.json import Jsonb                        # noqa: E402
from engine.normalizer.canonical import normalize_text      # noqa: E402

TYPES = list(_kb.LEGISLATION_TYPES)
TODAY = "2026-10-09"
EFFECT_DATE = "2027-10-01"
EFFECT_SHOW = "2027/10/1"
EFFECT_RULE = "اعتباراً من تاريخ العمل بالمرسوم بقانون رقم (88) لسنة 2026"
EFFECT_SRC_ID = "legis-88-2026-issuing-m7"
EFFECT_SRC_NEEDLE = "1/10/2027"
RULE_SRC_ID = "legis-91-2026-issue-4"
RULE_SRC_NEEDLE = "تاريخ العمل بالمرسوم بقانون رقم (88) لسنة 2026"
TRANSITION_ID = "legis-88-2026-issuing-m3"   # استمرار محكمة أسواق المال فيما قُيّد لديها

LAW = "legis-7-2010-"
AMEND_TAG = "91 لسنة 2026"                     # يُعرف به سند النسخة السابقة المضافة يوم 9/20
REPEAL_INSTR = "legis-91-2026-issue-3"
EXPECT_AMENDED = {"legis-7-2010-m1", "legis-7-2010-m2"}
EXPECT_REPEALED = {"legis-7-2010-m%d" % n for n in (108, 109, 110, 111, 112, 113, 116)}
EXPECT_NOTED = {"legis-7-2010-m114", "legis-7-2010-m130"}

# الاستبدالان كما في المرسوم (المادة الأولى) — المسافة بين الكلمات تقبل سطرًا (درس phrase_rx §13)
OLD_DEF_MINISTER = "الوزير المختص : وزير التجارة والصناعة"
NEW_DEF_MINISTER = "الوزير المختص : الوزير الذي يحدده مجلس الوزراء"
OLD_DEF_COURT = "المحكمة المختصة : محكمة أسواق المال المنصوص عليها في هذا القانون."
NEW_DEF_COURT = ("المحكمة المختصة : الدائرة الاقتصادية المدنية والتجارية أو الإدارية "
                 "المنشأة بالمرسوم بقانون رقم (88) لسنة 2026، والمحكمة المختصة وفقا "
                 "للقواعد المقررة في قانون الإجراءات والمحاكمات الجزائية بحسب الأحوال.")
SUBS = [("وزير التجارة والصناعة", "الوزير المختص"), ("محكمة أسواق المال", "المحكمة المختصة")]


def _rx(p):
    return re.compile(r"\s+".join(re.escape(w) for w in p.split()))


BLOCK_MARK = "ـــ نصٌّ مُعلَّق بالمرسوم بقانون رقم (91) لسنة 2026"
REPEAL_MARK = "ـــ إلغاءٌ مُعلَّق بالمرسوم بقانون رقم (91) لسنة 2026"
T_AMEND = " ⟨يُعدَّل بالمرسوم بقانون 91/2026 — يُعمل به من %s⟩" % EFFECT_SHOW
T_REPEAL = " ⟨تُلغى بالمرسوم بقانون 91/2026 — يُعمل به من %s⟩" % EFFECT_SHOW
NOTE_TAIL = ("تنبيه لاحق (2026-10-09): المرسوم بقانون رقم (91) لسنة 2026 لا يُعمل به إلا "
             "اعتبارًا من تاريخ العمل بالمرسوم بقانون رقم (88) لسنة 2026، أي من 2027/10/1 "
             "(المادة الرابعة من 91/2026، والمادة السابعة من مواد إصدار 88/2026). فالمواد "
             "108–113 و116 من هذا القانون نافذة حتى ذلك التاريخ.")

# البطاقات والعناوين — (مفتاح المجموعة، اسم البطاقة، وسم العنوان أو None)
CARDS = [
    ("legis-88-2026", "قانون إنشاء الدوائر الاقتصادية ⟨يُعمل به من %s⟩" % EFFECT_SHOW,
     " ⟨يُعمل به من %s⟩" % EFFECT_SHOW),
    ("legis-91-2026", "مرسوم بقانون بتعديل بعض أحكام قانون هيئة أسواق المال (7/2010) "
     "⟨يُعمل به من %s⟩" % EFFECT_SHOW, " ⟨يُعمل به من %s⟩" % EFFECT_SHOW),
    ("legis-94-2026", "مرسوم بقانون بتعديل بعض أحكام قانون المناقصات العامة (49/2016) "
     "⟨يُعمل به بعد ثلاثة أشهر من 2026/9/27⟩", " ⟨يُعمل به بعد ثلاثة أشهر من 2026/9/27⟩"),
    ("legis-10-2026", "قانون تنظيم العمل بقطاع التجارة الرقمية ⟨يُعمل به بعد شهر من نشر لائحته "
     "التنفيذية⟩", None),
    ("legis-90-2026", "قانون الصكوك الحكومية", None),
]

GEXPR = ("COALESCE(metadata->>'library_group', substring(id from '^(legis-[a-z0-9]+-[0-9]+)'), "
         "substring(id from '^(lreg-[0-9]+-[0-9]+-k[0-9]+)'), "
         "substring(id from '^(regl-[0-9]+-[0-9]+)'), "
         "substring(id from '^(reg-[0-9]+-[0-9]+)'))")
FP_OUT = ("SELECT md5(string_agg(id || '␟' || coalesce(title,'') || '␟' || coalesce(original_text,'') "
          "|| '␟' || coalesce(verification_status,'') || '␟' || coalesce(usable_as_citation::text,''), "
          "'|' ORDER BY id)) FROM knowledge_objects WHERE object_type = ANY(%s) AND NOT (id = ANY(%s))")


def _block(scope, text):
    return ("%s — %s — لا يُعمل به إلا %s، أي من %s (المادة السابعة من مواد إصدار المرسوم بقانون "
            "88/2026)؛ والنصُّ أعلاه هو النافذ حتى ذلك التاريخ ـــ\n%s"
            % (BLOCK_MARK, scope, EFFECT_RULE, EFFECT_SHOW, text))


REPEAL_BLOCK = ("%s — تُلغى هذه المادة بالمادة الثالثة منه %s، أي من %s (المادة السابعة من مواد "
                "إصدار المرسوم بقانون 88/2026)؛ والنصُّ أعلاه نافذ حتى ذلك التاريخ. وتستمر محكمة "
                "أسواق المال في نظر ما قُيّد لديها قبل ذلك التاريخ حتى الفصل فيه (المادة الثالثة "
                "من مواد إصدار 88/2026 — %s) ـــ" % (REPEAL_MARK, EFFECT_RULE, EFFECT_SHOW, TRANSITION_ID))


def _pending(kind, instr, extra):
    d = {"instrument": instr, "effective_rule": EFFECT_RULE,
         "effective_from": EFFECT_DATE,
         "effective_from_basis": "منصوص: %s («يعمل به من تاريخ 1/10/2027»)" % EFFECT_SRC_ID,
         "in_force_today": False, "recorded_at": TODAY, "kind": kind}
    d.update(extra)
    return d


def _correction(meta, note):
    sc = meta.get("source_correction")
    entry = {"date": TODAY, "note": note}
    if isinstance(sc, list):
        if not any(isinstance(x, dict) and x.get("note") == note for x in sc):
            sc.append(entry)
        meta["source_correction"] = sc
    elif sc:
        if note not in str(sc):
            meta["source_correction"] = [sc, entry]
    else:
        meta["source_correction"] = [entry]


def _title_add(t, mark):
    t = t or ""
    return t if mark.strip() in t else t + mark


def touched_ids(cur):
    ids = set()
    cur.execute("SELECT id FROM knowledge_objects WHERE id LIKE %s AND object_type = ANY(%s) AND "
                "(metadata->>'repeal_instrument' = %s OR (metadata->'pending_repeal'->>'instrument') = %s "
                " OR metadata::text LIKE %s)",
                (LAW + "%", TYPES, REPEAL_INSTR, REPEAL_INSTR, "%" + AMEND_TAG + "%"))
    ids |= {r[0] for r in cur.fetchall()}
    ids |= EXPECT_NOTED            # ملاحظتاهما تُمسّان فتدخلان النسخة الاحتياطية
    for key, _, _ in CARDS:
        cur.execute("SELECT id FROM knowledge_objects WHERE object_type = ANY(%s) AND " + GEXPR + " = %s",
                    (TYPES, key))
        ids |= {r[0] for r in cur.fetchall()}
    return ids


def apply(a):
    conn = psycopg.connect(os.environ["DATABASE_URL"])
    changed_text = set()
    try:
        with conn.cursor() as cur:
            # 0) مصدر التاريخ من القاعدة نفسها
            for oid, needle in ((EFFECT_SRC_ID, EFFECT_SRC_NEEDLE), (RULE_SRC_ID, RULE_SRC_NEEDLE)):
                cur.execute("SELECT original_text FROM knowledge_objects WHERE id=%s", (oid,))
                r = cur.fetchone()
                if not r or needle not in re.sub(r"\s+", " ", r[0]):
                    raise SystemExit("EFFECT_SOURCE_CHANGED: %s لا يحمل «%s»" % (oid, needle))
            print("EFFECT_SOURCE_OK: 91/2026 ← 88/2026 ← %s" % EFFECT_SHOW)

            ids = touched_ids(cur)
            cur.execute(FP_OUT, (TYPES, list(ids)))
            fp_before = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM knowledge_objects")
            n_before = cur.fetchone()[0]
            cur.execute("SELECT id, title, original_text, normalized_text, verification_status, "
                        "usable_as_citation, metadata FROM knowledge_objects WHERE id = ANY(%s) ORDER BY id",
                        (list(ids),))
            rows = cur.fetchall()
            bpath = os.path.join(a.backup_dir, "rows_before.jsonl")
            with open(bpath, "w", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps(dict(zip(("id", "title", "original_text", "normalized_text",
                                                 "verification_status", "usable_as_citation", "metadata"), r)),
                                       ensure_ascii=False) + "\n")
            if os.path.getsize(bpath) == 0:
                raise SystemExit("BACKUP_EMPTY")
            print("BACKUP_OK: %d صفًّا ← %s" % (len(rows), bpath))
            byid = {r[0]: r for r in rows}

            # 1) المواد المعدَّلة — من البيانات: نسخة سابقة سندها 91/2026
            amended = {}
            for oid, r in byid.items():
                if not oid.startswith(LAW):
                    continue
                pv = [p for p in ((r[6] or {}).get("previous_versions") or [])
                      if AMEND_TAG in str(p.get("superseded_by", ""))]
                if pv:
                    amended[oid] = pv[-1]
            if set(amended) != EXPECT_AMENDED:
                raise SystemExit("SET_UNEXPECTED: المعدَّلة المكتشفة %s" % sorted(amended))
            for oid, pv in sorted(amended.items()):
                _, title, cur_text, _, _, _, meta = byid[oid]
                meta = dict(meta or {})
                old = pv["text"]
                if cur_text.startswith(old) and BLOCK_MARK in cur_text:
                    print("AMEND_ALREADY_PENDING: %s" % oid)
                    continue
                if oid.endswith("-m1"):
                    expect = old.replace(OLD_DEF_MINISTER, NEW_DEF_MINISTER).replace(OLD_DEF_COURT, NEW_DEF_COURT)
                    block_txt = NEW_DEF_MINISTER + "\n" + NEW_DEF_COURT
                    scope = "التعريفان المستبدَلان (الوزير المختص) و(المحكمة المختصة) — المادة الأولى منه"
                else:
                    expect = old
                    for o, n in SUBS:
                        expect = _rx(o).sub(n, expect)
                    block_txt = cur_text
                    scope = ("نصُّ المادة بعد استبدال «الوزير المختص» بعبارة «وزير التجارة والصناعة» "
                             "— الفقرة الثانية من المادة الأولى منه")
                if expect != cur_text:
                    raise SystemExit("STATE_UNEXPECTED: %s نصها الحالي ليس النص النافذ بعد الاستبدال" % oid)
                body = old + "\n\n" + _block(scope, block_txt)
                pend = {k: meta.pop(k) for k in ("amended_by", "amendment_date", "amendment_scope") if k in meta}
                meta["pending_amendment"] = _pending("amendment", "legis-91-2026-issue-1",
                                                     {"text_after_commencement": cur_text, "was": pend})
                _correction(meta, "أُعيد المتن إلى النص النافذ اليوم: تعديل 91/2026 طُبّق يوم 2026-09-20 "
                                  "قبل نفاذه (يُعمل به من 2027/10/1) — النص المعدَّل كاملًا في "
                                  "pending_amendment.text_after_commencement وفي الكتلة الموسومة.")
                cur.execute("UPDATE knowledge_objects SET original_text=%s, normalized_text=%s, title=%s, "
                            "metadata=%s, updated_at=now() WHERE id=%s",
                            (body, normalize_text(body), _title_add(title, T_AMEND), Jsonb(meta), oid))
                changed_text.add(oid)
                print("AMEND_DEFERRED: %s — المتن نافذ اليوم والقادم في كتلة موسومة" % oid)

            # 2) الإلغاء المؤجَّل — من البيانات
            cur.execute("SELECT verification_status, count(*) FROM knowledge_objects WHERE id ~ %s "
                        "AND object_type='legislation_article' AND coalesce(verification_status,'') <> 'superseded' "
                        "AND NOT (id = ANY(%s)) GROUP BY 1 ORDER BY 2 DESC", ("^legis-7-2010-m[0-9]+$", list(EXPECT_REPEALED)))
            modes = cur.fetchall()
            if not modes or not modes[0][0]:
                raise SystemExit("STATUS_MODE_MISSING: لا حالة تحقق غالبة لشقيقات 7/2010")
            status = modes[0][0]
            print("STATUS_FROM_SIBLINGS: %s (%s)" % (status, modes[:3]))
            rep = {oid for oid, r in byid.items() if oid.startswith(LAW) and (
                (r[6] or {}).get("repeal_instrument") == REPEAL_INSTR or
                ((r[6] or {}).get("pending_repeal") or {}).get("instrument") == REPEAL_INSTR)}
            if rep != EXPECT_REPEALED:
                raise SystemExit("SET_UNEXPECTED: الملغاة المكتشفة %s" % sorted(rep))
            for oid in sorted(rep):
                _, title, text, _, vs, uc, meta = byid[oid]
                meta = dict(meta or {})
                if REPEAL_MARK in text and meta.get("pending_repeal"):
                    print("REPEAL_ALREADY_PENDING: %s" % oid)
                    continue
                was = {k: meta.pop(k) for k in ("repealed_by", "repeal_date", "repeal_instrument", "repeal_note")
                       if k in meta}
                was["verification_status"] = vs
                was["usable_as_citation"] = uc
                meta["pending_repeal"] = _pending("repeal", REPEAL_INSTR, {"was": was})
                _correction(meta, "أُعيدت المادة قابلةً للاستشهاد: إلغاؤها بالمرسوم بقانون 91/2026 لا يُعمل "
                                  "به إلا من 2027/10/1 — وُسمت superseded يوم 2026-09-20 قبل نفاذ الإلغاء.")
                body = text + "\n\n" + REPEAL_BLOCK
                cur.execute("UPDATE knowledge_objects SET original_text=%s, normalized_text=%s, title=%s, "
                            "verification_status=%s, usable_as_citation=true, metadata=%s, updated_at=now() "
                            "WHERE id=%s",
                            (body, normalize_text(body), _title_add(title, T_REPEAL), status, Jsonb(meta), oid))
                changed_text.add(oid)
                print("REPEAL_DEFERRED: %s — قابلة للاستشهاد، والإلغاء معلَّق" % oid)

            # 3) ملاحظتا م114 وم130
            cur.execute("SELECT id, metadata FROM knowledge_objects WHERE id LIKE %s AND "
                        "metadata->>'source_note' LIKE %s", (LAW + "%", "%محكمة سوق المال%"))
            noted = dict(cur.fetchall())
            if set(noted) != EXPECT_NOTED:
                raise SystemExit("SET_UNEXPECTED: الملاحظات المكتشفة %s" % sorted(noted))
            for oid, meta in sorted(noted.items()):
                if NOTE_TAIL in meta["source_note"]:
                    print("NOTE_ALREADY: %s" % oid)
                    continue
                meta["source_note"] = meta["source_note"] + "\n\n" + NOTE_TAIL
                cur.execute("UPDATE knowledge_objects SET metadata=%s WHERE id=%s", (Jsonb(meta), oid))
                print("NOTE_DATED: %s" % oid)

            # 4) البطاقات والعناوين
            for key, card, mark in CARDS:
                cur.execute("SELECT id, title FROM knowledge_objects WHERE object_type = ANY(%s) AND "
                            + GEXPR + " = %s", (TYPES, key))
                grp = cur.fetchall()
                if not grp:
                    raise SystemExit("CARD_GROUP_MISSING: %s" % key)
                cur.execute("UPDATE knowledge_objects SET metadata = coalesce(metadata,'{}'::jsonb) || "
                            "jsonb_build_object('library_card_name', %s::text) WHERE object_type = ANY(%s) AND "
                            + GEXPR + " = %s", (card, TYPES, key))
                nt = 0
                if mark:
                    for oid, t in grp:
                        nt2 = _title_add(t, mark)
                        if nt2 != (t or ""):
                            cur.execute("UPDATE knowledge_objects SET title=%s, updated_at=now() WHERE id=%s",
                                        (nt2, oid))
                            changed_text.add(oid)
                            nt += 1
                print("CARD_OK: %-14s %3d كائنًا | عناوين وُسمت: %d | %s" % (key, len(grp), nt, card))

            # 5) التحقق
            cur.execute(FP_OUT, (TYPES, list(ids)))
            if cur.fetchone()[0] != fp_before:
                raise SystemExit("SCOPE_BREACH: تغيّر صفٌّ خارج النطاق — تراجع فوري!")
            cur.execute("SELECT count(*) FROM knowledge_objects")
            if cur.fetchone()[0] != n_before:
                raise SystemExit("COUNT_CHANGED")
            cur.execute("SELECT count(*) FROM knowledge_objects WHERE id = ANY(%s) AND "
                        "(verification_status='superseded' OR usable_as_citation IS NOT TRUE)",
                        (list(EXPECT_REPEALED),))
            if cur.fetchone()[0]:
                raise SystemExit("STILL_SUPERSEDED: مادة ملغاة إلغاءً مؤجَّلًا ما زالت ممنوعة الاستشهاد")
        conn.commit()
        if a.ids_out:
            with open(a.ids_out, "w", encoding="utf-8") as f:
                f.write("\n".join(sorted(changed_text)) + ("\n" if changed_text else ""))
        print("IDS_FOR_REINDEX: %d" % len(changed_text))
        print("FIX91_APPLIED")
    except BaseException as e:
        conn.rollback()
        print("ROLLED_BACK: %s" % e)
        raise
    finally:
        conn.close()


def restore(path):
    recs = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn, conn.cursor() as cur:
        for r in recs:
            cur.execute("UPDATE knowledge_objects SET title=%s, original_text=%s, normalized_text=%s, "
                        "verification_status=%s, usable_as_citation=%s, metadata=%s WHERE id=%s",
                        (r["title"], r["original_text"], r["normalized_text"], r["verification_status"],
                         r["usable_as_citation"], Jsonb(r["metadata"]) if r["metadata"] is not None else None,
                         r["id"]))
        conn.commit()
    print("RESTORED: %d صفًّا أُعيدت كما كانت حرفيًا" % len(recs))


def report():
    """قراءة خالصة: بنية مجموعة أسواق المال وتعليمات كفاية رأس المال، وقواعد نفاذ صكوك 2025-2026."""
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn, conn.cursor() as cur:
        conn.read_only = True
        PART = "COALESCE(NULLIF(metadata->>'doc_part',''),'النص الأصلي')"
        SUB = "COALESCE(NULLIF(metadata->>'doc_subpart',''),'—')"
        for key in ("cma-authority-unified", "cap-adequacy-legacy", "legis-91-2026"):
            print("\n=== بنية %s (الجزء | الفرعي | العدد | أول معرّف | أول عنوان)" % key)
            cur.execute("SELECT " + PART + ", " + SUB + ", count(*), min(id), min(title) FROM knowledge_objects "
                        "WHERE object_type = ANY(%s) AND " + GEXPR + " = %s GROUP BY 1,2 ORDER BY min(id)",
                        (TYPES, key))
            rs = cur.fetchall()
            for p, s, n, i, t in rs[:80]:
                print("  %s | %s | %d | %s | %s" % (p[:60], s[:60], n, i, (t or "")[:70]))
            if len(rs) > 80:
                print("  … و%d سطرًا آخر" % (len(rs) - 80))
        print("\n=== ورود «كفاية رأس المال» داخل مجموعة أسواق المال")
        cur.execute("SELECT " + PART + ", " + SUB + ", count(*), min(id) FROM knowledge_objects WHERE "
                    "object_type = ANY(%s) AND " + GEXPR + " = 'cma-authority-unified' AND "
                    "(title LIKE %s OR metadata->>'doc_part' LIKE %s OR metadata->>'doc_subpart' LIKE %s "
                    " OR metadata->>'book_title' LIKE %s) GROUP BY 1,2 ORDER BY min(id)",
                    (TYPES, "%كفاية رأس المال%", "%كفاية%", "%كفاية%", "%كفاية%"))
        for p, s, n, i in cur.fetchall():
            print("  %s | %s | %d | %s" % (p[:60], s[:60], n, i))
        print("\n=== مفاتيح ميتاداتا مجموعة كفاية رأس المال")
        cur.execute("SELECT k, count(*), count(DISTINCT metadata->>k) FROM knowledge_objects, "
                    "jsonb_object_keys(metadata) k WHERE object_type = ANY(%s) AND jsonb_typeof(metadata)='object' "
                    "AND " + GEXPR + " = 'cap-adequacy-legacy' GROUP BY k ORDER BY 2 DESC", (TYPES,))
        for k, n, d in cur.fetchall():
            print("  %s | %d | %d" % (k, n, d))
        print("\n=== قواعد نفاذ صكوك 2025-2026 (كل جملة «يعمل به» في المجموعة)")
        cur.execute("SELECT g, id, original_text FROM (SELECT " + GEXPR + " g, id, original_text FROM "
                    "knowledge_objects WHERE object_type = ANY(%s)) s WHERE g ~ '-(2025|2026)$' "
                    "AND original_text ~ '(يعمل|يُعمل|العمل) (به|بهذا|بأحكام)' ORDER BY g, id", (TYPES,))
        seen = collections.Counter()
        for g, i, t in cur.fetchall():
            if seen[g] >= 3:
                continue
            seen[g] += 1
            t1 = re.sub(r"\s+", " ", t)
            m = re.search(r"[^.؛]{0,90}(يعمل|يُعمل|العمل) (به|بهذا|بأحكام)[^.؛]{0,90}", t1)
            print("  %-16s %-34s %s" % (g, i, m.group(0).strip() if m else ""))
    print("\nREPORT_DONE")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backup-dir")
    ap.add_argument("--ids-out")
    ap.add_argument("--restore")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    if a.report:
        return report()
    if a.restore:
        return restore(a.restore)
    if not a.backup_dir or not os.path.isdir(a.backup_dir):
        raise SystemExit("BACKUP_DIR_MISSING")
    apply(a)


if __name__ == "__main__":
    main()
