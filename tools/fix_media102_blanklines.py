# -*- coding: utf-8 -*-
"""تنقية أسطر فارغة دخيلة داخل ثماني مواد من قانون تنظيم الإعلام 102/2026.

**ما العلة ومن أين جاءت:** نُقل القانون بصريًا عمودًا عمودًا على دفعات، وحين عبرت
المادة حدَّ ملف النقل التُقط بينهما **سطر فارغ** ليس في الجريدة. سبعٌ منها بين بنود
مرقَّمة (أثرها شكلي)، **والثامنة م51 تشقُّ جملة واحدة في منتصفها** («... إلا بعد
الحصول ⏎⏎ على الترخيص اللازم ...») — وهذا يُفسد قراءة الجملة ويضرّ بجودة التضمين،
فهو وحده يبرر الجولة.

**لا يُمسّ حرف واحد:** التغيير فراغٌ خالص، وحارسُه قاطع — نصُّ كل مادة بعد تجريد
**كل** المحارف البيضاء يجب أن يبقى مطابقًا بايتًا ببايت لما قبلها، وإلا سقطت
المعاملة كلها (`CONTENT_CHANGED`). ومع ذلك يُحفظ النص السابق في
`metadata.previous_versions[]` التزامًا بقاعدة «لا يُمحى نص قط».

النطاق مقصور على المعرفات الثمانية؛ وأي كائن آخر تحت `legis-102-2026-` تُقاس بصمته
قبل وبعد (`SCOPE_BREACH`). وإعادة التشغيل عديمة الأثر (منع التكرار ببصمة sha256).

النجاح = FIX_BLANKLINES_OK (أو FIX_BLANKLINES_NOOP إن كانت مُطبَّقة سلفًا)
"""

import sys, os, re, hashlib, datetime

sys.path.insert(0, "/opt/LegalMind")
os.chdir("/opt/LegalMind")

import psycopg
from psycopg.types.json import Jsonb
from engine.normalizer.canonical import normalize_text

PREFIX = "legis-102-2026-"
TARGETS = [PREFIX + "m%d" % n for n in (1, 11, 15, 19, 33, 51, 61, 68)]
NOTE = ("سطر فارغ دخيل من نقلنا (حدُّ ملف النقل البصري) لا من الجريدة — أُزيل. "
        "التغيير فراغٌ خالص: نص المادة بعد تجريد المحارف البيضاء لم يتغير بايتًا واحدًا.")
CHANGED_IDS_FILE = "/opt/legalmind-data/media102_blank_changed_ids.txt"


def squeeze(t):
    return re.sub(r"\n{2,}", "\n", t)


def bare(t):
    return re.sub(r"\s+", "", t)


def _sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def main():
    dsn = os.environ["DATABASE_URL"]
    changed = []
    try:
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM knowledge_objects")
                total_before = cur.fetchone()[0]

                # ── حارس نطاق: بصمة كل ما هو خارج المجموعة المستهدفة ──
                cur.execute("""SELECT md5(string_agg(id || '␟' || original_text, '|' ORDER BY id))
                               FROM knowledge_objects
                               WHERE id LIKE %s AND NOT (id = ANY(%s))""",
                            (PREFIX + "%", TARGETS))
                outside_before = cur.fetchone()[0]

                print("──── الفحص والإزالة ────")
                for rid in TARGETS:
                    cur.execute("""SELECT original_text, metadata FROM knowledge_objects
                                   WHERE id=%s""", (rid,))
                    row = cur.fetchone()
                    if not row:
                        raise SystemExit("TARGET_MISSING: %s غير موجودة — أوقفت الدفعة." % rid)
                    old, meta = row[0], (row[1] or {})
                    new = squeeze(old)
                    if new == old:
                        print("  %s — ALREADY_CLEAN" % rid)
                        continue
                    # الحارس القاطع: لا شيء تغيّر سوى الفراغ
                    if bare(new) != bare(old):
                        raise SystemExit("CONTENT_CHANGED: %s تغيّر محتواها لا فراغها "
                                         "— تراجع فوري!" % rid)
                    prev = list(meta.get("previous_versions") or [])
                    sha = _sha(old)
                    if not any(p.get("sha256") == sha for p in prev):
                        prev.append({
                            "text": old, "sha256": sha,
                            "superseded_on": datetime.date.today().isoformat(),
                            "superseded_by": NOTE,
                            "recorded_at": datetime.datetime.now(
                                datetime.timezone.utc).isoformat(),
                        })
                    meta["previous_versions"] = prev
                    meta["source_correction"] = NOTE
                    cur.execute("""UPDATE knowledge_objects
                                   SET original_text=%s, normalized_text=%s,
                                       metadata=%s, updated_at=now()
                                   WHERE id=%s""",
                                (new, normalize_text(new), Jsonb(meta), rid))
                    changed.append(rid)
                    print("  %s — BLANKLINE_REMOVED (%d حرفًا ← %d)"
                          % (rid, len(old), len(new)))

                cur.execute("""SELECT md5(string_agg(id || '␟' || original_text, '|' ORDER BY id))
                               FROM knowledge_objects
                               WHERE id LIKE %s AND NOT (id = ANY(%s))""",
                            (PREFIX + "%", TARGETS))
                if cur.fetchone()[0] != outside_before:
                    raise SystemExit("SCOPE_BREACH: كائن خارج المجموعة تغيّر — تراجع!")
                cur.execute("SELECT count(*) FROM knowledge_objects")
                if cur.fetchone()[0] != total_before:
                    raise SystemExit("COUNT_CHANGED: عدد كائنات القاعدة تغيّر — تراجع!")
            conn.commit()
    except SystemExit:
        print("\nROLLED_BACK: بوابة فشلت — لم تُكتب أي تغييرات على القاعدة.")
        raise

    # يُفرَّغ دائمًا فلا تُفهرس جولةٌ سابقة
    with open(CHANGED_IDS_FILE, "w", encoding="utf-8") as fh:
        fh.write("\n".join(changed) + ("\n" if changed else ""))
    print("\nCHANGED_IDS: %d معرّفًا → %s" % (len(changed), CHANGED_IDS_FILE))

    if not changed:
        print("\nFIX_BLANKLINES_NOOP")
        return

    print("\n──── تحقق بعد الكتابة ────")
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        for rid in changed:
            cur.execute("SELECT original_text, metadata FROM knowledge_objects WHERE id=%s",
                        (rid,))
            t, m = cur.fetchone()
            assert "\n\n" not in t, "%s: ما زال فيها سطر فارغ" % rid
            assert bare(m["previous_versions"][-1]["text"]) == bare(t), \
                "%s: المحتوى اختلف عن النسخة السابقة!" % rid
        cur.execute("SELECT original_text FROM knowledge_objects WHERE id=%s",
                    (PREFIX + "m51",))
        t51 = cur.fetchone()[0]
        ok = "إلا بعد الحصول\nعلى الترخيص اللازم" in t51 or \
             "إلا بعد الحصول على الترخيص اللازم" in t51
        print("  م51 (الجملة المشقوقة): %s" % ("التأمت ✓" if ok else "لم تلتئم ✗"))
        assert ok
        print("  الثمانية: لا سطر فارغ، والمحتوى مطابق للنسخة المحفوظة بايتًا ببايت")

    print("\nFIX_BLANKLINES_OK")


if __name__ == "__main__":
    main()
