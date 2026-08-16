#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""معاينةُ عيوب قانون الجزاء 16/1960 — لا تكتب شيئًا في القاعدة إطلاقًا.
تعرض: (1) موادَّ «مكرر» المدفونةَ داخل كائنات آبائها مع نقاط الفصل والمعرّفات المقترحة ونصوصها كاملةً،
(2) مواضعَ الأقواس المعكوسة بسياقها، (3) مواضعَ الحروف/الحركات المضاعفة بسياقها.
تُقرأ مخرجاتُها ثمّ يُبنى الإصلاح عليها — لا إصلاح بلا معاينة."""
import os, re, sys

MKR_RE = re.compile(r"^\s*مادة\s+([0-9]+)\s*مكرر[اً]?\s*(.*?)\s*$", re.M)
SUF = {"أ": "a", "ا": "a", "ب": "b", "ج": "c", "د": "d", "1": "1", "2": "2", "3": "3", "": ""}


def suffix_id(raw):
    """يُحوّل لاحقة «مكرر» إلى جزءٍ صالحٍ للمعرّف؛ يُعيد None إن كانت اللاحقة تالفةً/ملتبسة."""
    s = re.sub(r"[«»\(\)\"']", " ", raw).strip()
    parts = [p for p in re.split(r"\s+", s) if p]
    out = []
    for p in parts:
        if p not in SUF:
            return None
        out.append(SUF[p])
    return "-".join(x for x in out if x) or "1"


def main():
    import psycopg
    dsn = os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
    with psycopg.connect(dsn) as cx, cx.cursor() as cur:
        cur.execute("SELECT id,title,original_text FROM knowledge_objects WHERE id LIKE 'legis-16-1960-%'")
        rows = cur.fetchall()
    by_id = {r[0]: (r[1], r[2]) for r in rows}
    print("إجمالي كائنات 16/1960 =", len(rows))

    print("\n" + "=" * 72)
    print("أوّلًا: موادُّ «مكرر» المدفونة — نقاطُ الفصل والمعرّفات المقترحة")
    print("=" * 72)
    total_new = 0
    for oid, title, txt in sorted(rows):
        ms = list(MKR_RE.finditer(txt))
        if not ms:
            continue
        base = re.match(r"legis-16-1960-m([0-9]+)", oid)
        print("\n### %s" % oid)
        print("    العنوان الحالي: %s" % (title or "—"))
        print("    طولُ النصّ: %d حرفًا | عددُ المواد المدفونة: %d" % (len(txt), len(ms)))
        head = txt[:ms[0].start()].strip()
        print("\n  [الأصل يبقى في الكائن الأمّ] — %d حرفًا" % len(head))
        print("  " + head[:200].replace("\n", " ") + (" …" if len(head) > 200 else ""))
        for k, m in enumerate(ms):
            end = ms[k + 1].start() if k + 1 < len(ms) else len(txt)
            body = txt[m.end():end].strip()
            num, raw_suf = m.group(1), m.group(2)
            sid = suffix_id(raw_suf)
            if sid is None or (base and num != base.group(1)):
                flag = "  ⚠️ لاحقةٌ تالفة/غيرُ متوقّعة — تحتاج قرارًا يدويًّا"
                newid = "(يدويّ)"
            else:
                flag = ""
                newid = "legis-16-1960-m%s-mukarrar-%s" % (num, sid)
                total_new += 1
            print("\n  [مادة مقترحة %d] عنوانُ الفصل الخام: «مادة %s مكرر %s»%s"
                  % (k + 1, num, raw_suf, flag))
            print("    المعرّف المقترح: %s" % newid)
            print("    النصّ الكامل (%d حرفًا):" % len(body))
            for ln in body.split("\n"):
                print("      " + ln)
    print("\n  ⇒ عددُ الكائنات الجديدة المقترحة: %d" % total_new)

    print("\n" + "=" * 72)
    print("ثانيًا: الأقواس المعكوسة اتجاهيًّا — بسياقها")
    print("=" * 72)
    for oid, title, txt in sorted(rows):
        hits = list(re.finditer(r"\)\s*[0-9٠-٩][^()\n]{0,40}", txt))
        if not hits:
            continue
        print("\n### %s" % oid)
        for h in hits:
            s = max(0, h.start() - 60)
            print("    …%s…" % txt[s:h.end() + 20].replace("\n", " "))

    print("\n" + "=" * 72)
    print("ثالثًا: الحروف/الحركات المضاعفة — بسياقها")
    print("=" * 72)
    pat = re.compile(r"[ء-ي]*(?:([ب-ي])\1{2,}|ًً|ُُ|ِِ)[ء-ي]*")
    dbl2 = re.compile(r"(?:\S*(?:جج|تت|ضض|صص|لل|نن|بب|مم|ذذ|قق|كك)\S*)")
    for oid, title, txt in sorted(rows):
        found = set()
        for m in pat.finditer(txt):
            found.add(m.group(0))
        for m in dbl2.finditer(txt):
            w = m.group(0)
            if re.search(r"(جج|تت|ضض|صص|ذذ)", w) and len(w) > 3:
                found.add(w)
        if not found:
            continue
        print("\n### %s : %s" % (oid, " | ".join(sorted(found)[:12])))
    print("\n=== انتهت المعاينة — لم يُكتب شيءٌ في القاعدة ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
