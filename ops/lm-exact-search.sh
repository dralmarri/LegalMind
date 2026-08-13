#!/bin/bash
# إضافة مسار «المطابقة المباشرة» إلى /api/search: مادة + رقم + قانون → النص الحرفي أولاً
set -e
APP=/opt/LegalMind/admin/app.py
cp -a "$APP" /root/app.py.bak-exact-search
echo "نسخة احتياطية: /root/app.py.bak-exact-search"

python3 - <<'PYEOF'
# -*- coding: utf-8 -*-
p = "/opt/LegalMind/admin/app.py"
src = open(p, encoding="utf-8").read()

HELPER = '''
_AR_DIGITS_MAP = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_ART_STOPWORDS = {"المادة", "مادة", "رقم", "من", "في", "نص", "ما", "هي", "هو",
                  "قانون", "القانون", "لائحة", "اللائحة", "مرسوم", "المرسوم",
                  "بقانون", "لسنة", "سنة", "و", "او", "أو", "على", "عن", "عند"}


def _exact_article_results(q: str, branch: str = "") -> list:
    """مطابقة مباشرة: «مادة + رقم (+ اسم قانون)» → النص الحرفي من القاعدة."""
    import re as _re
    qn = (q or "").translate(_AR_DIGITS_MAP)
    m = _re.search(r"(?:ال)?مادة\\s*\\(?\\s*(\\d+)", qn)
    if not m:
        return []
    num = m.group(1)
    pat = r"(^|[^0-9])" + num + r"([^0-9]|$)"
    sql = """SELECT id, object_type, branch, topic, subtopic, micro_issue, title,
                    original_text, source_key, verification_status, authority_status,
                    usable_as_citation, coalesce(metadata->>'publication','') AS publication
             FROM knowledge_objects
             WHERE title ILIKE %s AND title ~ %s"""
    args = ["%مادة " + num + "%", pat]
    if branch:
        sql += " AND branch = %s"
        args.append(branch)
    sql += " LIMIT 40"
    try:
        rows = db_rows(sql, tuple(args))
    except Exception:
        return []
    toks = [w.strip("()؟?.,:؛«»\\"'") for w in _re.split(r"\\s+", qn) if w.strip()]
    law_toks = []
    for w in toks:
        if w in _ART_STOPWORDS or w.isdigit():
            continue
        w2 = w.lstrip("ال")
        if len(w2) >= 3:
            law_toks.append(w2)
    scored = []
    for r in rows:
        hay = " ".join([r["title"] or "", r["publication"] or "",
                        r["topic"] or "", r["subtopic"] or ""])
        n = sum(1 for t in law_toks if t in hay)
        if law_toks and n == 0:
            continue
        scored.append((n, r))
    scored.sort(key=lambda x: -x[0])
    out = []
    for _, r in scored[:3]:
        out.append({
            "score": 1.0, "match_type": "exact",
            "object_id": r["id"], "object_type": r["object_type"],
            "branch": r["branch"], "topic": r["topic"],
            "subtopic": r["subtopic"], "micro_issue": r["micro_issue"],
            "title": r["title"], "text": r["original_text"],
            "source_key": r["source_key"],
            "verification_status": r["verification_status"],
            "authority_status": r["authority_status"],
            "usable_as_citation": r["usable_as_citation"],
        })
    return out


'''

ANCHOR = '@app.get("/api/search")'
assert ANCHOR in src, "لم أجد نقطة الإدراج"
assert "_exact_article_results" not in src, "الإصلاح مركب مسبقاً"
src = src.replace(ANCHOR, HELPER + ANCHOR, 1)

OLD1 = '''    hits = _qdrant_search(vector, limit, flt)
    if not hits:
        return {"query": q, "count": 0, "results": []}'''
NEW1 = '''    exact = _exact_article_results(q, branch.strip())
    hits = _qdrant_search(vector, limit, flt)
    if not hits and not exact:
        return {"query": q, "count": 0, "results": []}'''
assert OLD1 in src, "لم أجد كتلة البحث"
src = src.replace(OLD1, NEW1, 1)

OLD2 = '''    by_id = {r["id"]: r for r in rows}
    results = []'''
NEW2 = '''    by_id = {r["id"]: r for r in rows}
    exact_ids = {e["object_id"] for e in exact}
    results = list(exact)'''
assert OLD2 in src, "لم أجد كتلة النتائج"
src = src.replace(OLD2, NEW2, 1)

OLD3 = '''        row = by_id.get(oid)
        if not row:
            continue'''
NEW3 = '''        row = by_id.get(oid)
        if not row or oid in exact_ids:
            continue'''
assert OLD3 in src, "لم أجد كتلة الترشيح"
src = src.replace(OLD3, NEW3, 1)

open(p, "w", encoding="utf-8").write(src)
print("رُكب مسار المطابقة المباشرة ✓")
PYEOF

/opt/LegalMind/.venv/bin/python -m py_compile "$APP" && echo "الكود سليم ✓"
systemctl restart legalmind-admin
sleep 3
systemctl is-active legalmind-admin && echo "الخدمة تعمل ✓"

echo ""
echo "== اختبار حي =="
PW=$(cat /root/legalmind-admin-password.txt 2>/dev/null | tail -1 | awk '{print $NF}')
curl -s -c /tmp/lmck -X POST http://127.0.0.1:8088/api/login \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"dralmarri\",\"password\":\"$PW\"}" > /tmp/lmlogin.json
if grep -q '"ok"\|lm_session' /tmp/lmck /tmp/lmlogin.json 2>/dev/null; then
  curl -s -b /tmp/lmck -G "http://127.0.0.1:8088/api/search" \
    --data-urlencode "q=المادة ٣٥ من قانون الشركات" --data-urlencode "limit=5" | \
    python3 -c "
import json, sys
d = json.load(sys.stdin)
for r in d.get('results', [])[:5]:
    print(' %.2f | %s | %s' % (r['score'], r.get('match_type', 'دلالي'), r['title'][:60]))
"
else
  echo "تعذر الدخول الآلي للاختبار — جرّب من التطبيق مباشرة: «المادة ٣٥ من قانون الشركات»"
fi
rm -f /tmp/lmck /tmp/lmlogin.json
echo "===== اكتمل التركيب ====="
