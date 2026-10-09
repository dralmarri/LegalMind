#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════
# DEPLOY_hc_gitsync.sh — المراجعة الصحية اليومية تراقب المزامنة اليومية.
#
# العلة: `daily_git_sync.sh` يعمل بمنطق سليم لكن **لا أحد يراقب أنه يعمل**،
# وإخطاره «عند الفشل» لا يغطي «لم يركض أصلًا». والمسبار الحي (2026-10-08)
# أثبت أن المؤقت يركض كل يوم وأن 17 يومًا بلا التزام حالةٌ **سليمة** — أي أنه
# لم تكن ثمة وسيلة تميّز الهادئ من الميت إلا مسبار يدوي، وهذا هو المبرر.
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
