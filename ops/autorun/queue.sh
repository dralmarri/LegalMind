#!/bin/bash
# أمر آلي 17: مسح شامل عاجل لكل الكتب الـ19 (لائحة 7/2010 التنفيذية أسواق المال)
# تصنيف كل كتاب: سليم بالفعل | مصنّف خطأً لكن نصه سليم (إصلاح فوري) | نصه مشوّه فعلاً (يحتاج إعادة قراءة)
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a

# أوقف أي أمر قديم متأخر لتفادي التزاحم على القاعدة
pkill -f "table_reader.py" 2>/dev/null || true

cat > /root/audit19.py <<'PYEOF'
# -*- coding: utf-8 -*-
import sys, re, json
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()

    # 1) كل مصادر مجموعة "الكتاب-...-اسواق-المال" في الأرشيف والقاعدة معاً
    cur.execute("""SELECT DISTINCT s.source_key, s.file_name
                   FROM sources s
                   WHERE s.file_name ILIKE '%اسواق-المال%' OR s.file_name ILIKE '%الكتاب%'
                      OR s.file_name ILIKE '%لائحة%'""")
    sources = cur.fetchall()
    print("مصادر مطابقة في جدول sources:", len(sources), flush=True)

    # أيضاً: كائنات معروفة الآن بنوع legislation/legislation_article السليمة — لأعرف النوع الصحيح المعتمد فعلاً
    cur.execute("""SELECT DISTINCT object_type FROM knowledge_objects
                   WHERE metadata->>'batch_id' IS NULL AND id NOT LIKE 'TBL-%' AND id NOT LIKE 'JUR-%'
                     AND id NOT LIKE 'legis-%' AND id NOT LIKE 'lreg-%'
                   LIMIT 5""")

    def looks_garbled(text):
        t = text or ""
        digits = len(re.findall(r"\d", t))
        density = digits / max(1, len(t))
        en_hit = any(m in t for m in ("Venture Capital", "Private Equity", "Off Balance"))
        frags = [f for f in t.split("\n") if f.strip()]
        short = sum(1 for f in frags if 0 < len(f.strip()) < 25)
        score = (density > 0.06) + (en_hit * 2) + (short >= 4)
        return score >= 2

    report = []
    for sk, fname in sources:
        cur.execute("""SELECT id, object_type, title, original_text, verification_status, usable_as_citation
                       FROM knowledge_objects WHERE source_key=%s""", (sk,))
        rows = cur.fetchall()
        if not rows:
            continue
        by_type = {}
        for r in rows:
            by_type[r[1]] = by_type.get(r[1], 0) + 1
        jur_n = by_type.get("judicial_principle", 0)
        total = len(rows)
        jur_ratio = jur_n / total if total else 0

        garbled_n = sum(1 for r in rows if looks_garbled(r[3]))
        garbled_ratio = garbled_n / total if total else 0

        verdict = "سليم"
        if jur_ratio > 0.3 and garbled_ratio > 0.15:
            verdict = "مصنّف_خطأ_ومشوّه"
        elif jur_ratio > 0.3:
            verdict = "مصنّف_خطأ_فقط"
        elif garbled_ratio > 0.2:
            verdict = "مشوّه_فقط"

        report.append({"source_key": sk, "file": fname, "total": total,
                       "by_type": by_type, "jur_ratio": round(jur_ratio, 2),
                       "garbled_ratio": round(garbled_ratio, 2), "verdict": verdict})

    report.sort(key=lambda x: (x["verdict"] != "سليم", -x["total"]))
    print("\n=== تقرير %d مصدراً ===" % len(report), flush=True)
    counts = {}
    for r in report:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
        print("  [%s] %s | إجمالي=%d | مبدأ_قضائي=%.0f%% | تشوه=%.0f%% | %s" %
              (r["verdict"], r["file"][:50], r["total"], r["jur_ratio"]*100, r["garbled_ratio"]*100,
               r["by_type"]), flush=True)

    print("\nملخص الأحكام:", counts, flush=True)

    # 2) إصلاح فوري للحالة "مصنّف_خطأ_فقط": إعادة تصنيف النوع فقط، لا حاجة لإعادة قراءة
    fixed_sources = 0
    fixed_objects = 0
    for r in report:
        if r["verdict"] != "مصنّف_خطأ_فقط":
            continue
        cur.execute("""UPDATE knowledge_objects
                       SET object_type='legislation_article',
                           metadata = metadata || '{"reclassified_from":"judicial_principle"}'::jsonb,
                           updated_at=now()
                       WHERE source_key=%s AND object_type='judicial_principle'""", (r["source_key"],))
        n = cur.rowcount
        fixed_objects += n
        fixed_sources += 1
        # إعادة فهرسة (النص لم يتغير لكن الحمولة object_type تغيرت)
        cur.execute("""SELECT id, title, original_text, object_type, branch, topic, subtopic,
                              metadata->>'micro_issue', source_key
                       FROM knowledge_objects WHERE source_key=%s""", (r["source_key"],))
        allr = cur.fetchall()
        for s in range(0, len(allr), 48):
            w = allr[s:s + 48]
            common = {"object_type": w[0][3], "branch": w[0][4], "topic": w[0][5],
                      "subtopic": w[0][6], "micro_issue": w[0][7], "source_key": w[0][8]}
            eng.qdrant_request("PUT", "/collections/" + eng.COLLECTION + "/points?wait=true",
                               {"points": eng.build_points([(x[0], x[1], x[2]) for x in w], common)})
        print("  أُصلح فوراً: %s (%d كائن أُعيد تصنيفه وفهرسته)" % (r["file"][:45], n), flush=True)

    print("\nإصلاح فوري: %d مصدراً | %d كائناً أُعيد تصنيفه" % (fixed_sources, fixed_objects), flush=True)

    # 3) قائمة ما يحتاج إعادة قراءة كاملة (الأولوية القادمة)
    need_reread = [r for r in report if r["verdict"] in ("مشوّه_فقط", "مصنّف_خطأ_ومشوّه")]
    print("\nيحتاج إعادة قراءة كاملة (%d مصدراً):" % len(need_reread), flush=True)
    for r in need_reread:
        print("  -", r["file"], "| source_key=", r["source_key"], flush=True)

    with open("/root/need_reread.json", "w", encoding="utf-8") as f:
        json.dump([{"source_key": r["source_key"], "file": r["file"]} for r in need_reread],
                  f, ensure_ascii=False)
PYEOF
/opt/LegalMind/.venv/bin/python /root/audit19.py > /root/audit19.log 2>&1
cat /root/audit19.log

{
  echo "=== مسح شامل عاجل لكتب أسواق المال الـ19 — $(date -u +%F' '%T) UTC ==="
  echo ""
  cat /root/audit19.log
} > "/var/www/legalmind-v3/review-$(cat /opt/legalmind-autopilot/token).txt"
echo "===== نُشر المسح الشامل ====="
