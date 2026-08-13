#!/bin/bash
# الحذف النهائي للمحاولة القديمة (/opt/legalmind-api + بوستغرس المضيف) بعد نسخ احتياطي
set -e
BK=/root/old-system-final-backup-20260813
mkdir -p "$BK"

echo "===== المساحة قبل ====="
df -h / | tail -1

echo ""
echo "===== ضمانة السلامة: النظام الحالي لا يعتمد على بوستغرس المضيف ====="
CUR_DB=$(grep -h "DATABASE_URL" /opt/LegalMind/deploy/.env /opt/LegalMind/deploy/admin.env 2>/dev/null | head -2 | sed 's/:[^:@\/]*@/:****@/')
echo "$CUR_DB"
if echo "$CUR_DB" | grep -q "5433"; then
  echo "تحذير: النظام الحالي يشير إلى منفذ 5433 — إيقاف فوري دون حذف!"
  exit 1
fi
echo "النظام الحالي على حاوية دوكر (55432) ✓"

echo ""
echo "===== 1) تشغيل بوستغرس المضيف مؤقتاً لأخذ النسخ الاحتياطية ====="
systemctl start postgresql 2>/dev/null || true
sleep 5
DBS=$(sudo -u postgres psql -Atc "SELECT datname FROM pg_database WHERE NOT datistemplate AND datname NOT IN ('postgres');" 2>/dev/null || echo "")
echo "قواعد بوستغرس المضيف: $DBS"
if [ -z "$DBS" ]; then
  echo "تعذر الوصول لبوستغرس المضيف — لن أحذفه دون نسخة. أوقف التنفيذ."
  exit 1
fi
for db in $DBS; do
  echo "نسخ $db (مضغوط)..."
  sudo -u postgres pg_dump -Fc "$db" > "$BK/$db.dump"
  ls -lh "$BK/$db.dump"
done
for db in $DBS; do
  [ -s "$BK/$db.dump" ] || { echo "نسخة $db فارغة — إيقاف دون حذف!"; exit 1; }
done
echo "النسخ سليمة ✓"

echo ""
echo "===== 2) إيقاف بوستغرس المضيف وإزالته ====="
systemctl stop postgresql || true
systemctl disable postgresql 2>/dev/null || true
apt-get purge -y 'postgresql*' > /dev/null 2>&1 || apt-get purge -y postgresql postgresql-16 postgresql-common > /dev/null 2>&1 || true
apt-get autoremove -y > /dev/null 2>&1 || true
rm -rf /var/lib/postgresql /etc/postgresql /var/log/postgresql
echo "أُزيل بوستغرس المضيف ✓"

echo ""
echo "===== 3) حذف ملفات النظام القديم ====="
for d in /opt/legalmind-api /var/www/legalmind; do
  if [ -d "$d" ]; then
    du -sh "$d"
    rm -rf "$d"
    echo "حُذف: $d ✓"
  else
    echo "$d غير موجود (ربما حُذف سابقاً)"
  fi
done
for u in $(systemctl list-unit-files --no-legend 2>/dev/null | awk '{print $1}' | grep -E '^legalmind-api' || true); do
  systemctl stop "$u" 2>/dev/null || true
  systemctl disable "$u" 2>/dev/null || true
  rm -f "/etc/systemd/system/$u"
  echo "أُزيلت الخدمة: $u"
done
systemctl daemon-reload

echo ""
echo "===== 4) التأكد من سلامة النظام الحالي ====="
systemctl is-active legalmind-admin legalmind-ingest docker
docker ps --format '{{.Names}} | {{.Status}}' | grep -Ei 'legalmind|qdrant'
curl -s -o /dev/null -w "لوحة الإدارة محلياً: %{http_code}\n" http://127.0.0.1:8088/ || true

echo ""
echo "===== المساحة بعد ====="
df -h / | tail -1
echo ""
echo "النسخ الاحتياطية محفوظة في: $BK (احذفها يدوياً بعد شهر إن لم تحتجها)"
echo "===== اكتمل الحذف النهائي ====="
