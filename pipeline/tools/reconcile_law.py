#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مطابقة وتنظيف آمن لمواد قانون في القاعدة مقابل إعادة تحليل نظيفة لمصدره.
يستبدل نصّ القاعدة بالنصّ النظيف فقط إذا كان الأخير يحوي كامل محتوى القاعدة كبادئة
(يزيل تلوّث العنوان ويستردّ الاجتزاع دون فقدان حرف). قراءة+تحديث اختياري.
يقرأ إعادة التحليل من <prefix>_reparse.json المرفق ({"bodies":{opening_key:full_text}} أو قائمة)."""
import os, re, sys, json

def norm(t):
    t = re.sub(r"[أإآ]","ا",t); t = re.sub(r"[ىی]","ي",t); t = t.replace("ة","ه").replace("ـ","")
    t = re.sub(r"[ً-ٟ]","",t)              # تشكيل
    return re.sub(r"\s+","",t)             # بلا فراغات

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
    prefix = sys.argv[1]
    reparse_path = sys.argv[2]
    apply = "--apply" in sys.argv
    # إعادة التحليل: قائمة نصوص نظيفة بالترتيب
    rp = json.load(open(reparse_path, encoding="utf-8"))
    bodies = [b for b in rp["bodies"] if b and b.strip()]
    # فهرسة المصدر ببدايته المطبّعة (أول 60 محرفًا)
    src_by_open = {}
    for b in bodies:
        k = norm(b)[:60]
        src_by_open.setdefault(k, b)
    import psycopg
    dsn=os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
    changes=[]; nomatch=[]; src_trunc=[]
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("select id, coalesce(original_text,'') from knowledge_objects where id like %s order by id",(prefix+"-%",))
        rows=cur.fetchall()
        for oid, db in rows:
            db=db.strip()
            if not db or db=="(ملغاة)" or "ملغا" in db[:12]: continue
            nk=norm(db)[:60]
            cand=src_by_open.get(nk)
            if not cand:
                # مطابقة مرنة: ابحث عن مصدر تبدأ بدايته المطبّعة ببداية القاعدة (>=40)
                dk=norm(db)
                cand=next((b for b in bodies if norm(b)[:40]==dk[:40]), None)
            if not cand:
                nomatch.append(oid); continue
            nd=norm(db); nc=norm(cand)
            if nd==nc: continue                       # مطابق تمامًا
            if nc.startswith(nd):                      # المصدر يحوي القاعدة كبادئة + زيادة (استرداد/تنظيف)
                changes.append((oid, db, cand, "استرداد/تنظيف"))
            elif nd.startswith(nc):                    # القاعدة أطول (تلوّث عنوان في الذيل غالبًا)
                # تحقّق أن الزائد في القاعدة قصير (عنوان) لا متن
                extra=len(nd)-len(nc)
                if extra<=60:
                    changes.append((oid, db, cand, "إزالة تلوّث عنوان"))
                else:
                    nomatch.append(oid+"(القاعدة أطول)")
            else:
                nomatch.append(oid+"(اختلاف)")
    print(f"== {prefix} : مطابقات للتغيير={len(changes)} | بلا مطابقة={len(nomatch)} ==")
    for oid, db, cand, why in changes[:40]:
        print(f"\n[{oid}] ({why})")
        print(f"  قبل: …{db[-55:]!r}")
        print(f"  بعد: …{cand[-55:]!r}")
    if nomatch:
        print("\nبلا مطابقة/اختلاف (تُترك):", nomatch[:30])
    if apply and changes:
        with psycopg.connect(dsn) as conn, conn.cursor() as cur:
            for oid, db, cand, why in changes:
                cur.execute("update knowledge_objects set original_text=%s, normalized_text=%s, updated_at=now() where id=%s",
                            (cand, normalize_text(cand), oid))
            conn.commit()
        print(f"\n✓ حُدِّث {len(changes)} مادة. شغّل reindex.")
    else:
        print("\n[تجربة جافّة] لم يُحدَّث شيء." if not apply else "\nلا تغييرات.")

if __name__=="__main__": main()
