#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════
# DEPLOY_srcnote_display.sh — طبقة إظهار metadata.source_note
#   في سياق استوديو الصياغة (admin/app.py) وفي أدوات MCP (mcp/server.py) معًا.
#
# يمسّ **كود الإنتاج الحي**، فالانضباط كامل:
#   نسخة احتياطية ← رقعة بمراسٍ «مرة واحدة بالضبط» ← فحص نحوي ← إعادة تشغيل
#   الخدمتين ← فحوص حياة ← مسبار حي يثبت ظهور التنبيه فعلًا ← **بطاريتان
#   متتاليتان** ← و**تراجع آلي** يستعيد الملفين ويعيد تشغيل الخدمتين عند أي فشل.
#
# قيد بنيوي مقصود: ميزانية السياق تُحتسب على الكتلة **قبل** إلحاق التنبيه،
# فأثر الرقعة على الاسترجاع صفرٌ بنيويًا لا احتمالًا.
#
# النجاح النهائي = DONE_SRCNOTE
# ══════════════════════════════════════════════════════════════════════════
set -uo pipefail

SELF="${BASH_SOURCE[0]:-}"
if [ "${1:-}" != "--worker" ] && [ -n "$SELF" ] && [ -f "$SELF" ]; then
  LOG=/tmp/deploy_srcnote_$(date +%s).log
  echo "running in background (survives terminal disconnect). log: $LOG"
  nohup bash "$SELF" --worker > "$LOG" 2>&1 &
  disown
  echo "follow with:  tail -f $LOG"
  exit 0
fi
[ "${1:-}" = "--worker" ] || echo "(pasted mode: running in the foreground)"

cd /opt/LegalMind
set -a; . /opt/LegalMind/deploy/.env; set +a
mkdir -p /opt/LegalMind/tools /opt/legalmind-data

STAMP=$(date +%Y%m%d_%H%M%S)
SAFE=/opt/legalmind-data/srcnote_safe_$STAMP
mkdir -p "$SAFE"
cp -a /opt/LegalMind/admin/app.py   "$SAFE/app.py"
cp -a /opt/LegalMind/mcp/server.py  "$SAFE/server.py"
# النسخة الآمنة هي شرط التراجع نفسه — تُتحقق قبل أي لمس للكود
if [ ! -s "$SAFE/app.py" ] || [ ! -s "$SAFE/server.py" ]; then
  echo "BACKUP_EMPTY — لم تُنسخ الملفات، فلا تراجع ممكن. أوقفت الدفعة بلا أي تعديل."
  exit 1
fi
echo "النسخة الآمنة قبل أي لمس: $SAFE ($(wc -c < "$SAFE/app.py") + $(wc -c < "$SAFE/server.py") بايت)"

rollback() {
  echo
  echo "══════ تراجع آلي ══════"
  cp -a "$SAFE/app.py"  /opt/LegalMind/admin/app.py
  cp -a "$SAFE/server.py" /opt/LegalMind/mcp/server.py
  systemctl restart legalmind-admin legalmind-mcp 2>/dev/null
  sleep 3
  echo "استُعيد الملفان وأُعيد تشغيل الخدمتين."
  systemctl is-active legalmind-admin legalmind-mcp
  echo "ROLLED_BACK"
  exit 1
}

echo
echo "═══ 1) كتابة الباتشر ═══"
base64 -d <<'B64LM' | gunzip > /opt/LegalMind/tools/patch_source_note_display.py
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
AAA=
B64LM
python3 -c "import ast,io;ast.parse(io.open('/opt/LegalMind/tools/patch_source_note_display.py',encoding='utf-8').read());print('SYNTAX_OK')" || rollback

echo
echo "═══ 2) تطبيق الرقعة (مراسٍ مرة واحدة بالضبط) ═══"
python3 /opt/LegalMind/tools/patch_source_note_display.py || rollback

echo
echo "═══ 3) فحص نحوي للملفين بعد الرقعة ═══"
/opt/LegalMind/admin/.venv/bin/python -c "import ast,io;ast.parse(io.open('/opt/LegalMind/admin/app.py',encoding='utf-8').read());print('APP_SYNTAX_OK')" || rollback
/opt/LegalMind/admin/.venv/bin/python -c "import ast,io;ast.parse(io.open('/opt/LegalMind/mcp/server.py',encoding='utf-8').read());print('MCP_SYNTAX_OK')" || rollback

echo
echo "═══ 4) إعادة تشغيل الخدمتين وفحص الحياة ═══"
systemctl restart legalmind-admin legalmind-mcp || rollback
sleep 4
systemctl is-active legalmind-admin >/dev/null || { echo "ADMIN_DOWN"; rollback; }
systemctl is-active legalmind-mcp   >/dev/null || { echo "MCP_DOWN";   rollback; }
echo "الخدمتان تعملان."
CODE=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8088/api/whoami)
echo "/api/whoami = $CODE (المتوقع 401)"
[ "$CODE" = "401" ] || rollback

echo
echo "═══ 5) مسبار حي: هل يظهر التنبيه فعلًا؟ ═══"
/opt/LegalMind/admin/.venv/bin/python - <<'PYP' || rollback
import sys
sys.path.insert(0, "/opt/LegalMind"); sys.path.insert(0, "/opt/LegalMind/admin")
from admin import app
OID = "legis-7-2010-m114"
t = app._draft_fetch_texts({OID}).get(OID)
assert t, "لم تُجلب المادة"
note = (t.get("note") or "").strip()
print("  الاستوديو: طول الملاحظة المقروءة =", len(note))
assert note, "STUDIO_NOTE_EMPTY: الحقل لا يصل من القاعدة"
blk = '<مصدر نوع="تشريع" معرف="%s" عنوان="x">\n%s\n</مصدر>' % (OID, (t["text"] or "")[:200])
out = app._draft_with_note(blk, note)
assert "لا يُستشهد بها" in out and out.endswith("\n</مصدر>"), "STUDIO_RENDER_FAIL"
assert out.index("</مصدر>") > out.index("لا يُستشهد بها"), "التنبيه خارج الكتلة"
print("  الاستوديو: التنبيه داخل الكتلة قبل وسم الإغلاق ✓")
# حارس عدم المزاحمة: الكتلة بلا تنبيه هي ما تُحتسب عليه الميزانية
assert app._draft_with_note(blk, None) == blk, "NOOP_FAIL"
print("  الاستوديو: بلا ملاحظة الكتلة كما هي ✓")
print("STUDIO_PROBE_OK")
PYP

/opt/LegalMind/mcp/.venv/bin/python - <<'PYM' || rollback
import sys, importlib.util
sys.path.insert(0, "/opt/LegalMind")
spec = importlib.util.spec_from_file_location("lm_mcp", "/opt/LegalMind/mcp/server.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
out = m.get_object("legis-7-2010-m114")
assert "محكمة سوق المال" in out, "النص الأصلي غائب"
assert "لا يُستشهد بها" in out, "MCP_NOTE_MISSING: التنبيه لا يظهر في مخرج الأداة"
print("  MCP: get_object يعرض النص + التنبيه ✓ (الطول %d)" % len(out))
out2 = m.get_object("legis-49-2016-m62-mukarrar")
assert "لا يُستشهد بها" not in out2, "MCP_FALSE_NOTE: تنبيه ظهر بلا source_note"
print("  MCP: كائن بلا ملاحظة يخرج نظيفًا ✓")
print("MCP_PROBE_OK")
PYM

echo
echo "═══ 6) البطارية — جولة أولى ═══"
/opt/LegalMind/admin/.venv/bin/python /opt/LegalMind/tools/battery_run.py > /tmp/bat_srcnote_1.log 2>&1
tail -4 /tmp/bat_srcnote_1.log
grep -q "BATTERY_PASS" /tmp/bat_srcnote_1.log || {
  echo "الجولة الأولى لم تمر — تُعاد مرة واحدة قبل الحكم (بروتوكول الفشل المفرد)"
  /opt/LegalMind/admin/.venv/bin/python /opt/LegalMind/tools/battery_run.py > /tmp/bat_srcnote_1b.log 2>&1
  tail -4 /tmp/bat_srcnote_1b.log
  grep -q "BATTERY_PASS" /tmp/bat_srcnote_1b.log || { echo "BATTERY_FAIL_TWICE"; rollback; }
}

echo
echo "═══ 7) البطارية — جولة ثانية (الثبات شرط لا النجاح المفرد) ═══"
/opt/LegalMind/admin/.venv/bin/python /opt/LegalMind/tools/battery_run.py > /tmp/bat_srcnote_2.log 2>&1
tail -4 /tmp/bat_srcnote_2.log
grep -q "BATTERY_PASS" /tmp/bat_srcnote_2.log || {
  echo "الجولة الثانية لم تمر — تُعاد مرة واحدة"
  /opt/LegalMind/admin/.venv/bin/python /opt/LegalMind/tools/battery_run.py > /tmp/bat_srcnote_2b.log 2>&1
  tail -4 /tmp/bat_srcnote_2b.log
  grep -q "BATTERY_PASS" /tmp/bat_srcnote_2b.log || { echo "BATTERY_FAIL_TWICE"; rollback; }
}

echo
echo "═══ 8) تشخيص: كم ملاحظة صارت مرئية الآن (لا بوابة) ═══"
set +e
psql "$DATABASE_URL" -At -c "
  SELECT 'كائنات تحمل source_note = '||count(*) FROM knowledge_objects
    WHERE metadata ? 'source_note'
  UNION ALL SELECT '  منها تشريعات = '||count(*) FROM knowledge_objects
    WHERE metadata ? 'source_note' AND object_type LIKE 'legislation%';"

echo
echo "النسخة الآمنة محفوظة في: $SAFE"
echo "DONE_SRCNOTE"
