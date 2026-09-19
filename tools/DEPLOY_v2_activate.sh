#!/bin/bash
# DEPLOY_v2_activate — لا يُشغَّل إلا بعد RETRIEVAL_V2_READY.
# التفعيل بالانضباط المعتمد في المشروع: نسخة احتياطية ← ضبط العلم ←
# بطاريتان متتاليتان ← إعادة تشغيل ← تحقق حي. وأي فشل يتراجع تلقائيًا.
set -u
cd /opt/LegalMind || exit 1
TS=$(date +%s)
cp deploy/.env "deploy/.env.bak_v2_$TS" || exit 1
echo "نسخة احتياطية: deploy/.env.bak_v2_$TS"

grep -q '^LEGALMIND_RETRIEVAL_V2=' deploy/.env \
  && sed -i 's/^LEGALMIND_RETRIEVAL_V2=.*/LEGALMIND_RETRIEVAL_V2=1/' deploy/.env \
  || echo 'LEGALMIND_RETRIEVAL_V2=1' >> deploy/.env
echo "العلم مضبوط. تشغيل بطاريتين متتاليتين..."

set -a; . deploy/.env; set +a
PASS=0
for i in 1 2; do
  if /opt/LegalMind/admin/.venv/bin/python tools/battery_run.py 2>&1 | tee "/tmp/bat_v2_$i.log" \
     | grep -q BATTERY_PASS; then
    echo "  بطارية $i: PASS"; PASS=$((PASS+1))
  else
    echo "  بطارية $i: FAIL"; break
  fi
done

if [ "$PASS" -ne 2 ]; then
  cp "deploy/.env.bak_v2_$TS" deploy/.env
  echo "ROLLED_BACK — البطاريتان لم تنجحا؛ أُعيد .env كما كان ولم يُفعَّل شيء."
  exit 1
fi

systemctl restart legalmind-admin
sleep 3
CODE=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8088/api/whoami)
if [ "$CODE" != "401" ]; then
  cp "deploy/.env.bak_v2_$TS" deploy/.env
  systemctl restart legalmind-admin
  echo "ROLLED_BACK — whoami=$CODE بدل 401."
  exit 1
fi
echo "DONE_V2_ACTIVE — العلم مفعَّل، بطاريتان 13/13، whoami=401."
echo "للتراجع في أي وقت:  cp deploy/.env.bak_v2_$TS deploy/.env && systemctl restart legalmind-admin"
