#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نشرُ التصحيحات النصّية المستهدَفة + فهرسةٌ موضعيّة (لا reindex كامل).
معاينةٌ أوّلًا فتُقرأ المواضعُ بسياقها، ثمّ تطبيقٌ، ثمّ إعادةُ فهرسة الكائنات المعدَّلة وحدَها عبر
`/opt/LegalMind/engine/reindex_one_cli.py` (غيرُ هدّامة: تستبدل نقطةً واحدة ولا تلمس المجموعة)،
ثمّ تحقّقٌ من أنّ اللا-كلمة اختفت من القاعدة."""
import base64, gzip, hashlib, pathlib, subprocess

H = pathlib.Path(__file__).parent
FIX = (H / "fix_texts.py").read_text(encoding="utf-8")
b_fix = base64.b64encode(gzip.compress(FIX.encode(), 9)).decode()
s_fix = hashlib.sha256(FIX.encode()).hexdigest()

SH = f"""#!/usr/bin/env bash
set -euo pipefail
PYA=/opt/LegalMind/admin/.venv/bin/python
PYE=/opt/LegalMind/.venv/bin/python
TMP=/tmp/fixtexts; mkdir -p "$TMP"
printf '%s' '{b_fix}' | base64 -d | gunzip > "$TMP/fix_texts.py"
echo "== SHA256 =="; echo "fix: {s_fix}"; sha256sum "$TMP/fix_texts.py"
"$PYA" -c "import ast; ast.parse(open('$TMP/fix_texts.py',encoding='utf-8').read()); print('OK')"
echo
echo "===================== معاينة (لا يُكتب شيء) ====================="
"$PYA" "$TMP/fix_texts.py"
echo
echo "===================== تطبيق ====================="
"$PYA" "$TMP/fix_texts.py" --apply | tee "$TMP/out.txt"
IDS=$(grep '^IDS=' "$TMP/out.txt" | sed 's/^IDS=//' || true)
if [ -z "$IDS" ]; then echo "لا كائناتٍ معدَّلة — لا فهرسة."; else
  echo
  echo "===================== فهرسةٌ موضعيّة ====================="
  for oid in $IDS; do
    echo -n "  $oid ⇐ "
    "$PYE" /opt/LegalMind/engine/reindex_one_cli.py "$oid"
  done
fi
echo
echo "===================== تحقّق ====================="
"$PYA" - <<'PY2'
import os, psycopg
dsn = os.getenv('DATABASE_URL') or 'postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind'
with psycopg.connect(dsn) as cx, cx.cursor() as cur:
    for oid, bad, good in (("legis-5-1959-m14", "بعد اموت", "بعد الموت"),
                           ("legis-20-1981-m2", "الأخر", "الآخر")):
        cur.execute("SELECT original_text, normalized_text FROM knowledge_objects WHERE id=%s", (oid,))
        o, n = cur.fetchone()
        assert bad not in o, "%s: اللا-كلمة «%s» ما زالت في النصّ الأصليّ"%(oid, bad)
        assert good in o, "%s: الصوابُ «%s» غيرُ موجود"%(oid, good)
        assert bad not in (n or ""), "%s: اللا-كلمة باقيةٌ في النصّ المُطبَّع"%oid
        i = o.find(good)
        print("  ✓ %-22s …%s…" % (oid, o[max(0,i-55):i+len(good)+55].replace(chr(10)," ")))
print("  === تمّ: النصّان مصحَّحان في الأصليّ والمُطبَّع معًا =====")
PY2
echo '=== تم: تصحيحان نصّيّان + فهرسةٌ موضعيّة (بلا reindex كامل) ==='
"""

(H / "run_fixtexts.sh").write_text(SH, encoding="utf-8")
one = ("printf '%s' '" + base64.b64encode(gzip.compress(SH.encode(), 9)).decode() +
       "' | base64 -d | gunzip > run_fixtexts.sh && bash run_fixtexts.sh")
(H / "DEPLOY_fixtexts.txt").write_text(one + "\n", encoding="utf-8")
assert gzip.decompress(base64.b64decode(one.split("'")[3])) == SH.encode(), "round-trip mismatch!"
print("round-trip OK")
r = subprocess.run(["bash", "-n", str(H / "run_fixtexts.sh")], capture_output=True, text=True)
print("bash -n:", "OK" if r.returncode == 0 else r.stderr)
print("one-liner bytes:", len(one))
