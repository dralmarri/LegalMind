#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يطبّق تصحيحات نصوص مواد مبتورة (نصّها الكامل من المصدر الرسمي) ثم يفهرس كلّ مادة وحدها.
FIXES محمّلة من JSON مضمّن (تفاديًا لمشاكل الإفلات). الوضع الافتراضي معاينة؛ --apply يكتب ويفهرس.
كلّ مادة تُفهرَس فور تحديثها عبر reindex_one_cli (سريع، بلا مهلة nginx)."""
import os, re, sys, json, subprocess

# قائمة تصحيحات. mode=replace: استبدال النصّ كاملًا (نصّ موثّق كامل).
#                mode=append: إلحاق الذيل المقتطع فقط إن كان النصّ الحالي ينتهي بالمرساة
#                (يمسّ موضع البتر وحده، لا يعيد كتابة المتن).
FIXES = []
FIXES.append({"id": "legis-67-1980-m99", "mode": "replace",
    "text": "تصرفات المعتوه تسري عليها أحكام تصرفات الصغير المميز المنصوص عليها في المادة 87، نصب عليه قيم أو لم ينصب."})

# م38 إثبات: بترٌ في الذيل فقط — الذيل الصحيح «المواد السابقة.» (مؤكَّد من صورة المصدر الرسمي)
FIXES.append({"id": "legis-39-1980-m38", "mode": "append",
    "anchor": "المنصوص عليها في", "tail": " المواد السابقة."})

# م167 مرافعات (مؤكَّد من المستخدم والمصدر) — استبدال كامل
_M167 = (
    "على الدائن أن يكلف المدين أولاً بالوفاء بميعاد عشرة أيام على الأقل ثم يستصدر\n"
    "أمر بالأداء من قاضي محكمة المواد الجزئية أو رئيس الدائرة بالمحكمة الكلية حسب\n"
    "الأحوال، ولا يجوز أن يكون الحق الوارد في التكليف بالوفاء أقل من المطلوب\n"
    "في عريضة استصدار الأمر بالأداء، ويكفي في التكليف بالوفاء أن يحصل بكتاب\n"
    "مسجل ، أو بأية وسيلة اتصال إلكترونية حديثة قابلة للحفظ والاستخراج يصدر\n"
    "بها قرار من وزير العدل.\n"
    "ويصدر الأمر بالأداء بناء على عريضة يقدمها الدائن يرفق بها سند الدين وما يثبت\n"
    "حصول التكليف بوفائه وقفل الحساب في الحالات التي يكون لها مقتضى، ويبقى\n"
    "هذا السند في إدارة الكتاب إلى أن يمضي ميعاد التظلم ويجب أن تحرر العريضة من\n"
    "نسختين متطابقتين وأن تشتمل على بيانات صحيفة الدعوى المنصوص عليها في\n"
    "المادة 54 من هذا القانون.\n"
    "ويجب أن يصدر الأمر على إحدى نسختي العريضة خلال ثلاثة أيام على الأكثر من\n"
    "تقديمها وأن يبين المبلغ الواجب أداؤه، كما يبين ما اذا كان صادراً في مادة تجارية\n"
    "وتعتبر العريضة سالفة الذكر منتجة لآثار رفع الدعوى من تاريخ تقديمها، ولو\n"
    "كانت المحكمة غير مختصة."
)
FIXES.append({"id": "legis-38-1980-m167", "mode": "replace", "text": _M167})

# م123 أسواق المال (7/2010): بترٌ في الذيل — نصّ المصدر مؤكَّد من المستخدم حرفيًّا (بما فيه الرقم)
FIXES.append({"id": "legis-7-2010-m123", "mode": "append", "anchor": "وارد فى",
    "tail": " الفصل السابع من هذا القانون فى شأن الأستحواذ وحماية حقوق الأقلية."})


def nt(text):
    try:
        sys.path.insert(0, "/opt/LegalMind/engine")
        from normalizer.canonical import normalize_text as f
        return f(text)
    except Exception:
        import unicodedata
        t = unicodedata.normalize("NFKC", text).replace("ـ", "")
        t = re.sub(r"[ \t]+", " ", t); t = re.sub(r" *\n *", "\n", t)
        return re.sub(r"\n{3,}", "\n\n", t).strip()


def main():
    apply = "--apply" in sys.argv
    dsn = os.getenv("DATABASE_URL") or \
        "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
    import psycopg
    changed = []
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        for fx in FIXES:
            oid = fx["id"]
            cur.execute("SELECT original_text FROM knowledge_objects WHERE id=%s", (oid,))
            r = cur.fetchone()
            if not r:
                print(f"⚠ {oid}: غير موجود — تخطّي"); continue
            old = (r[0] or "").strip()
            if fx["mode"] == "replace":
                new = fx["text"].strip()
            else:  # append: يلحق الذيل فقط إن انتهى النصّ بالمرساة (أمان)
                anchor = fx["anchor"]
                _m = lambda s: re.sub(r"[ىي]", "ي", re.sub(r"[أإآ]", "ا", s)).replace("ة", "ه")
                if not _m(old).endswith(_m(anchor)):   # مطابقة متسامحة مع صيغة الياء
                    print(f"⚠ {oid}: لا ينتهي بالمرساة «{anchor}» (ينتهي بـ …{old[-40:]!r}) — تخطّي حرصًا"); continue
                new = (old + fx["tail"]).strip()
            print(f"\n=== {oid} ({fx['mode']}) ===")
            print(f"[قبل] طول {len(old):4} …{old[-70:]!r}")
            print(f"[بعد] طول {len(new):4} …{new[-70:]!r}")
            if old == new:
                print("• مطابق سلفًا — لا تغيير"); continue
            if apply:
                cur.execute(
                    "UPDATE knowledge_objects SET original_text=%s, normalized_text=%s, "
                    "verification_status='source_verified', updated_at=now() WHERE id=%s",
                    (new, nt(new), oid))
                changed.append(oid)
        if apply:
            conn.commit()
    if not apply:
        print("\n[معاينة] لم يُكتب شيء. أضِف --apply للتطبيق.")
        return 0
    print(f"\n✓ حُدِّث {len(changed)} مادة. الآن الفهرسة الجزئية لكلّ منها…")
    cli = "/opt/LegalMind/engine/reindex_one_cli.py"
    pye = "/opt/LegalMind/.venv/bin/python"
    for oid in changed:
        env = dict(os.environ); env["HF_HUB_OFFLINE"] = "1"; env["TRANSFORMERS_OFFLINE"] = "1"
        p = subprocess.run([pye, cli, oid], capture_output=True, text=True, env=env, timeout=300)
        print(f"  {oid}: {(p.stdout or p.stderr).strip().splitlines()[-1] if (p.stdout or p.stderr).strip() else 'لا مخرجات'}")
    print("\n✓ تمّ التصحيح والفهرسة.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
