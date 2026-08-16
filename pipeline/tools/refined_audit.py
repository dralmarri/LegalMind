#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تدقيق مُنقّح (قراءة فقط): يكشف تلوّث «عنوان قسم مُلحق» في ذيل المواد:
سطرٌ أخير قصير بلا علامة ختام، يعقب سطرًا منتهيًا بعلامة ختام = عنوان باب/فصل/موضوعٍ تالٍ
التصق بالمادة أثناء الاستخراج. يطبع أيضًا المواد القصيرة كاملةً وذيول '__'. لا يكتب في القاعدة."""
import os, re, json
from collections import defaultdict

DSN = os.getenv("DATABASE_URL") or \
    "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
TERM = set('.؛!؟')
FUNC = {"في", "على", "من", "الى", "عن", "و", "او", "التي", "الذي", "مع", "بين",
        "أو", "إلى", "هذا", "هذه", "ذلك", "أن", "ان", "التى"}


def law(oid):
    m = re.match(r'(legis-\d+-\d+|lreg-\d+-\d+-k\d+)', oid)
    return m.group(1) if m else oid


def trailing_heading(text):
    """يعيد السطر الأخير إن بدا عنوان قسمٍ ملحقًا (لا جزءًا من المادة)، وإلا None."""
    ne = [l.strip() for l in (text or "").split("\n") if l.strip()]
    if len(ne) < 2:
        return None
    last, prev = ne[-1], ne[-2]
    if not last or not prev:
        return None
    if len(last) > 45:                      # العناوين قصيرة
        return None
    if last[-1] in TERM or last[-1] == ':':  # العنوان لا ينتهي بعلامة ختام
        return None
    if re.match(r'^[\d\-•*()]', last):       # قوائم/بنود مرقّمة ليست عناوين
        return None
    if prev[-1] not in TERM:                  # الجملة السابقة يجب أن تكون مكتملة
        return None
    lw = re.sub(r'[^؀-ۿ]', '', last.split()[-1]) if last.split() else ""
    nlw = re.sub(r'[أإآ]', 'ا', re.sub(r'[ىي]', 'ي', lw)).replace('ة', 'ه')
    if nlw in FUNC:                           # ينتهي بكلمة وظيفية ⇒ بترٌ لا عنوان
        return None
    return last


def main():
    import psycopg
    with psycopg.connect(DSN) as c, c.cursor() as cur:
        cur.execute("SELECT id, coalesce(original_text,''), coalesce(title,'') "
                    "FROM knowledge_objects WHERE id LIKE 'legis-%' OR id LIKE 'lreg-%' ORDER BY id")
        rows = cur.fetchall()
    by = {r[0]: r for r in rows}

    short = []
    if os.path.exists("/tmp/cleanup_audit.json"):
        short = json.load(open("/tmp/cleanup_audit.json")).get("short", [])
    print("===== SHORT (النصّ كامل) =====")
    for oid in short:
        r = by.get(oid)
        if r:
            print(f"\n• {oid} [{r[2][:45]}]\n   {r[1].strip()!r}")

    cand = defaultdict(list)
    junk_us = []
    for oid, text, title in rows:
        h = trailing_heading(text)
        if h:
            cand[law(oid)].append((oid, h))
        if '__' in text or '�' in text:
            junk_us.append(oid)

    total = sum(len(v) for v in cand.values())
    print(f"\n===== تلوّث «عنوان قسم مُلحق» في الذيل: {total} مرشّحًا في {len(cand)} قانونًا =====")
    for lp in sorted(cand, key=lambda k: -len(cand[k])):
        print(f"\n— {lp} [{len(cand[lp])}]:")
        for oid, h in cand[lp][:15]:
            print(f"    {oid}  ⟵ {h!r}")
        if len(cand[lp]) > 15:
            print(f"    … و{len(cand[lp]) - 15} أخرى")

    print(f"\n===== ذيول '__' أو � : {len(junk_us)} مادة =====")
    print("   ", junk_us[:25])

    json.dump({"trailing_heading": {k: v for k, v in cand.items()}, "junk_underscore": junk_us},
              open("/tmp/refined_audit.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n✓ كُتبت: /tmp/refined_audit.json")


if __name__ == "__main__":
    main()
