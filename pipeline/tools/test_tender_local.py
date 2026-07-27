#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""فحصٌ محلّيٌّ لمحفّز 49/2016 وحدَه — يستخرج الدوالَّ من /tmp/app_patched.py بلا قاعدةٍ ولا خدمة.
يقيس البوّابةَ (متى ينطق ومتى يصمت) والعناقيدَ (ماذا يُصدر)، لا الترتيبَ النهائيّ — فذاك يقاس
على الخادم في النشرة نفسِها."""
import ast, re, sys

SRC = open("/tmp/app_patched.py", encoding="utf-8").read()
TREE = ast.parse(SRC)
WANT_FN = {"_draft_norm_ar", "_kmatch", "_kmatch_w", "_tender_ids"}
WANT_VAR = {"_AR_DIAC", "_BR_PFX", "_BR_MCACHE", "_PEN_BND",
            "_TENDER_STRONG", "_TENDER_ENT", "_TENDER_ACT", "_TENDER_TERM", "_TENDER_CTX",
            "_TENDER_CORE", "_TENDER_P"}
picked, got = [], set()
for n in TREE.body:
    if isinstance(n, ast.FunctionDef) and n.name in WANT_FN:
        picked.append(n); got.add(n.name)
    elif isinstance(n, ast.Assign):
        for t in n.targets:
            if isinstance(t, ast.Name) and t.id in WANT_VAR:
                picked.append(n); got.add(t.id)
missing = (WANT_FN | WANT_VAR) - got
assert not missing, "لم تُستخرَج: %s" % missing
ns = {"re": re}
exec(compile(ast.Module(body=picked, type_ignores=[]), "<extract>", "exec"), ns)
T = lambda q: ns["_tender_ids"](ns["_draft_norm_ar"](q))

fails = []


def case(q, must, mustnt=(), lbl=""):
    ids = T(q)
    short = [i.replace("legis-", "") for i in ids]
    for m_ in must:
        if m_ not in ids:
            fails.append("%s: مفقود %s | الناتج=%s" % (lbl, m_, short))
    for m_ in mustnt:
        if m_ in ids:
            fails.append("%s: تسرّب %s" % (lbl, m_))
    print("• %-26s %2d معرّفًا | %s" % (lbl, len(ids), ", ".join(short[:12])))
    return ids


P = "legis-49-2016-%s"
print("== نطقُ البوّابة ==")
case("شركتنا تقدّمت بعطاء في مناقصة عامة طرحتها وزارة الأشغال، ورُسيت على غيرنا بسعر أعلى. "
     "كيف نتظلّم؟ وما الميعاد؟ وأي محكمة تختص؟",
     [P % "m77", P % "m78", P % "m79", "legis-20-1981-m2", P % "m2"], lbl="تظلّمٌ من الترسية")
case("صادرت الجهة صاحبة الشأن تأميننا النهائي في مقاولة الأشغال بعد فسخ العقد، فهل يجوز؟ "
     "وهل تخصم الغرامات من مستحقاتنا لدى جهة حكومية أخرى؟",
     [P % "m65", P % "m70", P % "m66"], lbl="مصادرةُ التأمين")
case("هل يجوز للجهاز إصدار أمر تغييري بالزيادة يتجاوز 5% من قيمة العقد؟",
     [P % "m74", P % "m76"], lbl="الأوامر التغييرية")
case("شركة أجنبية تريد التقدّم لمناقصة في الكويت، هل تحتاج وكيلًا محلّيًا وسجلًا تجاريًا؟",
     [P % "m31", P % "m24"], lbl="شروطُ المتعاقد الأجنبيّ")
case("تعاقدت وزارة بالأمر المباشر على توريد بقيمة تسعين ألف دينار بدون إذن الجهاز، هل يصحّ؟",
     [P % "m19", P % "m22"], lbl="الحدُّ الماليّ")
case("حُذفت شركتنا من سجل المقاولين وحُرمنا من الاشتراك خمس سنوات، ما سندُ الجزاء وكيف نتظلّم؟",
     [P % "m85", P % "m77", P % "m78"], lbl="الجزاءات الإدارية")
case("هل يجوز إعلاننا بترسية المناقصة عبر البريد الإلكتروني؟",
     [P % "m80", "legis-20-2014-m10"], lbl="الإعلانُ الإلكترونيّ")
case("ما نسبة أفضلية المنتج المحلي والمشروعات الصغيرة في المناقصات؟",
     [P % "m62", P % "m62-mukarrar", P % "m87"], lbl="أفضليةُ المنتج المحلّيّ")
case("هل يسري قانون المناقصات على مشتريات مؤسسة البترول الكويتية من مشتقات النفط؟",
     [P % "m2", P % "m3"], lbl="نطاقُ السريان")
case("ما هو قانون المناقصات العامة في الكويت؟",
     [P % "m2", P % "m13", P % "m79"], lbl="سؤالٌ عامّ")

print("\n== الصمتُ الواجب ==")
for q, lbl in (("ما عقوبةُ السرقة من منزلٍ مسكونٍ ليلًا؟", "سرقة"),
               ("هل يجوز فصلُ العامل أثناء إجازته المرضية؟", "عمل"),
               ("زوجي هجرني منذ سنة، فهل لي طلبُ التفريق للضرر؟", "أحوال"),
               ("أي محكمة تختص بدعوى تعويض ضد وزارة الصحة عن خطأ طبي أصابني؟", "خطأ طبّيّ"),
               ("اشتريتُ أرضًا بعقدٍ عرفيٍّ ولم أسجّله، لمن تكون الملكية؟", "عقار"),
               ("ما إجراءات تسجيل حق الإرث في عقارات التركة؟", "إرث")):
    ids = T(q)
    if ids:
        fails.append("صمتٌ مخروق في «%s»: %s" % (lbl, [i.replace("legis-", "") for i in ids][:6]))
    print("• %-12s %s" % (lbl, "صامت ✓" if not ids else "نطق ✗ %s" % ids[:4]))

print("\n== حجمُ المخرَج (نافذةُ الصدارة 18) ==")
big = []
for q in ("شركتنا تقدّمت بعطاء في مناقصة عامة ورُسيت على غيرنا، نريد التظلّم والطعن وفسخ العقد "
          "ومصادرة التأمين والأوامر التغييرية والتصنيف والإعلان الإلكتروني والأفضلية واللائحة والرسوم",):
    n = len(T(q))
    print("• أسوأُ حالة (كلُّ العناقيد): %d معرّفًا" % n)
    if n > 40:
        big.append(n)

print()
if fails:
    print("=== إخفاقات (%d) ===" % len(fails))
    for f in fails:
        print("  ✗", f)
    sys.exit(1)
print("=== كلُّ الفحوص خضراء ===")
