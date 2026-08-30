#!/usr/bin/env bash
set -uo pipefail
TMP=/tmp/tijari_deploy
declare -A EXP
EXP[01]="140000 176520a60cb90ae421e365106b7028fc8c513c8202a7cf4955c4a0062f2f3c19"
EXP[02]="140000 1e14683ce5e42c7788446c543ab93f2a53b27a0ab65384e05729d301e16f5dcb"
EXP[03]="140000 19d6f702a39a1dcef6a5de4a8e11c51eb5dbbd6928cefd51027e3c0f04d96b15"
EXP[04]="140000 341194c1b5b917999f2b1e81c25f0722c56cfcfbbc7bb6d5d33bd15efd623860"
EXP[05]="140000 85150a98c2d8d9eff0239173c416818a706839839cd8db8c55ef3f8cb74b83f1"
EXP[06]="140000 9c89a7d23704ce7ef7fd89fa1a85d4809f4f972a32de18bfda0714d05a5bf543"
EXP[07]="140000 4a8c291c2fe2979e598a33ef00e99b3e35966f77207ffcda169a0f0aae75bfb1"
EXP[08]="140000 f5368d2edd41642683b65b0abb1df7556f0ea37438a7e1b1daac4ac82de6da5d"
EXP[09]="140000 9b2acbaeccad3029ca8451ceb8e7809ac2438e74b70153c12c85d9f8edf276b0"
EXP[10]="140000 997f2a1e446774309ba93d66adcc26290507d07f686b3890ff2e064eabec5d40"
EXP[11]="140000 2eac0289195c64c4b5ee84d617da4e31644e328734524813d50cfda7f8a33d3a"
EXP[12]="140000 20c7f3dfbd742e24871ce281796ebf0a04e3d599f518f0cb11c8604e423cd6f7"
EXP[13]="140000 429895d291bf3e947bcbb995486e9f64f7bba5ccfad5ff556f6663a99a49d135"
EXP[14]="140000 28d7a24392384075e6947586f9f06d51aefc88e076512a39699f2d4d70dbe476"
EXP[15]="140000 af61fe1979d2721a18ac0437054e227a19c11817108700933f12df5dd74f2272"
EXP[16]="140000 670c6ef91bdbc49bc9ebf57595f1a56e36165b32e34548d443e2d834f993abe8"
EXP[17]="140000 ccfe368951a4cd470bb439272200d435382473cf4f5d853766b659b1dafc8cb2"
EXP[18]="131480 0c9881df7d78f75a3f207b375e56228300498d14457864ef9221ff2ec8148c56"
echo "== تشخيص أجزاء tijari =="
bad=0
for i in $(seq -w 1 18); do
  f="$TMP/p$i"
  read -r esz esh <<< "${EXP[$i]}"
  if [ ! -s "$f" ]; then echo "p$i: مفقود ✗ — الصق DEPLOY_tijari_part$i.txt"; bad=1; continue; fi
  sz=$(wc -c < "$f"); sh=$(sha256sum "$f" | cut -d' ' -f1)
  if [ "$sz" != "$esz" ] || [ "$sh" != "$esh" ]; then
    echo "p$i: تالف ✗ (الحجم $sz والمتوقع $esz) — أعد لصق DEPLOY_tijari_part$i.txt"; bad=1
  else
    echo "p$i: سليم ✓ ($sz بايت)"
  fi
done
[ $bad -eq 1 ] && { echo; echo "== النتيجة: أعد لصق الأجزاء المعلَّمة ✗ ثم أعد هذا الفحص =="; exit 0; }
cat $(for i in $(seq -w 1 18); do echo "$TMP/p$i"; done) > "$TMP/all.b64"
echo "بصمة الكل: $(sha256sum "$TMP/all.b64" | cut -d' ' -f1)"
echo "المتوقعة  : cb103fb07dd8b5df8226fc3c876fbbe7b9353aa7f1726096aced10615f78ec3e"
if [ "$(sha256sum "$TMP/all.b64" | cut -d' ' -f1)" != "cb103fb07dd8b5df8226fc3c876fbbe7b9353aa7f1726096aced10615f78ec3e" ]; then
  echo "✗ بصمة الكل مخالفة رغم سلامة الأجزاء — أرسل هذا الناتج"; exit 0
fi
base64 -d < "$TMP/all.b64" | gunzip > "$TMP/tijari_records.json" 2>"$TMP/err" || { echo "✗ فك الترميز فشل:"; cat "$TMP/err"; exit 0; }
echo "بصمة JSON: $(sha256sum "$TMP/tijari_records.json" | cut -d' ' -f1)"
echo "المتوقعة  : 731d9d1ce2d9d61ad0e7b0a42639d5a179560588748e1e0d79e821be698bf3ee"
if [ -r /opt/LegalMind/deploy/.env ]; then set -a; . /opt/LegalMind/deploy/.env; set +a; fi
PYA=/opt/LegalMind/admin/.venv/bin/python
[ -s "$TMP/ingest_tijari.py" ] && "$PYA" -c "import ast; ast.parse(open('$TMP/ingest_tijari.py',encoding='utf-8').read()); print('ingest: py OK')" || echo "ingest_tijari.py غير موجود بعد (تكتبه التشغيلة) — طبيعي"
"$PYA" -c "import os,psycopg; psycopg.connect(os.environ['DATABASE_URL']).close(); print('اتصال قاعدة البيانات ✓')" || echo "✗ فشل اتصال قاعدة البيانات"
df -h /tmp | tail -1
echo "== خلاصة: إن كانت كل الفحوص ✓ فأعد لصق DEPLOY_tijari_run_noidx.txt الآن =="
