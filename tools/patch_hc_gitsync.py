# -*- coding: utf-8 -*-
"""إضافة فحص «طراوة المزامنة اليومية مع GitHub» إلى المراجعة الصحية اليومية.

**العلة:** `tools/daily_git_sync.sh` قائم ويعمل بمنطق سليم (فحص أسرار ← التزام ←
دفع ← إخطار عند الفشل)، لكن **لا أحد يراقب أنه يعمل**. فحين تتوقف المزامنة — أيًا
كان السبب — تتوقف **صامتة**: لا بريد، لا تنبيه، ولا يُكتشف الأمر إلا مصادفةً بعد
أسابيع (رُصد فعلًا: آخر مزامنة 2026-09-21، واكتُشف 2026-10-08 بالصدفة أثناء قراءة
كود لغرض آخر). وهذا تكرار حرفي لدرس «الميزة الآمنة الفشل تحتاج فحص حياة دوريًا
وإلا ماتت صامتة» (حادثتا مفتاح OpenAI والمرتِّب المتقاطع، §6 و§11) — مطبَّقًا هذه
المرة على **الحارس نفسه** لا على ميزة.

**الفحص المضاف (رقم 9-مكرر، بنفس نمط فحص النسخة الاحتياطية الموجود):**
  أ) **طراوة التشغيل:** عمر أحدث سجل في `/opt/legalmind-data/gitsync/`. والقياس
     بالسجل لا بآخر التزام **عمدًا** — لأن السكربت يخرج بلا التزام حين لا تغييرات،
     فـ«لا التزام» ليس عطلًا بينما «لا سجل» عطلٌ مؤكد. أكثر من 30 ساعة ⇐ الجدولة
     لا تعمل، فتُشغَّل المزامنة يدويًا **مرة واحدة** (ميكانيكي وقابل للعكس، على
     نموذج إعادة محاولة النسخة الاحتياطية)، وإن فشلت تدخل تقرير «يحتاج انتباهًا».
  ب) **التزامات محلية لم تُدفع:** `origin/main..main` — تكشف الحالة التي يلتزم
     فيها السكربت محليًا ويفشل دفعه، وهي الحالة التي تبدو فيها المزامنة «تعمل»
     بينما GitHub لا يصله شيء. تقرير فقط (الدفع المتكرر الفاشل ليس إصلاحًا).
  ج) **بُعد GitHub بالأيام:** تاريخ آخر التزام على `main` — رقمٌ في التقرير يجعل
     التراكم مرئيًا قبل أن يصير أسابيع.

لا تمسّ هذه الرقعة منطق المزامنة نفسه ولا أي كود قانوني — إضافة كتلة فحص واحدة
قبل كتلة الخاتمة في `daily_healthcheck.sh`.

النجاح = HCGIT_PATCH_OK
"""

import sys, io, os, ast, datetime

HC = "/opt/LegalMind/tools/daily_healthcheck.sh"
STAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

ANCHOR = '''FIXED_N=$(wc -l < "$FIXED_FILE")
ATTN_N=$(wc -l < "$ATTN_FILE")
'''

BLOCK = '''# 12) طراوة المزامنة اليومية مع GitHub — الحارس يحتاج حارسًا
# القياس بأحدث **سجل** لا بآخر التزام: السكربت يخرج بلا التزام حين لا تغييرات،
# فغياب الالتزام ليس عطلًا بينما غياب السجل عطلٌ مؤكد (الجدولة لم تركض أصلًا).
GSDIR=/opt/legalmind-data/gitsync
GSLOG=$(ls -1t "$GSDIR"/*.log 2>/dev/null | head -1)
if [ -n "$GSLOG" ]; then
  GS_AGE_H=$(( ( $(date +%s) - $(stat -c %Y "$GSLOG") ) / 3600 ))
  if [ "$GS_AGE_H" -le 30 ]; then
    log "✓ آخر تشغيل للمزامنة عمره ${GS_AGE_H} ساعة"
  else
    log "آخر تشغيل للمزامنة عمره ${GS_AGE_H} ساعة — محاولة تشغيل يدوي"
    if bash /opt/LegalMind/tools/daily_git_sync.sh >>"$LOG" 2>&1; then
      fixed "شُغِّلت المزامنة مع GitHub يدويًا بعد توقف الجدولة (${GS_AGE_H} ساعة)"
    else
      attn "المزامنة مع GitHub متوقفة منذ ${GS_AGE_H} ساعة وفشل تشغيلها يدويًا — تحتاج تشخيصًا"
    fi
  fi
else
  attn "لا سجل مزامنة واحد في $GSDIR — المزامنة اليومية لم تُشغَّل قط أو أن جدولتها غير مثبَّتة"
fi

# التزامات التزمها السكربت محليًا ولم يُفلح في دفعها — تبدو المزامنة «تعمل» وGitHub لا يصله شيء
GS_AHEAD=$(cd /opt/LegalMind && git rev-list --count origin/main..main 2>/dev/null)
GS_AHEAD=${GS_AHEAD:-0}
if [ "$GS_AHEAD" -gt 0 ] 2>/dev/null; then
  attn "$GS_AHEAD التزامًا محليًا لم يصل GitHub — الدفع يفشل (بيانات اعتماد أو اتصال)"
else
  log "✓ لا التزامات محلية معلّقة"
fi

# بُعد GitHub بالأيام — يجعل التراكم مرئيًا مبكرًا لا بعد أسابيع
GS_LAST=$(cd /opt/LegalMind && git log -1 --format=%ct origin/main 2>/dev/null)
if [ -n "$GS_LAST" ]; then
  GS_DAYS=$(( ( $(date +%s) - GS_LAST ) / 86400 ))
  if [ "$GS_DAYS" -gt 3 ] 2>/dev/null; then
    attn "آخر التزام على GitHub عمره ${GS_DAYS} يومًا — راجع سبب انقطاع المزامنة"
  else
    log "✓ آخر التزام على GitHub عمره ${GS_DAYS} يومًا"
  fi
fi

'''


def main():
    if not os.path.exists(HC):
        raise SystemExit("MISSING_FILE: " + HC)
    src = io.open(HC, encoding="utf-8").read()

    if "طراوة المزامنة اليومية مع GitHub" in src:
        print("ALREADY_PATCHED: الفحص مركّب سلفًا — لا تغيير.")
        print("\nHCGIT_PATCH_OK")
        return

    n = src.count(ANCHOR)
    if n != 1:
        raise SystemExit("ANCHOR_FAIL: مرساة الخاتمة وردت %d مرة (المتوقع 1)." % n)

    new = src.replace(ANCHOR, BLOCK + ANCHOR)
    d = len(new) - len(src)
    print("حجم التغيير: +%d حرفًا" % d)
    if not (1200 < d < 3000):
        raise SystemExit("DELTA_UNEXPECTED: حجم التغيير خارج المدى المتوقع — أوقفت.")

    bak = HC + ".bak_hcgit_" + STAMP
    io.open(bak, "w", encoding="utf-8").write(src)
    io.open(HC, "w", encoding="utf-8").write(new)
    print("  %s — مرقّع (النسخة الاحتياطية: %s)" % (HC, bak))
    print("\nHCGIT_PATCH_OK")


if __name__ == "__main__":
    main()
