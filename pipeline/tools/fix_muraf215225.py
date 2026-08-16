#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تصحيح م215 وم225 مرافعات (38/1980): سدّ فجوة المصدر بالنصّ الرسمي. تحديث نصّ فقط."""
import os, re, sys, json
FIXES = json.loads('{"legis-38-1980-m215": "تنفذ القرارات والاحكام الصادرة في مسائل الاحوال الشخصية بالطرق المقررة في الباب الثاني من هذا الكتاب إذا اقتضى ذلك الحجز على الأموال وبيعها.\\nوينفذ ما عدا ذلك من هذه القرارات والاحكام بالطريق الاداري بمعرفة جهات الإدارة أو من يعينه وزير العدل لذلك ، إلا إذا نص القانون على غير ذلك.\\nوتنفذ الاحكام الصادرة بضم الصغير وحفظه او تسليمه لامين بالطريق المشار اليه\\nفي الفقرة السابقة، ويجوز تنفيذها جبرا ولو ادى ذلك الى استعمال القوة ودخول\\nالمنازل، ويتبع القائمون بالتنفيذ في ذلك ما يأمر به مدير ادارة التنفيذ وتجوز اعادة\\nالتنفيذ كلما اقتضى الحال ذلك.\\nوتحدد المحكمة طريقة تنفيذ الحكم الصادر برؤية الصغير، ولا يجوز ان يكون ذلك\\nفي مخفر الشرطة او اية جهة من جهات الادارة.", "legis-38-1980-m225": "يتبع في الحجز التحفظي على المنقولات القواعد والاجراءات المنصوص عليها في الفصل الرابع من هذا الباب عدا ما يتعلق منها بتحديد يوم البيع إلا إذا كانت هذه المنقولات عرضة للتلف فيراعي نص الفقرة الثانية من المادة 252 ويجب ان\\nيعلن الحاجز الى المحجوز عليه محضر الحجز والامر الصادر به إذا لم يكن قد أعلن\\nبه من قبل وذلك خلال ثمانية ايام على الاكثر من تاريخ توقيعه والا اعتبر كان لم\\nيكن.\\nكما يجب على الحاجز - خلال الاجل سالف الذكر - ان يرفع امام المحكمة المختصة\\nالدعوى بثبوت الحق وصحة الحجز، وذلك في الاحوال التي يكون فيها الحجز\\nبأمر من القاضي، والا اعتبر الحجز كأن لم يكن.\\nوإذا كانت الدعوى بالحق مرفوعة من قبل قدمت دعوى صحة الحجز الى ذات\\nالمحكمة لتنظر فيهما معا.\\nوإذا صدر حكم بصحة الحجز وكان واجب التنفيذ او صار كذلك تتبع الاجراءات\\nالمقررة للبيع في الفصل الرابع من هذا الباب او يجري التنفيذ بتسليم المنقول في\\nالحالة المشار اليها في المادة 223 ."}')
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
        for oid,new in FIXES.items():
            cur.execute("select original_text from knowledge_objects where id=%s",(oid,))
            r=cur.fetchone()
            if not r: print("✗ غير موجود:",oid); continue
            print("=== %s ==="%oid)
            print("[قبل] طول",len((r[0] or "").strip()),"…"+repr((r[0] or "").strip()[-45:]))
            print("[بعد] طول",len(new.strip()),"…"+repr(new.strip()[-45:]))
            if not dry:
                cur.execute("update knowledge_objects set original_text=%s, normalized_text=%s, verification_status=%s, updated_at=now() where id=%s",
                            (new, normalize_text(new), "source_verified", oid))
        if not dry:
            conn.commit(); print("\n✓ حُدِّث. شغّل reindex.")
        else: print("\n[dry-run]")
if __name__=="__main__": main()
