#!/bin/bash
# تدقيق المطابقة المباشرة: كلمات كاملة (مدني ≠ المدنية) + فرع القانون + الأدق فقط في الصدارة
set -e
APP=/opt/LegalMind/admin/app.py
cp -a "$APP" /root/app.py.bak-exact-search2

python3 - <<'PYEOF'
# -*- coding: utf-8 -*-
p = "/opt/LegalMind/admin/app.py"
src = open(p, encoding="utf-8").read()

OLD = '''    scored = []
    for r in rows:
        hay = " ".join([r["title"] or "", r["publication"] or "",
                        r["topic"] or "", r["subtopic"] or ""])
        n = sum(1 for t in law_toks if t in hay)
        if law_toks and n == 0:
            continue
        scored.append((n, r))
    scored.sort(key=lambda x: -x[0])'''

NEW = '''    def _wnorm(w):
        w = w.strip("()؟?.,:؛«»\\"'—-")
        for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ى", "ي"), ("ة", "ه")):
            w = w.replace(a, b)
        if w.startswith("ال") and len(w) > 4:
            w = w[2:]
        return w

    ntoks = [t for t in (_wnorm(x) for x in law_toks) if t]
    scored = []
    for r in rows:
        hay = " ".join([r["title"] or "", r["publication"] or "",
                        r["topic"] or "", r["subtopic"] or "", r["branch"] or ""])
        words = {_wnorm(w) for w in hay.split()}
        n = sum(1 for t in ntoks if t in words)
        if ntoks and n == 0:
            continue
        scored.append((n, r))
    scored.sort(key=lambda x: -x[0])
    if scored and ntoks:
        best = scored[0][0]
        scored = [s for s in scored if s[0] == best]'''

assert OLD in src, "لم أجد كتلة الترتيب الحالية"
src = src.replace(OLD, NEW, 1)
open(p, "w", encoding="utf-8").write(src)
print("دُقّقت المطابقة ✓")
PYEOF

/opt/LegalMind/.venv/bin/python -m py_compile "$APP" && echo "الكود سليم ✓"
systemctl restart legalmind-admin
sleep 3
systemctl is-active legalmind-admin && echo "الخدمة تعمل ✓"
echo "===== جرّب الآن: «المادة ٣٥ مدني» — يفترض ألا تتصدر إلا مادة القانون المدني ====="
