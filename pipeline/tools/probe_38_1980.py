#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""معاينةُ بنية قانون المرافعات 38/1980 — قراءةٌ فقط.
الغرض: هل بابُ الاختصاص (النوعيّ والقيميّ والمحلّيّ) مُدخَلٌ أصلًا؟ يُكشف ذلك بثلاثة أشياء:
(1) جردُ الأرقام الموجودة وثغراتُها، (2) بحثٌ بستّة ألفاظٍ بديلة لصياغة الاختصاص المحلّيّ،
(3) طباعةُ المواد 20-70 بأوائلها لتُقرأ خريطةُ الأبواب. لا يُكتب شيءٌ في القاعدة."""
import os, re, sys

NEEDLES = ["يقع بدائرتها", "يقع في دائرتها", "تقع بدائرتها", "دائرتها", "موطن المدعى عليه",
           "موطن المدعي عليه", "محل اقامة المدعى", "الاختصاص المحلي", "يكون الاختصاص",
           "تختص المحكمة", "المحكمة المختصة", "الاختصاص القيمي", "الاختصاص النوعي"]


def num(oid):
    m = re.search(r"m(\d+)", oid)
    return int(m.group(1)) if m else 10 ** 6


def main():
    import psycopg
    dsn = os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
    with psycopg.connect(dsn) as cx, cx.cursor() as cur:
        cur.execute("SELECT id,title,original_text FROM knowledge_objects WHERE id LIKE 'legis-38-1980-%'")
        rows = cur.fetchall()
    rows.sort(key=lambda r: num(r[0]))
    nums = sorted({num(r[0]) for r in rows if num(r[0]) < 10 ** 6})
    print("إجمالي الكائنات = %d | مواد مرقّمة = %d | المدى = %d..%d"
          % (len(rows), len(nums), nums[0], nums[-1]))
    gaps, prev = [], None
    for n in nums:
        if prev is not None and n > prev + 1:
            gaps.append((prev + 1, n - 1))
        prev = n
    print("ثغراتُ الترقيم (%d): %s" % (len(gaps),
          ", ".join("%d-%d" % g if g[0] != g[1] else str(g[0]) for g in gaps[:30]) or "لا شيء"))
    miss = sum(b - a + 1 for a, b in gaps)
    print("إجمالي الموادّ الغائبة داخل المدى = %d" % miss)

    print("\n" + "=" * 70)
    print("بحثُ ألفاظ الاختصاص")
    print("=" * 70)
    for nd in NEEDLES:
        hit = [r[0].replace("legis-38-1980-", "") for r in rows if nd in (r[2] or "")]
        print(" «%-22s» ⇐ %2d : %s" % (nd, len(hit), ", ".join(hit[:12]) or "—"))

    print("\n" + "=" * 70)
    print("خريطةُ المواد 20-70 (أوائلُها)")
    print("=" * 70)
    for oid, t, x in rows:
        n = num(oid)
        if 20 <= n <= 70:
            print(" %-8s %s" % (oid.replace("legis-38-1980-", ""),
                                re.sub(r"\s+", " ", x or "").strip()[:96]))

    print("\n" + "=" * 70)
    print("العناوين المميّزة (إن حُفظت الأبواب في العنوان)")
    print("=" * 70)
    seen = []
    for oid, t, x in rows:
        t = (t or "").strip()
        if t and t not in seen:
            seen.append(t)
    for t in seen[:6]:
        print("  •", t[:100])
    print("  … عددُ العناوين المتمايزة =", len(seen))
    return 0


if __name__ == "__main__":
    sys.exit(main())
