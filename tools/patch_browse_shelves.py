#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""رقعة المتصفح: مجلدات «القوانين» تصير رفوف المكتبة (metadata.library_shelf) بترتيب المرجع.

تمسّ browse_kb وحدها، وفي فرع kind == "laws" وحده: المستوى الأول (المجلدات) والثاني
(قوانين المجلد). وما لا رفّ له يبقى في فرعه (COALESCE) فلا يختفي قانون أبدًا. ولا يُعدّ في المجلد إلا ما يمكن فتحه
(مفتاح تجميع غير فارغ — كائنات بلا مفتاح كانت تُعدّ في عدد المجلد ولا تظهر فيه). المبادئ
والأحكام والصيغ تبقى على الفروع كما هي، والاسترجاع لا يقرأ هذه الدالة أصلًا.
كل مرساة «مرة واحدة بالضبط»، وإعادة التشغيل بلا أثر (SHELF_PATCH_ALREADY).
"""
import sys, io

PATH = sys.argv[1] if len(sys.argv) > 1 else "/opt/LegalMind/admin/app.py"
MARK = "# رفوف المكتبة (taxonomy/library_shelves.json)"

A0 = ('''    BR = "CASE WHEN branch LIKE 'أحوال شخصية%%' THEN 'أحوال شخصية' ELSE COALESCE(NULLIF(branch,''),'غير مصنّف') END"\n''')
B0 = A0 + (
    '''    ''' + MARK + ''' — مجلدات القوانين بترتيب المرجع؛ وما لا رفّ له يبقى في فرعه\n'''
    '''    SH = "COALESCE(NULLIF(metadata->>'library_shelf',''), " + BR + ")"\n'''
    '''    SHO = "NULLIF(metadata->>'library_shelf_order','')::int"\n''')

A1 = ('''            if not b:\n'''
      '''                _cur.execute(\n'''
      '''                    "SELECT " + BR + " AS g, count(*) FROM knowledge_objects "\n'''
      '''                    "WHERE object_type IN (" + tph + ") GROUP BY g ORDER BY count(*) DESC",\n'''
      '''                    tuple(types))\n''')
B1 = ('''            if not b:\n'''
      '''                _cur.execute(\n'''
      '''                    "SELECT " + SH + " AS g, count(*), min(" + SHO + ") AS o FROM knowledge_objects "\n'''
      '''                    "WHERE object_type IN (" + tph + ") AND " + GEXPR + " IS NOT NULL "\n'''
      '''                    "GROUP BY g ORDER BY o NULLS LAST, count(*) DESC",\n'''
      '''                    tuple(types))\n''')

A2 = ('''                    "FROM knowledge_objects WHERE object_type IN (" + tph + ") AND " + BR + " = %s "\n'''
      '''                    "GROUP BY g ORDER BY g", tuple(types) + (b,))\n''')
B2 = ('''                    "FROM knowledge_objects WHERE object_type IN (" + tph + ") AND " + SH + " = %s "\n'''
      '''                    "GROUP BY g ORDER BY g", tuple(types) + (b,))\n''')


def main():
    s = io.open(PATH, encoding="utf-8").read()
    if MARK in s:
        print("SHELF_PATCH_ALREADY")
        return
    for name, a in (("A0", A0), ("A1", A1), ("A2", A2)):
        n = s.count(a)
        if n != 1:
            raise SystemExit("ANCHOR_FAIL: %s وُجدت %d مرة والمطلوب مرة واحدة بالضبط" % (name, n))
    # A1 يجب أن يقع داخل فرع القوانين لا في فرع المبادئ (الذي يحمل نفس الشكل بإزاحة أقل)
    i_laws = s.index('        if kind == "laws":')
    i_other = s.index("        # غير التشريعات: فرع ← موضوع ← عناصر")
    for name, a in (("A1", A1), ("A2", A2)):
        if not (i_laws < s.index(a) < i_other):
            raise SystemExit("ANCHOR_SCOPE: %s خارج فرع القوانين" % name)
    out = s.replace(A0, B0).replace(A1, B1).replace(A2, B2)
    delta = len(out) - len(s)
    if not (0 < delta < 1200):
        raise SystemExit("SIZE_GUARD: حجم التغيير %d خارج المتوقع" % delta)
    io.open(PATH, "w", encoding="utf-8").write(out)
    print("SHELF_PATCH_OK (+%d حرفًا)" % delta)


if __name__ == "__main__":
    main()
