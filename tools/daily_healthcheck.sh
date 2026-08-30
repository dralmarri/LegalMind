#!/bin/bash
# daily_healthcheck.sh — مراجعة صحية يومية آلية بإصلاح ميكانيكي محدود ومُتحكَّم فيه فقط
# (إعادة تشغيل خدمة/حاوية متوقفة، إعادة تسخين كاش نموذج معطَّل، تجديد شهادة قاربت الانتهاء،
# تنظيف ملفات مؤقتة موثقة السياسة، إعادة محاولة نسخة احتياطية متأخرة). لا تمس هذه الأداة app.py
# أو أي منطق قانوني أو بيانات القاعدة إطلاقًا — وأي شيء يحتاج حكمًا (فشل بطارية، عدم اتساق
# PG/Qdrant، خدمة لا تُصلَح آليًا) يُدرَج في تقرير ويُرسَل بريديًا دون أي محاولة إصلاح تلقائي له.
set -uo pipefail
cd /opt/LegalMind
set -a; . deploy/.env 2>/dev/null; set +a

STAMP=$(date +%Y%m%d_%H%M%S)
LOGDIR=/opt/legalmind-data/healthcheck
mkdir -p "$LOGDIR"
LOG="$LOGDIR/${STAMP}.log"
FIXED_FILE=$(mktemp)
ATTN_FILE=$(mktemp)
trap 'rm -f "$FIXED_FILE" "$ATTN_FILE"' EXIT

log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }
fixed() { echo "$*" >> "$FIXED_FILE"; log "✔ إصلاح آلي: $*"; }
attn()  { echo "$*" >> "$ATTN_FILE"; log "⚠ يحتاج انتباهًا: $*"; }

log "=== بدء المراجعة الصحية اليومية ($STAMP) ==="

# 1) الخدمات الأساسية
for svc in legalmind-admin legalmind-ingest legalmind-mcp; do
  if systemctl is-active --quiet "$svc"; then
    log "✓ $svc نشطة"
  else
    log "$svc غير نشطة — محاولة إعادة تشغيل"
    systemctl restart "$svc" 2>>"$LOG"
    sleep 3
    if systemctl is-active --quiet "$svc"; then
      fixed "أُعيدت $svc للعمل بعد توقفها"
    else
      attn "$svc متوقفة ولم تُستعَد بإعادة التشغيل — تحتاج تشخيصًا"
    fi
  fi
done

# 2) حاويات docker (Postgres/Qdrant)
for c in legalmind-postgres legalmind-qdrant; do
  ST=$(docker inspect -f '{{.State.Status}}' "$c" 2>/dev/null || echo "missing")
  if [ "$ST" = "running" ]; then
    log "✓ حاوية $c تعمل"
  else
    log "حاوية $c بحالة $ST — محاولة تشغيل"
    docker start "$c" >>"$LOG" 2>&1
    sleep 5
    ST2=$(docker inspect -f '{{.State.Status}}' "$c" 2>/dev/null || echo "missing")
    if [ "$ST2" = "running" ]; then
      fixed "أُعيدت حاوية $c للعمل بعد توقفها ($ST)"
    else
      attn "حاوية $c لا تعمل ($ST2) — تحتاج تشخيصًا"
    fi
  fi
done

# 3) استجابة API الحية
WHOAMI=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 http://127.0.0.1:8088/api/whoami 2>/dev/null || echo "000")
if [ "$WHOAMI" = "401" ]; then
  log "✓ /api/whoami=401"
else
  log "/api/whoami رجعت $WHOAMI (المتوقع 401) — محاولة إعادة تشغيل legalmind-admin"
  systemctl restart legalmind-admin 2>>"$LOG"
  sleep 5
  WHOAMI2=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 http://127.0.0.1:8088/api/whoami 2>/dev/null || echo "000")
  if [ "$WHOAMI2" = "401" ]; then
    fixed "أُعيد تشغيل legalmind-admin بعد استجابة API غير سليمة ($WHOAMI)"
  else
    attn "واجهة API لا تستجيب سليمة حتى بعد إعادة التشغيل (رجعت $WHOAMI2)"
  fi
fi

# 4) صحة المرتِّب المتقاطع الحية (نفس منطق الإصلاح المعتمد 2026-08-30)
check_rerank() {
  /opt/LegalMind/admin/.venv/bin/python3 -c "
import sys
sys.path.insert(0, '/opt/LegalMind'); sys.path.insert(0, '/opt/LegalMind/admin')
from admin import app
r = app._draft_rerank('فحص يومي', [('a', 'نص أول للفحص'), ('b', 'نص ثانٍ مختلف للفحص')])
print('OK' if r else 'FAIL')
" 2>/dev/null
}
RR=$(check_rerank)
if [ "$RR" = "OK" ]; then
  log "✓ المرتِّب المتقاطع يعمل"
else
  log "المرتِّب المتقاطع لا يعمل — محاولة إعادة تسخين الكاش"
  rm -rf /root/.cache/huggingface/hub/models--cross-encoder--mmarco-mMiniLMv2-L12-H384-v1
  /opt/LegalMind/.venv/bin/python3 -c "
from sentence_transformers import CrossEncoder
CrossEncoder('cross-encoder/mmarco-mMiniLMv2-L12-H384-v1').predict([('a', 'b')])
" >>"$LOG" 2>&1
  RR2=$(check_rerank)
  if [ "$RR2" = "OK" ]; then
    fixed "أُعيد تسخين كاش المرتِّب المتقاطع بعد توقفه"
  else
    attn "المرتِّب المتقاطع لا يزال معطلًا بعد محاولة إعادة تسخين الكاش — يحتاج تشخيصًا"
  fi
fi

# 5) اتساق PostgreSQL/Qdrant (فحص فقط — لا فهرسة كاملة آلية أبدًا، تاريخها مكلف وخطر)
PG_COUNT=$(psql "$DATABASE_URL" -tAc "SELECT count(*) FROM knowledge_objects;" 2>/dev/null | tr -d ' ')
QD_COUNT=$(curl -s --max-time 10 "http://127.0.0.1:6333/collections/legalmind_multilingual_e5_base_v1" 2>/dev/null \
  | python3 -c "import sys,json
try:
    print(json.load(sys.stdin).get('result',{}).get('points_count',''))
except Exception:
    print('')" 2>/dev/null)
if [ -n "$PG_COUNT" ] && [ -n "$QD_COUNT" ]; then
  if [ "$PG_COUNT" = "$QD_COUNT" ]; then
    log "✓ PG=Qdrant=$PG_COUNT"
  else
    attn "عدم تطابق PostgreSQL($PG_COUNT) وQdrant($QD_COUNT) — يحتاج تشخيصًا؛ لا تُشغَّل فهرسة كاملة آليًا"
  fi
else
  attn "تعذر قراءة عدّادي PostgreSQL/Qdrant للمقارنة"
fi

# 6) البطارية (فحص فقط — أي فشل يحتاج تشخيصًا حقيقيًا لا رقعة آلية)
BAT_OUT=$(/opt/LegalMind/admin/.venv/bin/python3 /opt/LegalMind/tools/battery_run.py 2>&1)
if echo "$BAT_OUT" | grep -q "BATTERY_PASS"; then
  log "✓ البطارية 13/13"
else
  attn "فشلت البطارية — انتكاس محتمل في الاسترجاع، يحتاج تشخيصًا فوريًا"
  echo "$BAT_OUT" >> "$LOG"
fi

# 7) كل شهادات SSL المُدارة على الخادم (لا نطاق LegalMind وحده — الخادم مشترك)
CERTS_RAW=$(certbot certificates 2>/dev/null)
NEED_RENEW=0
while IFS= read -r name && IFS= read -r days; do
  [ -z "$name" ] && continue
  if [ "$days" -lt 14 ] 2>/dev/null; then
    log "شهادة $name تنتهي خلال $days يومًا"
    NEED_RENEW=1
  else
    log "✓ شهادة $name سارية ($days يومًا)"
  fi
done < <(echo "$CERTS_RAW" | awk '
  /Certificate Name:/ { name=$3 }
  /VALID: [0-9]+ day/ {
    match($0, /VALID: [0-9]+/); d=substr($0, RSTART+7, RLENGTH-7)
    print name; print d
  }')
if [ "$NEED_RENEW" = "1" ]; then
  log "محاولة تجديد آلية لكل الشهادات المستحقة (certbot renew)"
  BEFORE="$CERTS_RAW"
  if certbot renew --quiet 2>>"$LOG"; then
    systemctl reload nginx 2>>"$LOG" || true
  fi
  AFTER=$(certbot certificates 2>/dev/null)
  STILL_LOW=$(echo "$AFTER" | awk '
    /Certificate Name:/ { name=$3 }
    /VALID: [0-9]+ day/ {
      match($0, /VALID: [0-9]+/); d=substr($0, RSTART+7, RLENGTH-7)
      if (d+0 < 14) print name": "d" يومًا"
    }')
  if [ -z "$STILL_LOW" ]; then
    fixed "جُدِّدت شهادة/شهادات SSL كانت قريبة من الانتهاء"
  else
    while IFS= read -r line; do
      [ -n "$line" ] && attn "شهادة SSL تحتاج تجديدًا يدويًا — $line (فشل التجديد الآلي، تحقق من DNS/الإعداد)"
    done <<< "$STILL_LOW"
  fi
fi

# 8) مساحة القرص
DISK_PCT=$(df / --output=pcent | tail -1 | tr -dc '0-9')
if [ -n "$DISK_PCT" ] && [ "$DISK_PCT" -ge 85 ]; then
  log "القرص ممتلئ ${DISK_PCT}% — تنظيف ملفات مؤقتة ضمن سياسات موثقة فقط"
  find /tmp -maxdepth 1 \( -name "deploy_*.sh" -o -name "patch_*.py" -o -name "peek_*.sh" -o -name "probe_*.py" -o -name "*.log" \) -mtime +7 -delete 2>/dev/null
  find "$LOGDIR" -name "*.log" -mtime +30 -delete 2>/dev/null
  DISK_PCT2=$(df / --output=pcent | tail -1 | tr -dc '0-9')
  if [ "$DISK_PCT2" -lt 85 ]; then
    fixed "نُظِّفت ملفات مؤقتة قديمة، القرص كان ${DISK_PCT}% وصار ${DISK_PCT2}%"
  else
    attn "القرص لا يزال ممتلئًا (${DISK_PCT2}%) بعد التنظيف الآمن — يحتاج مراجعة يدوية"
  fi
else
  log "✓ القرص ${DISK_PCT:-?}%"
fi

# 9) النسخة الاحتياطية اليومية (فحص فقط أنها ركضت حديثًا؛ لا تُنشأ نسخة موازية جديدة)
LATEST_BAK=$(ls -1t /opt/legalmind-data/backups/pg/legalmind_*.dump* 2>/dev/null | head -1)
if [ -n "$LATEST_BAK" ]; then
  AGE_H=$(( ( $(date +%s) - $(stat -c %Y "$LATEST_BAK") ) / 3600 ))
  if [ "$AGE_H" -le 26 ]; then
    log "✓ آخر نسخة احتياطية عمرها ${AGE_H} ساعة"
  else
    log "آخر نسخة احتياطية عمرها ${AGE_H} ساعة — محاولة تشغيل يدوي"
    if bash /opt/LegalMind/tools/daily_backup.sh >>"$LOG" 2>&1; then
      fixed "شُغِّلت نسخة احتياطية يدويًا بعد تأخر الجدولة (${AGE_H} ساعة)"
    else
      attn "فشل تشغيل النسخة الاحتياطية يدويًا — يحتاج تشخيصًا"
    fi
  fi
else
  attn "لا توجد أي نسخة احتياطية على الإطلاق — يحتاج مراجعة عاجلة"
fi

# 10) مسح أنماط الأخطاء في يوميات آخر 24 ساعة (تقرير معلوماتي فقط)
for pat in "audit-error" "gap-search-error" "crosscheck-error" "email-error" "evidence-error" "attrib-error"; do
  N=$(journalctl -u legalmind-admin --since "24 hours ago" 2>/dev/null | grep -c "\[draft\] $pat" 2>/dev/null)
  N=${N:-0}
  if [ "$N" -gt 0 ] 2>/dev/null; then
    log "ℹ نمط $pat: $N مرة في آخر 24 ساعة (معلوماتي)"
  fi
done

# 11) وحدات systemd الفاشلة غير المتوقعة
FAILED_UNITS=$(systemctl --failed --plain --no-legend 2>/dev/null | awk '{print $1}')
if [ -n "$FAILED_UNITS" ]; then
  attn "وحدات systemd فاشلة: $FAILED_UNITS"
fi

FIXED_N=$(wc -l < "$FIXED_FILE")
ATTN_N=$(wc -l < "$ATTN_FILE")
log "=== النهاية: ${FIXED_N} إصلاح آلي، ${ATTN_N} بند يحتاج انتباهًا ==="

# --- الإخطار: فقط عند وجود إصلاح أو بند يحتاج انتباهًا (لا بريد يومي عند السلامة التامة) ---
if [ "$FIXED_N" -gt 0 ] || [ "$ATTN_N" -gt 0 ]; then
  {
    echo "تقرير المراجعة الصحية اليومية — $STAMP"
    echo ""
    if [ "$FIXED_N" -gt 0 ]; then
      echo "إصلاحات آلية تمت:"
      sed 's/^/  • /' "$FIXED_FILE"
      echo ""
    fi
    if [ "$ATTN_N" -gt 0 ]; then
      echo "بنود تحتاج مراجعة (لم تُصلَح آليًا عمدًا — تحتاج حكمًا لا رقعة ميكانيكية):"
      sed 's/^/  • /' "$ATTN_FILE"
    fi
  } > /tmp/hc_email_body_${STAMP}.txt
  /opt/LegalMind/admin/.venv/bin/python3 -c "
import sys
sys.path.insert(0, '/opt/LegalMind')
from admin.support_api import _send_notification_email
body = open('/tmp/hc_email_body_${STAMP}.txt', encoding='utf-8').read()
_send_notification_email('نظام LegalMind — مراجعة صحية يومية', 'healthcheck-daily', body)
print('EMAIL_SENT_ATTEMPT')
" >>"$LOG" 2>&1
  rm -f /tmp/hc_email_body_${STAMP}.txt
fi

exit 0
