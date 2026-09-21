#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════
# verify_1809.sh — إكمال التحقق بعد نجاح إدخال دفعة العدد 1809.
#
# الإدخال والفهرسة نجحا فعلًا (INGEST_SUKUK90_OK / INGEST_1809_OK /
# REGL_590_OFFICIAL_OK / REINDEX_DELTA_OK 116 نقطة / CONSISTENT_OK) — وسقط
# اختبار الاسترجاع وحده لأن `embed_query_cli.py` يقرأ السؤال من **stdin** لا
# من وسيط سطر الأوامر، فخرج المتجه `[]` ورفضه Qdrant بـ400. هذا الملف يعيد
# الاختبار بالصيغة الصحيحة ثم يشغّل البطارية.
#
# النجاح النهائي = DONE_1809_ALL
# ══════════════════════════════════════════════════════════════════════════
set -uo pipefail          # لا -e: خطأ في اختبار تشخيصي يجب ألا يمنع البطارية

SELF="${BASH_SOURCE[0]:-}"
if [ "${1:-}" != "--worker" ] && [ -n "$SELF" ] && [ -f "$SELF" ]; then
  LOG=/tmp/verify_1809_$(date +%s).log
  echo "running in background. log: $LOG"
  nohup bash "$SELF" --worker > "$LOG" 2>&1 &
  disown
  echo "follow with:  tail -f $LOG"
  exit 0
fi

cd /opt/LegalMind
set -a; . /opt/LegalMind/deploy/.env; set +a

echo "═══ أ) جرد ما دخل فعلًا ═══"
psql "$DATABASE_URL" -At -c "
  SELECT 'legis-90-2026 = '||count(*) FROM knowledge_objects WHERE id LIKE 'legis-90-2026-%'
  UNION ALL SELECT 'legis-91-2026 = '||count(*) FROM knowledge_objects WHERE id LIKE 'legis-91-2026-%'
  UNION ALL SELECT 'legis-93-2026 = '||count(*) FROM knowledge_objects WHERE id LIKE 'legis-93-2026-%'
  UNION ALL SELECT 'regl-10-2020  = '||count(*) FROM knowledge_objects WHERE id LIKE 'regl-10-2020-%'
  UNION ALL SELECT 'legis-80-2026 (تنظيم القضاء، يجب 87) = '||count(*) FROM knowledge_objects WHERE id LIKE 'legis-80-2026-%'
  UNION ALL SELECT 'legis-10-2020 (قانون التوثيق، يجب 30) = '||count(*) FROM knowledge_objects WHERE id LIKE 'legis-10-2020-%'
  UNION ALL SELECT 'مواد 7/2010 الموسومة بالإلغاء (يجب 7) = '||count(*) FROM knowledge_objects
      WHERE id LIKE 'legis-7-2010-m%' AND verification_status='superseded'
        AND metadata->>'repeal_instrument'='legis-91-2026-issue-3';"

echo
echo "═══ ب) اختبار استرجاع حي (بالصيغة الصحيحة: السؤال عبر stdin) ═══"
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /opt/LegalMind/.venv/bin/python - <<'PYTEST'
import sys, os, subprocess, json
sys.path.insert(0, "/opt/LegalMind"); os.chdir("/opt/LegalMind")
from engine import legalmind_engine as eng
PY = "/opt/LegalMind/.venv/bin/python"
CASES = [
 ("الشركة ذات الغرض الخاص وإصدار الصكوك الحكومية وموجوداتها", "legis-90-2026-"),
 ("هيئة الفتوى والرقابة الشرعية للصكوك ومراقب الحسابات", "legis-90-2026-"),
 ("المحكمة المختصة بمنازعات هيئة أسواق المال بعد إنشاء الدوائر الاقتصادية", "legis-91-2026-"),
 ("عقوبة مخالفة أحكام الغش التجاري ورد قيمة البضاعة المغشوشة إلى المشتري", "legis-"),
 ("رسوم توثيق التوكيلات العامة والخاصة وإثبات التاريخ لدى إدارة التوثيق", "regl-10-2020-"),
]
ok_all = True
for q, want in CASES:
    # embed_query_cli يقرأ من stdin لا من argv — وهذا بالضبط سبب فشل الجولة السابقة
    p = subprocess.run([PY, "engine/embed_query_cli.py"], input=q,
                       capture_output=True, text=True, env=dict(os.environ), timeout=240)
    vec = json.loads((p.stdout or "").strip() or "[]")
    if not vec:
        print("  EMBED_EMPTY لـ«%s» — stderr: %s" % (q[:40], (p.stderr or "")[-200:]))
        ok_all = False
        continue
    r = eng.qdrant_request("POST", "/collections/%s/points/search" % eng.COLLECTION,
          {"vector": vec, "limit": 6, "with_payload": True,
           "filter": {"must": [{"key": "object_type", "match": {"any": [
             "legislation_article", "legislation_issuing_article", "legislation_preamble"]}}]}})
    hits = [(h["score"], h["payload"]["object_id"]) for h in r["result"]]
    hit = any(o.startswith(want) for _, o in hits)
    ok_all = ok_all and hit
    print("  «%s»  -> %s" % (q[:52], "OK" if hit else "MISS"))
    for s, oid in hits[:3]:
        print("        %.3f  %s" % (s, oid))
print("RETRIEVAL_" + ("ALL_OK" if ok_all else "SOME_MISS"))
PYTEST

echo
echo "═══ ج) بطارية القياس (صمام الانتكاس) ═══"
/opt/LegalMind/admin/.venv/bin/python /opt/LegalMind/tools/battery_run.py > /tmp/battery_1809_all.log 2>&1
tail -20 /tmp/battery_1809_all.log
echo
if grep -q "BATTERY_PASS" /tmp/battery_1809_all.log; then
  echo "DONE_1809_ALL"
else
  echo "BATTERY_FAIL — أعد تشغيل البطارية وحدها مرة واحدة قبل أي تشخيص:"
  echo "  cd /opt/LegalMind; set -a; . deploy/.env; set +a"
  echo "  /opt/LegalMind/admin/.venv/bin/python /opt/LegalMind/tools/battery_run.py"
  exit 1
fi
