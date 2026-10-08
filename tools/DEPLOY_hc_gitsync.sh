#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════
# DEPLOY_hc_gitsync.sh — المراجعة الصحية اليومية تراقب المزامنة اليومية.
#
# العلة: `daily_git_sync.sh` يعمل بمنطق سليم لكن **لا أحد يراقب أنه يعمل** —
# فتوقفه صامت (رُصد فعلًا: 17 يومًا بلا مزامنة، واكتُشف بالصدفة). هذا تطبيق
# درس «الميزة الآمنة الفشل تحتاج فحص حياة دوريًا» على **الحارس نفسه**.
#
# يضيف ثلاثة مؤشرات لتقرير المراجعة اليومية: طراوة آخر تشغيل (بإعادة تشغيل
# واحدة ميكانيكية عند التأخر)، والتزامات محلية لم تُدفع، وبُعد GitHub بالأيام.
#
# البوابة: فحص صياغي ← **تشغيل يدوي كامل للمراجعة** (قاعدة §11) ← تراجع آلي.
# تنبيه: التشغيل اليدوي يستغرق ~6 دقائق لأنه يشغّل البطارية ضمنه.
#
# النجاح النهائي = DONE_HCGIT
# ══════════════════════════════════════════════════════════════════════════
set -uo pipefail

SELF="${BASH_SOURCE[0]:-}"
if [ "${1:-}" != "--worker" ] && [ -n "$SELF" ] && [ -f "$SELF" ]; then
  LOG=/tmp/deploy_hcgit_$(date +%s).log
  echo "running in background (survives terminal disconnect). log: $LOG"
  nohup bash "$SELF" --worker > "$LOG" 2>&1 &
  disown
  echo "follow with:  tail -f $LOG"
  exit 0
fi
[ "${1:-}" = "--worker" ] || echo "(pasted mode: running in the foreground)"

cd /opt/LegalMind
set -a; . /opt/LegalMind/deploy/.env; set +a

HC=/opt/LegalMind/tools/daily_healthcheck.sh
STAMP=$(date +%Y%m%d_%H%M%S)
SAFE=/opt/legalmind-data/hcgit_safe_$STAMP
mkdir -p "$SAFE"
cp -a "$HC" "$SAFE/daily_healthcheck.sh"
if [ ! -s "$SAFE/daily_healthcheck.sh" ]; then
  echo "BACKUP_EMPTY — لا تراجع ممكن. أوقفت بلا أي تعديل."; exit 1
fi
echo "النسخة الآمنة: $SAFE ($(wc -c < "$SAFE/daily_healthcheck.sh") بايت)"

rollback() {
  echo; echo "══════ تراجع آلي ══════"
  cp -a "$SAFE/daily_healthcheck.sh" "$HC"
  echo "استُعيد $HC"; echo "ROLLED_BACK"; exit 1
}

echo
echo "═══ 1) كتابة الباتشر ═══"
base64 -d <<'B64LM' | gunzip > /opt/LegalMind/tools/patch_hc_gitsync.py
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
B64LM
python3 -c "import ast,io;ast.parse(io.open('/opt/LegalMind/tools/patch_hc_gitsync.py',encoding='utf-8').read());print('SYNTAX_OK')" || rollback

echo
echo "═══ 2) تطبيق الرقعة ═══"
python3 /opt/LegalMind/tools/patch_hc_gitsync.py || rollback

echo
echo "═══ 3) فحص صياغي للسكربت بعد الرقعة ═══"
bash -n "$HC" || rollback
echo "BASH_SYNTAX_OK"

echo
echo "═══ 4) تشغيل يدوي كامل للمراجعة الصحية (قاعدة §11 — ~6 دقائق) ═══"
bash "$HC"
HC_RC=$?
echo "رمز الخروج: $HC_RC"
[ "$HC_RC" -eq 0 ] || { echo "HEALTHCHECK_RUN_FAILED"; rollback; }

echo
echo "═══ 5) ما قالته الفحوص الثلاثة الجديدة في هذا التشغيل ═══"
HCLOG=$(ls -1t /opt/legalmind-data/healthcheck/*.log 2>/dev/null | head -1)
set +e
grep -E "المزامنة|GitHub|التزام" "$HCLOG" 2>/dev/null
echo "—— سجل المراجعة الكامل: $HCLOG"
echo
echo "═══ 6) حالة المزامنة بعد التشغيل ═══"
echo "آخر سجل مزامنة: $(ls -1t /opt/legalmind-data/gitsync/*.log 2>/dev/null | head -1)"
echo "آخر التزام على main:"; git log --oneline -1 main
echo "التزامات محلية غير مدفوعة: $(git rev-list --count origin/main..main 2>/dev/null)"

echo
echo "النسخة الآمنة محفوظة في: $SAFE"
echo "DONE_HCGIT"
