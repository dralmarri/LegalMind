#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني خريطة الإحالات الصريحة بين القوانين من نصوص القاعدة.
يقرأ كل مواد التشريع (id, النصّ)، يستخرج «المادة N من قانون/مرسوم X»، يحلّها إلى معرّف الهدف،
ويُبقي فقط الأهداف الموجودة فعلًا والمنتمية لقانون آخر (إحالات عابرة للقوانين).
المخرَج: /opt/LegalMind/admin/xref_map.json  = {"معرّف المصدر": ["هدف", ...]}
الوضع --local يقرأ ملفات *_parsed.json في المجلد الحالي للتحقّق دون قاعدة بيانات."""
import re, json, os, sys, argparse

def _norm(t):
    t = re.sub(r"[أإآ]", "ا", t); t = re.sub(r"[ىی]", "ي", t)
    t = t.replace("ة", "ه").replace("ـ", ""); t = re.sub(r"[ً-ْٰ]", "", t)
    return t

_DIG = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_ORD = {"الاولى":1,"الاول":1,"الثانيه":2,"الثاني":2,"الثالثه":3,"الثالث":3,"الرابعه":4,"الرابع":4,
        "الخامسه":5,"الخامس":5,"السادسه":6,"السادس":6,"السابعه":7,"السابع":7,"الثامنه":8,"الثامن":8,
        "التاسعه":9,"التاسع":9,"العاشره":10,"العاشر":10}
_LAW_NAMES = [(re.compile(p), pre) for p, pre in [
    (r"قانون المرافعات(?: المدنيه والتجاريه)?", "legis-38-1980"),
    (r"المرافعات المدنيه والتجاريه", "legis-38-1980"),
    (r"قانون الاثبات(?: في المواد المدنيه والتجاريه)?", "legis-39-1980"),
    (r"القانون المدني", "legis-67-1980"),
    (r"قانون التجاره", "legis-68-1980"),
    (r"قانون الشركات", "legis-1-2016"),
    (r"قانون الجزاء", "legis-16-1960"),
    (r"قانون الاجراءات والمحاكمات الجزائيه", "legis-17-1960"),
    (r"قانون الخدمه المدنيه", "legis-15-1979"),
    (r"قانون التامينات الاجتماعيه", "legis-61-1976"),
    (r"قانون العمل في القطاع الاهلي", "legis-6-2010"),
    (r"قانون تنظيم الخبره", "legis-40-1980"),
    (r"قانون تنظيم القضاء", "legis-23-1990"),
    (r"قانون المحاماه", "legis-42-1964"),
    (r"قانون التوثيق", "legis-10-2020"),
    (r"قانون دعم(?: و?تشجيع)? العماله الوطنيه", "legis-19-2000"),
    (r"قانون حقوق الاشخاص ذوي الاعاقه", "legis-8-2010"),
]]
_SELF = re.compile(r"^(هذا|ذات|هذه|القانون المرافق|القانون المشار)")

# طبقة تصحيحات يدوية فوق الاستخراج الآلي:
# قوانين ما قبل 1980 قد تُحيل إلى «قانون المرافعات» بترقيم النسخة القديمة (6/1960) التي حلّ محلّها 38/1980،
# فيحلّ الرقم إلى مادة مختلفة تمامًا. نُسقِط الحواف المعروفة الخطأ، ونعيد التوجيه عند التيقّن من المقابل الحالي.
_SUPPRESS = set()  # لا إسقاط حاليًّا — نستعمل إعادة التوجيه بدلًا منه
_REDIRECT = {
    # م25 محاماة تُحيل إلى «م108 مرافعات» بترقيم النسخة القديمة (6/1960)؛ المقابل الموضوعي الحالي
    # لحكم الشهادة هو م43 من قانون الإثبات 39/1980 (القاعدة العامة في الشهادة التي يُستثنى منها المحامي).
    ("legis-42-1964-m25", "legis-38-1980-m108"): "legis-39-1980-m43",
    # م3 من قانون إنشاء الدائرة الإدارية 20/1981 يُحيل إلى «المادة الثانية من قانون تنظيم القضاء»
    # بترقيم المرسوم القديم 19/1959؛ المقابل الحالي هو قانون تنظيم القضاء 23/1990 (المادة الثانية).
    ("legis-20-1981-m3", "legis-19-1959-m2"): "legis-23-1990-m2",
}
# الأقواس حول الأرقام قد تنقلب اتجاهيًّا (bidi) فتُخزَّن «) 22 (» بدل «( 22 )»؛ نقبل أيّ قوسٍ [()]؟
_NUMYEAR = re.compile(r"رقم\s*[()]?\s*(\d+)\s*[()]?\s*لسنه\s*(\d+)")
_ARTNUM = r"[()]?\s*(\d+)\s*[()]?\s*(مكررا?)?"
_ORDWORD = "|".join(_ORD)
_PATTS = [
    re.compile(r"الماده\s*" + _ARTNUM + r"\s*من\s+([^\.،؛\n]{3,80})"),
    re.compile(r"الماده\s+(" + _ORDWORD + r")\s+من\s+([^\.،؛\n]{3,80})"),
    re.compile(r"المادتين\s*[()]?\s*(\d+)\s*،?\s*و?\s*(\d+)\s*[()]?\s*من\s+([^\.،؛\n]{3,80})"),
    re.compile(r"المواد\s*[()]?\s*([\d\s،و]+?)[()]?\s*من\s+([^\.،؛\n]{3,80})"),
]

def _resolve(ident):
    ident = ident.strip()
    if _SELF.match(ident):
        return None
    m = _NUMYEAR.search(ident)
    if m:
        return f"legis-{int(m.group(1))}-{int(m.group(2))}"
    for rx, pre in _LAW_NAMES:
        if rx.search(ident):
            return pre
    return None

def extract_refs(text):
    # اطوِ المسافات/الأسطر إلى فراغٍ واحد حتى لا تنكسر الإحالة عبر سطرٍ جديد
    # («... القانون رقم\n) 2( لسنة 2016» في م60 من 31/1970 كان يضيع بسبب فاصل السطر).
    t = re.sub(r"\s+", " ", _norm(text.translate(_DIG))); out = []
    def add(pre, num, mkr=None):
        if pre and num:
            out.append((pre, str(int(num)) + ("mkr" if mkr else "")))
    for m in _PATTS[0].finditer(t):
        add(_resolve(m.group(3)), m.group(1), m.group(2))
    for m in _PATTS[1].finditer(t):
        n = _ORD.get(m.group(1))
        if n: add(_resolve(m.group(2)), str(n))
    for m in _PATTS[2].finditer(t):
        pre = _resolve(m.group(3)); add(pre, m.group(1)); add(pre, m.group(2))
    for m in _PATTS[3].finditer(t):
        pre = _resolve(m.group(2))
        for nn in re.findall(r"\d+", m.group(1)): add(pre, nn)
    seen = set(); uniq = []
    for x in out:
        if x not in seen: seen.add(x); uniq.append(x)
    return uniq

def load_db():
    import psycopg
    dsn = os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
    rows = []
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("select id, coalesce(original_text,'') from knowledge_objects where id like 'legis-%'")
        rows = cur.fetchall()
    return rows

def load_local():
    import glob
    # ربط ملفات *_parsed.json ببادئاتها (للتحقّق المحلّي فقط)
    PREF = {"adm5":"legis-61-1976","adm6":"legis-128-1992","adm7":"legis-53-2001","adm8":"legis-23-1990",
            "adm9":"legis-12-1960","adm10":"legis-10-2020","adm11":"legis-42-1964","adm12":"legis-40-1980"}
    rows = []
    for f in glob.glob("*_parsed.json"):
        base = f.replace("_parsed.json", "")
        pre = PREF.get(base)
        if not pre: continue
        d = json.load(open(f, encoding="utf-8")); a = d["articles"]
        for k in d.get("order", list(a)):
            t = a[k]["text"] if isinstance(a[k], dict) else a[k]
            rows.append((f"{pre}-{k}", t))
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", action="store_true")
    ap.add_argument("--out", default="/opt/LegalMind/admin/xref_map.json")
    ap.add_argument("--cap", type=int, default=6, help="أقصى عدد أهداف لكل مصدر")
    args = ap.parse_args()

    rows = load_local() if args.local else load_db()
    id_set = {r[0] for r in rows}
    print(f"مواد التشريع: {len(rows)} | معرّفات فريدة: {len(id_set)}")

    xmap = {}
    edges = kept = dropped_missing = dropped_self = dropped_suppressed = 0
    tgt_law = {}
    unresolved = {}
    for oid, text in rows:
        if not text: continue
        src_pre = re.match(r"(legis-\d+-\d+)", oid)
        src_pre = src_pre.group(1) if src_pre else None
        targets = []
        for pre, num in extract_refs(text):
            edges += 1
            if pre == src_pre:
                dropped_self += 1; continue          # إحالة داخلية — تُترك
            tid = f"{pre}-m{num}"
            tid = _REDIRECT.get((oid, tid), tid)
            if (oid, tid) in _SUPPRESS:
                dropped_suppressed += 1
                continue
            if tid not in id_set:
                dropped_missing += 1
                unresolved[pre] = unresolved.get(pre, 0) + 1
                continue
            if tid not in targets:
                targets.append(tid)
        if targets:
            xmap[oid] = targets[:args.cap]
            kept += len(xmap[oid])
            for t in xmap[oid]:
                lp = re.match(r"(legis-\d+-\d+)", t).group(1)
                tgt_law[lp] = tgt_law.get(lp, 0) + 1

    print(f"إحالات مكتشفة: {edges} | داخلية متروكة: {dropped_self} | مُصحّحة يدويًّا (مُسقطة): {dropped_suppressed} | أهداف غير موجودة: {dropped_missing}")
    print(f"مصادر لها إحالات محفوظة: {len(xmap)} | إجمالي الحواف المحفوظة: {kept}")
    print("\nأكثر القوانين المُحال إليها (محفوظة):")
    for lp, c in sorted(tgt_law.items(), key=lambda x: -x[1])[:12]:
        print(f"  {lp}: {c}")
    print("\nأبرز الأهداف غير الموجودة (لم تُدخَل بعد):")
    for lp, c in sorted(unresolved.items(), key=lambda x: -x[1])[:12]:
        print(f"  {lp}: {c}")
    print("\nعيّنة من الحواف المحفوظة:")
    for oid in list(xmap)[:15]:
        print(f"  {oid} -> {xmap[oid]}")

    if not args.local:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(xmap, f, ensure_ascii=False)
        print(f"\n✓ كُتبت الخريطة: {args.out}  ({len(xmap)} مصدرًا، {kept} حافّة)")
    else:
        print("\n[local] لم تُكتب الخريطة.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
