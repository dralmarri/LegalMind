import re
src=open('/tmp/app_patched.py').read()
ns={}
def block(start, end_line):
    i=src.index(start)
    j=src.index(end_line, i)+len(end_line)
    return src[i:j]
exec(block("def _draft_norm_ar(t):", "return _AR_TATWEEL.sub"), ns) if False else None
# _draft_norm_ar: grab from def to the next '\ndef '
i=src.index("def _draft_norm_ar(t):"); j=src.index("\ndef ", i)
exec(src[i:j], ns)
# _LABOR_BUNDLES
i=src.index("_LABOR_BUNDLES = ["); j=src.index("\n]", i)+2
exec(src[i:j], ns)
# _LABOR19_BUNDLES
i=src.index("_LABOR19_BUNDLES = ["); j=src.index("\n]", i)+2
exec(src[i:j], ns)
# _LAB4_BUNDLES
i=src.index("_LAB4_BUNDLES = ["); j=src.index("\n]", i)+2
exec(src[i:j], ns)
# _LAB5_BUNDLES
i=src.index("_LAB5_BUNDLES = ["); j=src.index("\n]", i)+2
exec(src[i:j], ns)
# _DISABILITY_BUNDLES
i=src.index("_DISABILITY_BUNDLES = ["); j=src.index("\n]", i)+2
exec(src[i:j], ns)
# _CIVSERVICE_BUNDLES
i=src.index("_CIVSERVICE_BUNDLES = ["); j=src.index("\n]", i)+2
exec(src[i:j], ns)
# _NSM_BUNDLES
i=src.index("_NSM_BUNDLES = ["); j=src.index("\n]", i)+2
exec(src[i:j], ns)
# _SOCINS_BUNDLES
i=src.index("_SOCINS_BUNDLES = ["); j=src.index("\n]", i)+2
exec(src[i:j], ns)
# _SUPINS_BUNDLES
i=src.index("_SUPINS_BUNDLES = ["); j=src.index("\n]", i)+2
exec(src[i:j], ns)
# _JUSTORG_BUNDLES
i=src.index("_JUSTORG_BUNDLES = ["); j=src.index("\n]", i)+2
exec(src[i:j], ns)
# ranges
for name in ["_CIVIL_PROC_RANGES","_PENAL_PROC_RANGES","_CIVIL_UMBRELLA_RANGES"]:
    i=src.index(name+" ="); j=src.index("\n", i)
    exec(src[i:j], ns)
for n in ["_CIVIL_BUNDLES","_EVIDENCE_BUNDLES","_PROCEDURE_BUNDLES","_FEES_BUNDLES","_SMALLCLAIMS_BUNDLES","_GOVFEE_BUNDLES","_LEASE_BUNDLES","_REGISTRATION_BUNDLES","_COMMERCE_BUNDLES","_COMPANIES_BUNDLES","_BANKRUPTCY_BUNDLES","_CAPMARKETS_BUNDLES","_CAPMARKETS_DEF_BUNDLES","_CMAREG2_BUNDLES","_CMAREG3_BUNDLES","_CMAREG4_BUNDLES","_DRAFT_BUNDLES"]:
    ns[n]=[]
i=src.index("def _admin_core():"); j=src.index("\ndef ", i)
exec(src[i:j], ns)
for fn,endtok in [("def _procedural_core(is_penal):","    return out\n"),
                  ("def _civil_umbrella():","    return out\n"),
                  ("def _draft_bundles(","\n    return ids\n")]:
    i=src.index(fn); j=src.index(endtok, i)+len(endtok)
    exec(src[i:j], ns)
db=ns["_draft_bundles"]
print("== 1) استشارة عمالة منزلية: تبقى النواة، ولا 19/2000 ولا 6/2010 (لأنها منزلية) ==")
facts="صاحب عمل تأخر في دفع راتب العاملة المنزلية شهرين وما مقدار مكافأة نهاية الخدمة بعد ثلاث سنوات ورفع دعوى بمستحقاتها"
for br in ["أحوال شخصية","عمالة منزلية","عمل","",None,"العمالة المنزلية","تجاري"]:
    ids=db("استشارة", facts, [], None, br)
    core=[x.split('legis-68-2015-')[-1] for x in ids if x in ("legis-68-2015-m31","legis-68-2015-m35","legis-68-2015-m36","legis-68-2015-m37")]
    l19=[x for x in ids if x.startswith("legis-19-2000-")]
    l6=[x for x in ids if x.startswith("legis-6-2010-")]
    print(f"branch={str(br)[:18]:18} -> core {sorted(core)} | m27:{'legis-68-2015-m27' in ids} | 19/2000:{l19} | 6/2010:{len(l6)} | n={len(ids)}")

print("\n== 3) استشارات العمل العام 6/2010 (غير منزلية): يجب أن تُستحضَر المواد المناسبة، وألا تظهر مع المنزلي ==")
q6=[
 ("مكافأة نهاية الخدمة لموظف بشركة",
  "موظف في شركة خاصة استقال بعد سبع سنوات، كم مكافأة نهاية الخدمة المستحقة له؟"),
 ("الفصل التعسفي والتعويض",
  "صاحب عمل فصل عاملا في القطاع الأهلي دون مبرر، ما التعويض عن الفصل التعسفي والإخطار؟"),
 ("ساعات العمل والعمل الإضافي",
  "ما الحد الأقصى لساعات العمل اليومية والعمل الإضافي في القطاع الأهلي؟"),
 ("إصابة العمل والتعويض",
  "عامل أصيب أثناء العمل في مصنع، ما حقوقه في التعويض عن إصابة العمل والعجز؟"),
 ("الإجازة السنوية",
  "كم رصيد الإجازة السنوية المستحقة للعامل في القطاع الخاص وهل يجوز التعويض النقدي عنها؟"),
 ("تقادم الدعوى العمالية والرسوم",
  "ما مدة تقادم الدعوى العمالية وهل تُعفى دعاوى العمال من الرسوم القضائية؟"),
]
for name,facts in q6:
    ids=db("استشارة", facts, [], None, "عمل")
    l6=sorted((x.split("legis-6-2010-")[-1] for x in ids if x.startswith("legis-6-2010-")),
              key=lambda s:int(s[1:]))
    print(f"{name:34} -> 6/2010 {l6} | n={len(ids)}")

print("\n== 2) استشارات دعم العمالة الوطنية 19/2000: يجب أن تُستحضَر المواد المناسبة ==")
q19=[
 ("العلاوة الاجتماعية وعلاوة الأولاد",
  "ما شروط استحقاق العلاوة الاجتماعية وعلاوة الأولاد للمواطن الكويتي وكم قيمة علاوة الاولاد"),
 ("بدل البطالة",
  "كويتي عاطل عن العمل يطالب ببدل البطالة النقدي، ما الأساس القانوني؟"),
 ("نسب العمالة الوطنية والإحلال",
  "شركة في القطاع غير الحكومي لم تلتزم بنسبة العمالة الوطنية وفُرض عليها رسم اضافي على تصاريح العمل"),
 ("ضريبة دعم العمالة الوطنية",
  "هل تخضع أرباح الشركات الكويتية المدرجة في سوق الكويت للاوراق المالية لضريبة دعم العمالة الوطنية؟"),
 ("مستحقات غير الكويتيين عبر البنوك",
  "التزام الجهة غير الحكومية بدفع مستحقات العاملين غير الكويتيين في حساباتهم البنكية"),
]
for name,facts in q19:
    ids=db("استشارة", facts, [], None, "عمل")
    l19=sorted((x.split("legis-19-2000-")[-1] for x in ids if x.startswith("legis-19-2000-")),
               key=lambda s:int(s[1:]))
    print(f"{name:36} -> 19/2000 {l19} | n={len(ids)}")
