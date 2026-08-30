#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""فحصٌ محلّيٌّ لمحفّز 12/2020 — بلا قاعدةٍ ولا خدمة."""
import ast, re, sys
SRC=open("/tmp/app_patched.py",encoding="utf-8").read(); TREE=ast.parse(SRC)
FN={"_draft_norm_ar","_kmatch","_kmatch_w","_infoaccess_ids"}
VAR={"_AR_DIAC","_BR_PFX","_BR_MCACHE","_PEN_BND","_INFO_STRONG","_INFO_OBJ","_INFO_ACT","_INFO_ENT","_INFO_P"}
picked,got=[],set()
for n in TREE.body:
    if isinstance(n,ast.FunctionDef) and n.name in FN: picked.append(n); got.add(n.name)
    elif isinstance(n,ast.Assign):
        for x in n.targets:
            if isinstance(x,ast.Name) and x.id in VAR: picked.append(n); got.add(x.id)
assert not (FN|VAR)-got, (FN|VAR)-got
ns={"re":re}; exec(compile(ast.Module(body=picked,type_ignores=[]),"<x>","exec"),ns)
T=lambda q: ns["_infoaccess_ids"](ns["_draft_norm_ar"](q))
P="legis-12-2020-m%s"; fails=[]
print("== نطقُ البوّابة ==")
for q,must,lbl in (
 ("طلبتُ من الوزارة نسخةً من مستند يخصّني فرفضت، ماذا أفعل؟",[P%"13",P%"11","legis-20-1981-m8"],"رفضُ الطلب"),
 ("رفعتُ دعوى إلغاء ضدّ جهة حكومية رفضت تزويدي بمعلومات، هل دعواي مقبولة؟",[P%"13","legis-20-1981-m8","legis-20-1981-m7"],"قبولُ الدعوى"),
 ("هل يجوز للوزارة حجب معلومة بحجّة السرّية والأمن الوطني؟",[P%"12",P%"2"],"حالاتُ الحظر"),
 ("ما ميعاد ردّ الجهة على طلب الاطلاع على المعلومات؟",[P%"7",P%"9"],"المواعيد"),
 ("هل تسري أحكام حقّ الاطلاع على شركة خاصة تحتفظ بمعلومات نيابة عن وزارة؟",[P%"1",P%"2"],"النطاق"),
 ("ما عقوبة الموظف المختص الذي امتنع عن تقديم المعلومة؟",[P%"14",P%"15"],"العقوبات"),
 ("ما هو قانون حق الاطلاع على المعلومات؟",[P%"2",P%"12",P%"13"],"سؤالٌ عامّ")):
    ids=T(q); s=[i.replace("legis-12-2020-","ق").replace("legis-20-1981-","إد") for i in ids]
    for m in must:
        if m not in ids: fails.append("%s: مفقود %s | %s"%(lbl,m,s))
        elif ids.index(m)>=18: fails.append("%s: %s خارج النافذة (%d)"%(lbl,m,ids.index(m)))
    print("• %-16s %2d | %s"%(lbl,len(ids),", ".join(s[:11])))
print("\n== م13 تتصدّر عند الخصومة ==")
for q,lbl in (("طلبتُ من الوزارة معلومات فرفضت وأريد رفع دعوى","رفض+دعوى"),
              ("لم تردّ الجهة على طلب الاطلاع، هل أقاضيها مباشرة؟","صمتُ الإدارة")):
    ids=T(q); i13=ids.index(P%"13") if P%"13" in ids else None
    if i13 is None or i13>3: fails.append("%s: م13 ليست في الصدارة (%s)"%(lbl,i13))
    print("• %-14s م13 موضع %s"%(lbl,i13))
print("\n== الصمتُ الواجب ==")
for q,lbl in (("ما عقوبةُ السرقة من منزلٍ مسكونٍ ليلًا؟","سرقة"),
              ("هل يجوز فصلُ العامل أثناء إجازته المرضية؟","عمل"),
              ("زوجي هجرني منذ سنة، فهل لي طلبُ التفريق للضرر؟","أحوال"),
              ("ما نسبة التأمين النهائي في المناقصة؟","مناقصات"),
              ("اشتريتُ أرضًا بعقدٍ عرفيٍّ ولم أسجّله","عقار"),
              ("ما شروط قيد بيانات الشركة في السجل التجاري؟","سجل تجاري")):
    ids=T(q)
    if ids: fails.append("صمتٌ مخروق في %s: %s"%(lbl,ids[:4]))
    print("• %-12s %s"%(lbl,"صامت ✓" if not ids else "نطق ✗ %s"%ids[:3]))
print()
if fails:
    print("=== إخفاقات (%d) ==="%len(fails))
    for f in fails: print("  ✗",f)
    sys.exit(1)
print("=== كلُّ الفحوص خضراء ===")
