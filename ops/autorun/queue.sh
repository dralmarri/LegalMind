#!/bin/bash
# أمر آلي 33: (أ) توحيد بطاقة "هيئة أسواق المال" بمجلدين (القانون/اللائحة) وكتب فرعية داخل اللائحة
#            (ب) تعديل كود /api/browse لإضافة مستوى "sub" (نسخة احتياطية + فحص تركيبي قبل التطبيق)
#            (ج) فحص وجود بيانات "حماية المستهلك" ومعالجتها بنفس الطريقة إن وُجدت
#            (د) تسمية مبادئ هيئة أسواق المال تحت تبويب المبادئ والأحكام
set -e
set -a; source /opt/LegalMind/deploy/.env; set +a
PY=/opt/LegalMind/.venv/bin/python
$PY -c "import psycopg; print('psycopg متاح ✓')"

echo "===== (أ) البيانات: توحيد هيئة أسواق المال بمستويات القانون/اللائحة/الكتاب ====="
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

    cur.execute(f"""SELECT {GEXPR} AS g, count(*) FROM knowledge_objects
                    WHERE object_type IN ({ph}) AND branch='تجاري'
                      AND coalesce(metadata->>'library_card_name','') ILIKE '%%هيئة أسواق المال%%'
                    GROUP BY g ORDER BY count(*) DESC LIMIT 1""", LAW_TYPES)
    base_row = cur.fetchone()
    print("مجموعة قانون هيئة أسواق المال الأصلي:", base_row, flush=True)

    UNIFIED = "cma-authority-unified"
    if base_row and base_row[0]:
        cur.execute(f"""UPDATE knowledge_objects
                        SET metadata = metadata || jsonb_build_object(
                              'library_group', %s::text, 'library_card_name', 'هيئة أسواق المال'::text,
                              'doc_part', 'القانون'::text)
                        WHERE object_type IN ({ph}) AND branch='تجاري' AND {GEXPR} = %s""",
                    (UNIFIED, *LAW_TYPES, base_row[0]))
        print("  القانون الأصلي: عُدِّل", cur.rowcount, "كائن ->", UNIFIED, "/ القانون", flush=True)

    cur.execute(f"""SELECT DISTINCT metadata->>'library_group', metadata->>'library_card_name'
                    FROM knowledge_objects
                    WHERE object_type IN ({ph}) AND metadata->>'library_group' LIKE 'cma-book-%%'""", LAW_TYPES)
    book_groups = cur.fetchall()
    print("\nكتب اللائحة الحالية المنفصلة:", len(book_groups), flush=True)
    total_books_updated = 0
    for lg, card_name in book_groups:
        subname = (card_name or lg).replace("اللائحة التنفيذية — ", "").strip()
        cur.execute(f"""UPDATE knowledge_objects
                        SET metadata = metadata || jsonb_build_object(
                              'library_group', %s::text, 'library_card_name', 'هيئة أسواق المال'::text,
                              'doc_part', 'اللائحة التنفيذية'::text, 'doc_subpart', %s::text)
                        WHERE object_type IN ({ph}) AND metadata->>'library_group' = %s""",
                    (UNIFIED, subname, *LAW_TYPES, lg))
        total_books_updated += cur.rowcount
        print("  '%s' -> اللائحة/%s | %d كائن" % (lg, subname[:30], cur.rowcount), flush=True)
    print("إجمالي كائنات اللائحة الموحَّدة:", total_books_updated, flush=True)

    print("\n== فحص وجود بيانات حماية المستهلك ==", flush=True)
    cur.execute("""SELECT count(*) FROM knowledge_objects
                   WHERE (title ILIKE '%%حماية المستهلك%%' OR metadata->>'title' ILIKE '%%حماية المستهلك%%')""")
    cp_count = cur.fetchone()[0]
    print("كائنات فيها 'حماية المستهلك':", cp_count, flush=True)
    if cp_count:
        cur.execute(f"""SELECT {GEXPR} AS g, count(*), min(metadata->>'library_card_name')
                        FROM knowledge_objects
                        WHERE (title ILIKE '%%حماية المستهلك%%' OR metadata->>'title' ILIKE '%%حماية المستهلك%%')
                          AND object_type IN ({ph})
                        GROUP BY g""", LAW_TYPES)
        print("مجموعاتها الحالية:", cur.fetchall(), flush=True)
        print("(تحتاج فحصاً يدوياً منفصلاً لأن بنيتها قد تختلف)", flush=True)
    else:
        print("لا توجد بيانات لحماية المستهلك في القاعدة حالياً — لم تُرفع بعد، لا شيء لأفعله هنا", flush=True)

    print("\n== تسمية مبادئ هيئة أسواق المال ==", flush=True)
    cur.execute("""SELECT count(*) FROM knowledge_objects
                   WHERE object_type='judicial_principle'
                     AND metadata->>'title' ILIKE '%%المبادئ القانونية%%اسواق%%المال%%'""")
    print("مبادئ أسواق المال الموجودة:", cur.fetchone()[0], flush=True)
    cur.execute("""UPDATE knowledge_objects
                   SET topic='مبادئ هيئة أسواق المال', branch='تجاري', updated_at=now()
                   WHERE object_type='judicial_principle'
                     AND metadata->>'title' ILIKE '%%المبادئ القانونية%%اسواق%%المال%%'""")
    print("عُدِّل الموضوع لـ:", cur.rowcount, "كائن -> 'مبادئ هيئة أسواق المال' تحت فرع تجاري", flush=True)
PYEOF

echo ""
echo "===== (ب) الكود: إضافة مستوى فرعي (sub) في /api/browse ====="
APP=/opt/LegalMind/admin/app.py
cp -a "$APP" /root/app.py.bak-browse-sublevel
echo "نسخة احتياطية: /root/app.py.bak-browse-sublevel"

$PY - <<'PYEOF'
# -*- coding: utf-8 -*-
p = "/opt/LegalMind/admin/app.py"
src = open(p, encoding="utf-8").read()

OLD_SIG = '''def browse_kb(kind: str, b: str = "", t: str = "", group: str = "", part: str = "",
              _: str = Depends(require_auth)) -> dict:'''
NEW_SIG = '''def browse_kb(kind: str, b: str = "", t: str = "", group: str = "", part: str = "", sub: str = "",
              _: str = Depends(require_auth)) -> dict:'''
assert OLD_SIG in src, "لم أجد توقيع الدالة المتوقع"
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

assert OLD_BLOCK in src, "لم أجد كتلة العرض المتوقعة — توقف بلا تغيير"
src = src.replace(OLD_BLOCK, NEW_BLOCK, 1)
open(p, "w", encoding="utf-8").write(src)
print("رُكِّب مستوى sub بنجاح ✓")
PYEOF

echo ""
echo "== فحص تركيبي قبل إعادة التشغيل =="
if $PY -m py_compile "$APP"; then
  echo "الكود سليم ✓"
else
  echo "فشل الفحص التركيبي — استرجاع النسخة الاحتياطية فوراً"
  cp -a /root/app.py.bak-browse-sublevel "$APP"
  echo "استُرجعت النسخة السابقة — لم يتغير شيء في الكود الحي"
  exit 1
fi

systemctl restart legalmind-admin
sleep 3
systemctl is-active legalmind-admin && echo "الخدمة تعمل ✓"

echo ""
echo "===== اختبار ذاتي مباشر على القاعدة (محاكاة البنية الجديدة) ====="
$PY - <<'PYEOF'
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng
LAW_TYPES = ('legislation', 'legislation_article', 'legislation_issuing_article', 'legislation_preamble')
with eng.psycopg.connect(eng.database_url()) as conn, conn.cursor() as cur:
    ph = ",".join(["%s"] * len(LAW_TYPES))
    cur.execute(f"""SELECT metadata->>'doc_part' AS p, metadata->>'doc_subpart' AS sp, count(*)
                    FROM knowledge_objects WHERE object_type IN ({ph})
                      AND metadata->>'library_group'='cma-authority-unified'
                    GROUP BY 1,2 ORDER BY 1,2""", LAW_TYPES)
    print("البنية الفعلية الآن تحت 'هيئة أسواق المال':")
    for p, sp, c in cur.fetchall():
        print("  جزء='%s' | فرعي='%s' | %d كائن" % (p, sp, c))
PYEOF
echo "===== اكتمل الأمر الشامل ====="
