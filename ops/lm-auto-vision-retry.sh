#!/bin/bash
# النص المقسم الرديء يعيد نفسه للرؤية تلقائيا (سد ثغرة القانون البحري نهائيا)
set -e
python3 - <<'PYEOF'
p = "/opt/LegalMind/engine/claude_reader.py"
src = open(p, encoding="utf-8").read()
if "النص المقسم رديء" in src:
    print("المنعكس مركب مسبقا — لا تغيير")
else:
    OLD = '''                merged = _merge_part(merged, r, k)
            result = merged
        else:'''
    NEW = '''                merged = _merge_part(merged, r, k)
            result = merged
            confs = [float(c.get("confidence", 0)) for c in (result.get("chunks") or [])] or [0]
            avg = sum(confs) / len(confs)
            if path.suffix.lower() == ".pdf" and (result.get("reading_quality") == "partial" or avg < 0.65):
                print("[claude_reader] النص المقسم رديء (متوسط الثقة %.2f) — إعادة القراءة بالرؤية" % avg, flush=True)
                text = None
        else:'''
    assert OLD in src, "!! النمط غير مطابق — أخبر كلود"
    src = src.replace(OLD, NEW, 1)
    open(p, "w", encoding="utf-8").write(src)
    print("زُرع منعكس الشفاء الذاتي ✓")
PYEOF
/opt/LegalMind/.venv/bin/python -m py_compile /opt/LegalMind/engine/claude_reader.py
systemctl restart legalmind-ingest
systemctl is-active legalmind-ingest
echo "تم — أي ملف طويل رديء النص سيعيد نفسه للرؤية تلقائيا من الآن"
