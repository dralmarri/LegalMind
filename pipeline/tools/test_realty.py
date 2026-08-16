# -*- coding: utf-8 -*-
"""اختبارُ محفّز 5/1959 محلّيًّا — يقيس **الترتيب** لا الحضور، لأنّ ما بعد المرتبة 18 يسقط إلى درجة صفر."""
import ast, re, sys
src = open('/tmp/app_patched.py', encoding='utf-8').read()
tree = ast.parse(src)
FN = {'_draft_norm_ar', '_kmatch', '_realty_ids', '_etrx_ids'}
AS = {'_AR_DIAC', '_BR_MCACHE', '_BR_PFX', '_ETRX_KEYS', '_REALTY_STRONG', '_REALTY_SUBJ', '_REALTY_ACT', '_REALTY_ETRX_CORE'}
segs = []
for n in tree.body:
    if isinstance(n, ast.FunctionDef) and n.name in FN:
        segs.append(ast.get_source_segment(src, n))
    if isinstance(n, ast.Assign):
        for t in n.targets:
            if isinstance(t, ast.Name) and t.id in AS:
                segs.append(ast.get_source_segment(src, n))
ns = {'re': re}
exec("\n".join(segs), ns)
R, E, N = ns['_realty_ids'], ns['_etrx_ids'], ns['_draft_norm_ar']
HI = 18

def tr(q):
    b = N(q)
    return R(b) + E(b)

FIRE = [
 ("اتفقتُ مع شريكي على بيع حصّته في عقارٍ عبر البريد الإلكتروني بتوقيعٍ إلكترونيّ، وأنكر الآن الاتفاق. "
  "هل ينعقد البيع؟ وهل التوقيع حجّة عليه؟",
  ["legis-5-1959-m7", "legis-5-1959-m17", "legis-5-1959-m29", "legis-20-2014-m2", "legis-20-2014-m3"]),
 ("اشتريتُ أرضًا بعقدٍ عرفيٍّ ولم أسجّله، ثمّ باعها البائعُ لغيري وسجّلها. لمن تكون الملكية؟",
  ["legis-5-1959-m7", "legis-5-1959-m8", "legis-5-1959-m14"]),
 ("ما إجراءاتُ تسجيل حقّ الإرث في عقارات التركة؟",
  ["legis-5-1959-m7", "legis-5-1959-m10", "legis-5-1959-m20", "legis-5-1959-m21"]),
 ("رفعتُ دعوى استحقاقٍ على عقار، فهل تُسجَّل صحيفةُ الدعوى؟ وما أثرُ التأشير؟",
  ["legis-5-1959-m11-mukarrar-1", "legis-5-1959-m11-mukarrar-3"]),
 ("وكّلتُ محاميًا بتوكيلٍ محرَّرٍ في الخارج لبيع عقاري، فهل يُقبل أمام دائرة التسجيل العقاري؟",
  ["legis-5-1959-m49", "legis-5-1959-m50", "legis-5-1959-m45"]),
 ("كم رسمُ تسجيل عقد بيع العقار؟ وهل ثمّة إعفاء؟",
  ["legis-5-1959-m57", "legis-5-1959-m58", "legis-5-1959-m61"]),
]

# أسئلةٌ يجب ألّا يشتعل فيها المحفّز إطلاقًا (وإلّا زاحم نصوصًا أَولى بالصدارة)
QUIET = [
 "ما عقوبةُ السرقة من منزلٍ مسكونٍ ليلًا؟",
 "هل يجوز فصلُ العامل أثناء إجازته المرضية؟",
 "ما مدّةُ الطعن بالتمييز في الأحكام الجزائية؟",
 "زوجي هجرني منذ سنة، فهل لي طلبُ التفريق للضرر؟",
 "ما شروطُ الترخيص لمزاولة أعمال البثّ المرئي والمسموع؟",
 "بناءً على قرار الوزير رُفض طلبي، فما ميعادُ الطعن؟",
]

fail = 0
print("== إشعالٌ وترتيب ==")
for q, need in FIRE:
    b = tr(q)
    print("\n• %s" % q[:66])
    print("  إجمالي: %d | الصدارة: %s" % (len(b), ", ".join(x.replace("legis-", "") for x in b[:8])))
    for oid in need:
        pos = b.index(oid) if oid in b else -1
        ok = 0 <= pos < HI
        if not ok:
            fail += 1
        print("   %s %-30s ترتيب %s" % ("✓" if ok else "✗", oid.replace("legis-", ""),
                                        pos if pos >= 0 else "غائب"))

print("\n== صمتٌ واجب ==")
for q in QUIET:
    got = R(N(q))
    ok = not got
    if not ok:
        fail += 1
    print(" %s %-62s ⇐ %s" % ("✓" if ok else "✗", q[:62], "صامت" if ok else got[:4]))

print("\n%s" % ("✓ كلُّ الاختبارات ناجحة" if not fail else "✗ إخفاقات: %d" % fail))
sys.exit(1 if fail else 0)
