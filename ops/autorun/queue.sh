#!/bin/bash
# أمر آلي 34: شامل — (أ) كود مستوى sub (idempotent) (ب) دمج CMA (ج) دمج عام لكل قانون له لائحة
#            (د) تصحيح فرع حماية المستهلك إلى مدني
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
PY=/opt/LegalMind/.venv/bin/python
$PY -c "import psycopg; print('psycopg متاح ✓')"

echo "===== (أ) كود المستوى الفرعي (sub) — idempotent =====" 
APP=/opt/LegalMind/admin/app.py
if grep -q 'sub: str = ""' "$APP"; then
  echo "المستوى الفرعي مركّب مسبقاً — تخطّي"
else
  cp -a "$APP" /root/app.py.bak-browse-sublevel2
  echo "نسخة احتياطية: /root/app.py.bak-browse-sublevel2"
  $PY - <<'PYEOF'
# -*- coding: utf-8 -*-
p = "/opt/LegalMind/admin/app.py"
src = open(p, encoding="utf-8").read()

OLD_SIG = '''def browse_kb(kind: str, b: str = "", t: str = "", group: str = "", part: str = "",
              _: str = Depends(require_auth)) -> dict:'''
NEW_SIG = '''def browse_kb(kind: str, b: str = "", t: str = "", group: str = "", part: str = "", sub: str = "",
              _: str = Depends(require_auth)) -> dict:'''
if OLD_SIG in src:
    src = src.replace(OLD_SIG, NEW_SIG, 1)

    OLD_BLOCK = '''            _prts = _cur.fetchall()
                if len(_prts) > 1:
                    return {"mode": "groups", "level": "part",
                            "groups": [{"key": r[0], "count": r[1]} for r in _prts]}
            _cond = ("AND " + PEXPR + " = %s ") if part else ""
            _args = tuple(types) + ((group, part) if part else (group,))
            _cur.execute(
                "SELECT id, title, branch, subtopic, micro_issue FROM knowledge_objects "
                "WHERE object_type IN (" + tph + ") "
                "AND " + GEXPR + " = %s " + _cond + "ORDER BY id LIMIT 3000",
                _args)
            return {"mode": "items", "items": [
                {"id": r[0], "title": r[1], "branch": r[2], "subtopic": r[3], "micro_issue": r[4]}
                for r in _cur.fetchall()]}'''
    NEW_BLOCK = '''            _prts = _cur.fetchall()
                if len(_prts) > 1:
                    return {"mode": "groups", "level": "part",
                            "groups": [{"key": r[0], "count": r[1]} for r in _prts]}
            _cond = ("AND " + PEXPR + " = %s ") if part else ""
            _args = tuple(types) + ((group, part) if part else (group,))
            SUBEXPR = "NULLIF(metadata->>'doc_subpart','')"
            if not sub:
                _cur.execute(
                    "SELECT " + SUBEXPR + " AS sg, count(*), min(id) FROM knowledge_objects "
                    "WHERE object_type IN (" + tph + ") AND " + GEXPR + " = %s " + _cond +
                    "GROUP BY sg ORDER BY min(id)", _args)
                _subs = [r for r in _cur.fetchall() if r[0]]
                if len(_subs) > 1:
                    return {"mode": "groups", "level": "sub",
                            "groups": [{"key": r[0], "count": r[1]} for r in _subs]}
            _cond2 = _cond + ((" AND " + SUBEXPR + " = %s ") if sub else "")
            _args2 = _args + ((sub,) if sub else ())
            _cur.execute(
                "SELECT id, title, branch, subtopic, micro_issue FROM knowledge_objects "
                "WHERE object_type IN (" + tph + ") "
                "AND " + GEXPR + " = %s " + _cond2 + "ORDER BY id LIMIT 3000",
                _args2)
            return {"mode": "items", "items": [
                {"id": r[0], "title": r[1], "branch": r[2], "subtopic": r[3], "micro_issue": r[4]}
                for r in _cur.fetchall()]}'''
    assert OLD_BLOCK in src, "لم أجد كتلة العرض المتوقعة"
    src = src.replace(OLD_BLOCK, NEW_BLOCK, 1)
    open(p, "w", encoding="utf-8").write(src)
    print("رُكِّب مستوى sub ✓")
else:
    print("توقيع الدالة مختلف عن المتوقع — تخطّي التعديل البرمجي بأمان")
PYEOF
  $PY -m py_compile "$APP" && echo "الكود سليم ✓" || { cp -a /root/app.py.bak-browse-sublevel2 "$APP"; echo "استُرجعت النسخة السابقة"; exit 1; }
  systemctl restart legalmind-admin
  sleep 3
  systemctl is-active legalmind-admin && echo "الخدمة تعمل ✓"
fi

echo ""
echo "===== (ب+ج) دمج عام لكل زوج (قانون + لائحته التنفيذية) في النظام + حالة أسواق المال =====" 
$PY - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys, re
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng

LAW_TYPES = ('legislation', 'legislation_article', 'legislation_issuing_article', 'legislation_preamble')
GEXPR = ("COALESCE(metadata->>'library_group', substring(id from '^(legis-[a-z0-9]+-[0-9]+)'), "
         "substring(id from '^(lreg-[0-9]+-[0-9]+-k[0-9]+)'), "
         "substring(id from '^(regl-[0-9]+-[0-9]+)'), "
         "substring(id from '^(reg-[0-9]+-[0-9]+)'))")

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()
    ph = ",".join(["%s"] * len(LAW_TYPES))

    # 1) تثبيت حالة أسواق المال (في حال لم يُنفَّذ الأمر السابق) — عملية آمنة للتكرار
    cur.execute(f"""SELECT {GEXPR} AS g, count(*) FROM knowledge_objects
                    WHERE object_type IN ({ph}) AND branch='تجاري'
                      AND (coalesce(metadata->>'library_card_name','') ILIKE '%%هيئة أسواق المال%%'
                           OR metadata->>'library_group' LIKE 'cma-book-%%')
                      AND coalesce(metadata->>'library_group','') <> 'cma-authority-unified'
                    GROUP BY g""", LAW_TYPES)
    stale = cur.fetchall()
    if stale:
        print("توحيد أسواق المال لم يكتمل من قبل — إكماله الآن:", stale, flush=True)
        cur.execute(f"""SELECT {GEXPR} AS g, count(*) FROM knowledge_objects
                        WHERE object_type IN ({ph}) AND branch='تجاري'
                          AND coalesce(metadata->>'library_card_name','') ILIKE '%%هيئة أسواق المال%%'
                          AND coalesce(metadata->>'doc_part','') = ''
                        GROUP BY g ORDER BY count(*) DESC LIMIT 1""", LAW_TYPES)
        base = cur.fetchone()
        if base and base[0]:
            cur.execute(f"""UPDATE knowledge_objects
                            SET metadata = metadata || '{{"library_group":"cma-authority-unified",
                                  "library_card_name":"هيئة أسواق المال","doc_part":"القانون"}}'::jsonb
                            WHERE object_type IN ({ph}) AND {GEXPR} = %s""", LAW_TYPES + (base[0],))
            print("  أُصلح القانون الأساسي:", cur.rowcount, flush=True)
        cur.execute(f"""SELECT DISTINCT metadata->>'library_group', metadata->>'library_card_name'
                        FROM knowledge_objects WHERE metadata->>'library_group' LIKE 'cma-book-%%'""")
        for lg, cn in cur.fetchall():
            subname = (cn or lg).replace("اللائحة التنفيذية — ", "").strip()
            cur.execute(f"""UPDATE knowledge_objects
                            SET metadata = metadata || jsonb_build_object(
                                  'library_group','cma-authority-unified','library_card_name','هيئة أسواق المال',
                                  'doc_part','اللائحة التنفيذية','doc_subpart',%s::text)
                            WHERE metadata->>'library_group' = %s""", (subname, lg))
        print("  اكتمل توحيد أسواق المال ✓", flush=True)
    else:
        print("أسواق المال موحَّدة بالفعل ✓", flush=True)

    # 2) كشف عام: كل بطاقات القوانين الحالية بأسمائها وأعدادها
    cur.execute(f"""SELECT {GEXPR} AS g, count(*), min(metadata->>'library_card_name'),
                          min(title) FILTER (WHERE metadata->>'library_card_name' IS NULL)
                    FROM knowledge_objects WHERE object_type IN ({ph})
                    GROUP BY g HAVING g IS NOT NULL""", LAW_TYPES)
    all_groups = cur.fetchall()
    print("\nإجمالي بطاقات القوانين الحالية في النظام:", len(all_groups), flush=True)

    # اسم فعلي لكل مجموعة (card_name أو مشتق من العنوان)
    def name_of(row):
        g, c, cname, ttl = row
        if cname:
            return cname
        if ttl and "—" in ttl:
            return ttl.split("—")[-1].strip()
        return ttl or g

    named = [(g, c, name_of(r)) for r, g, c in [(r, r[0], r[1]) for r in all_groups]]
    # إعادة بناء القائمة بشكل صريح (تفادي التباس أعلاه)
    named = []
    for r in all_groups:
        g, c, cname, ttl = r
        named.append((g, c, name_of(r)))

    LAW_RE = re.compile(r"(?:رقم\s*)?(\d+)\s*/\s*(\d{4})")
    is_bylaw_word = ("اللائحة التنفيذية", "لائحته التنفيذية")

    laws, bylaws = {}, []
    for g, c, name in named:
        if any(w in name for w in is_bylaw_word) and not name.startswith("هيئة"):
            bylaws.append((g, c, name))
        else:
            m = LAW_RE.search(name)
            if m:
                key = m.group(1) + "/" + m.group(2)
                laws.setdefault(key, []).append((g, c, name))

    print("\nقوانين لها رقم واضح:", len(laws), "| بطاقات لائحة منفصلة محتملة:", len(bylaws), flush=True)

    merged_pairs = 0
    for bg, bc, bname in bylaws:
        m = LAW_RE.search(bname)
        if not m:
            continue
        key = m.group(1) + "/" + m.group(2)
        cands = laws.get(key)
        if not cands:
            continue
        # القانون الأصلي = أكبر مجموعة تطابق نفس الرقم وليست هي نفسها بطاقة اللائحة
        lg, lc, lname = max(cands, key=lambda x: x[1])
        if lg == bg:
            continue
        clean_name = re.sub(r"^(اللائحة التنفيذية.*?بشأن\s*|قانون\s*)", "", lname).strip()
        display = lname if lname.startswith("قانون") else ("قانون " + clean_name)
        print("  دمج: '%s' (قانون %d) + '%s' (لائحة %d) -> '%s'" %
              (lname[:35], lc, bname[:35], bc, display[:40]), flush=True)
        cur.execute(f"""UPDATE knowledge_objects
                        SET metadata = metadata || jsonb_build_object(
                              'library_group', %s::text, 'library_card_name', %s::text, 'doc_part','القانون')
                        WHERE object_type IN ({ph}) AND {GEXPR} = %s""",
                    (lg, display, *LAW_TYPES, lg))
        cur.execute(f"""UPDATE knowledge_objects
                        SET metadata = metadata || jsonb_build_object(
                              'library_group', %s::text, 'library_card_name', %s::text, 'doc_part','اللائحة التنفيذية')
                        WHERE object_type IN ({ph}) AND {GEXPR} = %s""",
                    (lg, display, *LAW_TYPES, bg))
        merged_pairs += 1
    print("\nإجمالي الأزواج المدموجة:", merged_pairs, flush=True)

    # 3) تصحيح فرع حماية المستهلك إلى مدني
    print("\n== تصحيح فرع حماية المستهلك ==", flush=True)
    cur.execute(f"""UPDATE knowledge_objects SET branch='مدني', updated_at=now()
                    WHERE object_type IN ({ph})
                      AND (title ILIKE '%%حماية المستهلك%%' OR metadata->>'title' ILIKE '%%حماية المستهلك%%')""", LAW_TYPES)
    print("عُدِّل فرع", cur.rowcount, "كائن من 'تجاري' إلى 'مدني'", flush=True)

    # 4) التحقق النهائي
    print("\n== التحقق النهائي: بطاقات القوانين الآن حسب الفرع ==", flush=True)
    cur.execute(f"""SELECT branch, count(DISTINCT {GEXPR}) FROM knowledge_objects
                    WHERE object_type IN ({ph}) GROUP BY branch ORDER BY 2 DESC""", LAW_TYPES)
    for b, c in cur.fetchall():
        print("  فرع '%s': %d بطاقة" % (b, c), flush=True)
PYEOF
echo ""
echo "===== اكتمل الأمر الشامل ====="
