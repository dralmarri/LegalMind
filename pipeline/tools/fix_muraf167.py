#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تصحيح م167 مرافعات (38/1980): استرداد التكملة المقتطعة من المحلّل القديم، من المصدر الرسمي.
DB id: legis-38-1980-m167. تحديث نصّ فقط."""
import os, re, sys
NEW = 'على الدائن أن يكلف المدين أولاً بالوفاء بميعاد عشرة أيام على الأقل ثم يستصدر\nأمر بالأداء من قاضي محكمة المواد الجزئية أو رئيس الدائرة بالمحكمة الكلية حسب\nالأحوال، ولا يجوز أن يكون الحق الوارد في التكليف بالوفاء أقل من المطلوب\nفي عريضة استصدار الأمر بالأداء، ويكفي في التكليف بالوفاء أن يحصل بكتاب\nمسجل ، أو بأية وسيلة اتصال إلكترونية حديثة قابلة للحفظ والاستخراج يصدر\nبها قرار من وزير العدل.\nويصدر الأمر بالأداء بناء على عريضة يقدمها الدائن يرفق بها سند الدين وما يثبت\nحصول التكليف بوفائه وقفل الحساب في الحالات التي يكون لها مقتضى، ويبقى\nهذا السند في إدارة الكتاب إلى أن يمضي ميعاد التظلم ويجب أن تحرر العريضة من\nنسختين متطابقتين وأن تشتمل على بيانات صحيفة الدعوى المنصوص عليها في\nالمادة 54 من هذا القانون.\nويجب أن يصدر الأمر على إحدى نسختي العريضة خلال ثلاثة أيام على الأكثر من\nتقديمها وأن يبين المبلغ الواجب أداؤه، كما يبين ما اذا كان صادراً في مادة تجارية\nوتعتبر العريضة سالفة الذكر منتجة لآثار رفع الدعوى من تاريخ تقديمها، ولو\nكانت المحكمة غير مختصة.'
def normalize_text(text):
    try:
        sys.path.insert(0,"/opt/LegalMind/engine")
        from normalizer.canonical import normalize_text as nt
        return nt(text)
    except Exception:
        import unicodedata
        t=unicodedata.normalize("NFKC",text).replace("ـ","")
        t=re.sub(r"[ \t]+"," ",t); t=re.sub(r" *\n *","\n",t)
        return re.sub(r"\n{3,}","\n\n",t).strip()
def main():
    dry="--dry-run" in sys.argv
    dsn=os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
    import psycopg
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("select original_text from knowledge_objects where id=%s",("legis-38-1980-m167",))
        r=cur.fetchone()
        print("=== legis-38-1980-m167 ===")
        print("[قبل] …"+repr((r[0] or "").strip()[-60:]))
        print("[بعد] …"+repr(NEW.strip()[-60:]))
        print("[طول] قبل",len((r[0] or "").strip()),"→ بعد",len(NEW.strip()))
        if not dry:
            cur.execute("update knowledge_objects set original_text=%s, normalized_text=%s, verification_status=%s, updated_at=now() where id=%s",
                        (NEW, normalize_text(NEW), "source_verified", "legis-38-1980-m167"))
            conn.commit(); print("\n✓ حُدِّث. شغّل reindex.")
        else:
            print("\n[dry-run] لم يُحدَّث.")
if __name__=="__main__": main()
