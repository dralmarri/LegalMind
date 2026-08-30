#!/bin/bash
# daily_git_sync.sh — مزامنة يومية آلية لحالة الخادم الحية مع مستودع GitHub.
# فحص أمانة حاسم قبل أي التزام: لا كلمة مرور قاعدة ولا مفتاح API يُلتزَم أبدًا مهما حدث.
# ملاحظة بنيوية: نمط البحث عن كلمة مرور القاعدة مُشفَّر بترميز base64 لا حرفيًا — لأن هذا
# الملف نفسه يدخل تتبع Git، وأي نمط حرفي مطابق للسر يجعل السكربت يكتشف نفسه خطأً كل تشغيل
# ويمنع أي مزامنة نهائيًا (عيب رُصد واعتُمد إصلاحه 2026-08-30).
# لا بريد يوميًا عند عدم وجود تغييرات — فقط عند حدوث مزامنة فعلية أو فشل يحتاج انتباهًا.
set -uo pipefail
cd /opt/LegalMind
set -a; . deploy/.env 2>/dev/null; set +a

STAMP=$(date +%Y%m%d_%H%M%S)
LOG="/opt/legalmind-data/gitsync/${STAMP}.log"
mkdir -p /opt/legalmind-data/gitsync
log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }

notify() {
  local subject="$1" body="$2"
  echo "$body" > "/tmp/gitsync_email_${STAMP}.txt"
  /opt/LegalMind/admin/.venv/bin/python3 -c "
import sys
sys.path.insert(0, '/opt/LegalMind')
from admin.support_api import _send_notification_email
b = open('/tmp/gitsync_email_${STAMP}.txt', encoding='utf-8').read()
_send_notification_email('$subject', 'daily-git-sync', b)
" >>"$LOG" 2>&1
  rm -f "/tmp/gitsync_email_${STAMP}.txt"
}

log "=== بدء المزامنة اليومية مع GitHub ($STAMP) ==="

git add -A 2>>"$LOG"

if git diff --cached --quiet; then
  log "لا تغييرات — لا شيء لمزامنته."
  find /opt/legalmind-data/gitsync -name "*.log" -mtime +30 -delete 2>/dev/null
  exit 0
fi

log "توجد تغييرات — فحص أمانة حاسم قبل أي التزام"

# كل أنماط الأسرار مُشفَّرة (base64) — تُفكّ وقت التشغيل فقط، فلا تظهر حرفيًا في هذا
# الملف المتتبَّع بـGit (وإلا اكتشف السكربت نفسه خطأً كل مرة يدخل فيها التتبع — عيب رُصد
# مرتين في نفس الجولة: أولًا لكلمة مرور القاعدة، ثم لنمطي مفتاحي API المنسيَّين)
PWFRAG=$(echo "MFBUaEJs" | base64 -d)
ANTFRAG=$(echo "c2stYW50LWFwaTAzLQ==" | base64 -d)
OAIFRAG=$(echo "c2stcHJvai0=" | base64 -d)

LEAK_FILES=""
for f in $(git diff --cached --name-only); do
  # فحص الملف الحقيقي على القرص مباشرة — لا نسخة فهرس Git (تجنبًا لأي تخزين مؤقت قائم
  # على حجم/توقيت الملف بعد كتابة متتالية سريعة، رُصد يُنتج نتائج قديمة أحيانًا)
  if [ -f "$f" ] && grep -qE "${PWFRAG}|${ANTFRAG}|${OAIFRAG}" "$f" 2>/dev/null; then
    LEAK_FILES="$LEAK_FILES $f"
  fi
done

if [ -n "$LEAK_FILES" ]; then
  log "SECRET_LEAK_DETECTED في:$LEAK_FILES"
  git reset >>"$LOG" 2>&1
  notify "نظام LegalMind — تحذير: توقفت المزامنة اليومية" \
    "اكتُشف أثر لسر (كلمة مرور قاعدة أو مفتاح API) ضمن ملفات متغيرة اليوم، فأُوقفت المزامنة تلقائيًا ولم يُلتزَم شيء.
الملفات: $LEAK_FILES
يحتاج مراجعة يدوية قبل أي محاولة دفع لاحقة."
  exit 1
fi
log "الفحص نظيف — لا أثر لأي سر."

N_FILES=$(git diff --cached --name-only | wc -l)
git commit -m "مزامنة آلية يومية لحالة الخادم — $STAMP" >>"$LOG" 2>&1
COMMIT_RC=$?
if [ $COMMIT_RC -ne 0 ]; then
  log "فشل الالتزام"
  notify "نظام LegalMind — فشل المزامنة اليومية" "فشل git commit — راجع السجل على الخادم: $LOG"
  exit 1
fi
log "التزام ناجح: $N_FILES ملفًا"

git push origin main >>"$LOG" 2>&1
PUSH_RC=$?
if [ $PUSH_RC -ne 0 ]; then
  log "فشل الدفع (push) — الالتزام محلي فقط، لم يصل GitHub بعد"
  notify "نظام LegalMind — تحذير: فشل دفع المزامنة اليومية" \
    "التزم Git محليًا بنجاح ($N_FILES ملفًا) لكن الدفع إلى GitHub فشل — قد تحتاج بيانات الاعتماد
تجديدًا أو توجد مشكلة اتصال. راجع السجل على الخادم: $LOG"
  exit 1
fi

log "DONE: دُفع بنجاح ($N_FILES ملفًا)"
notify "نظام LegalMind — مزامنة يومية ناجحة" "تمت مزامنة $N_FILES ملفًا مع GitHub بنجاح."

find /opt/legalmind-data/gitsync -name "*.log" -mtime +30 -delete 2>/dev/null
exit 0
