#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُفكِّكُ موادّ «مكرر» المدفونة في قانون الجزاء 16/1960.

الترقيمُ محقَّقٌ من صور الجريدة: الترويساتُ هي «مادة 135 مكرر»، «مادة 145 مكررا»، «مادة 149 مكررا»،
«مادة 206 مكرر أ/ب/ج»، «مادة 237 مكررا أ/ب» — والرقمُ «1» الملتصقُ ببعضها في نصّنا الرقميّ هو
**علامةُ حاشية** لا لاحقةَ مادة (نفسُ نمط «المادة 2 )))» في 3/2006). فتُسقَط الأرقامُ المجرّدة من
اللاحقة، ولا يُعتدّ إلا بحرفٍ عربيٍّ مفرد (أ/ب/ج/د).

بلا وسيط: `--dry-run` (افتراضيّ) يعرض كلَّ شيء ولا يكتب. مع `--apply` يُنشئ الكائنات الجديدة ويقتطع
متنَ الأمّ. يرفض التنفيذ عند أيّ لاحقةٍ ملتبسة أو تعارضِ معرّفات."""
from __future__ import annotations
import os, re, sys

HEAD_RE = re.compile(r"مادة\s+([0-9]+)\s*مكرر[اً]?\s*([^\n]{0,12})")
SUF_MAP = {"أ": "a", "ا": "a", "ب": "b", "ج": "c", "د": "d"}
JUNK = re.compile(r"[«»\(\)\{\}\"'‏‎0-9٠-٩\.\-–—:،\s]")


def parse_suffix(tail):
    """يُعيد (لاحقةُ المعرّف، اللاحقةُ العربية) أو (None, None) إن التبست."""
    s = JUNK.sub("", tail or "")
    if s == "":
        return "", ""
    if len(s) == 1 and s in SUF_MAP:
        return "-" + SUF_MAP[s], s
    return None, None


def main():
    apply = "--apply" in sys.argv
    import psycopg
    from psycopg.types.json import Jsonb
    dsn = os.getenv("DATABASE_URL") or "postgresql://legalmind:__SET_DATABASE_URL_ENV__@127.0.0.1:55432/legalmind"
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("SELECT id,branch,topic,title,original_text,metadata FROM knowledge_objects "
                    "WHERE id LIKE 'legis-16-1960-%' ORDER BY id")
        rows = cur.fetchall()
        existing = {r[0] for r in rows}

        plan = []          # (parent_id, head_text, [(new_id, num, ar_suffix, body)])
        for oid, branch, topic, title, txt, meta in rows:
            base = re.match(r"legis-16-1960-m([0-9]+)", oid)
            if not base:
                continue
            pnum = base.group(1)
            ms = [m for m in HEAD_RE.finditer(txt) if m.group(1) == pnum]
            if not ms:
                continue
            head = txt[:ms[0].start()].rstrip()
            if len(head) < 40:
                print("خطأ: متنُ الأمّ %s سيصير %d حرفًا — نقطةُ فصلٍ مشبوهة، أُوقف." % (oid, len(head)))
                return 1
            pieces = []
            for k, m in enumerate(ms):
                end = ms[k + 1].start() if k + 1 < len(ms) else len(txt)
                sid, ar = parse_suffix(m.group(2))
                if sid is None:
                    print("خطأ: لاحقةٌ ملتبسة في %s ⇐ «%s» — أُوقف التنفيذ."
                          % (oid, m.group(2).strip()))
                    return 1
                body = txt[m.end():end].strip()
                # ذيلُ الترويسة قد يحمل بقيّةَ السطر: نُعيدها إن لم تكن علامةَ حاشية
                lead = JUNK.sub("", m.group(2) or "")
                if lead and lead not in SUF_MAP:
                    body = (m.group(2).strip() + " " + body).strip()
                if len(body) < 30:
                    print("خطأ: متنُ المادة الجديدة في %s قصيرٌ (%d حرفًا) — أُوقف." % (oid, len(body)))
                    return 1
                nid = "legis-16-1960-m%s-mukarrar%s" % (pnum, sid)
                if nid in existing or nid in [p[0] for p in pieces]:
                    print("خطأ: تعارضُ معرّفات — %s موجودٌ سلفًا. أُوقف." % nid)
                    return 1
                pieces.append((nid, pnum, ar, body, branch, topic, meta))
            plan.append((oid, head, pieces, txt))

        print("== تفكيكُ موادّ «مكرر» المدفونة في 16/1960 ==")
        print("الوضع: %s\n" % ("تطبيقٌ فعليّ" if apply else "معاينةٌ فقط — لن يُكتب شيء"))
        total = 0
        for oid, head, pieces, txt in plan:
            print("### %s  (%d حرفًا ⇐ %d حرفًا بعد الاقتطاع)" % (oid, len(txt), len(head)))
            print("    آخرُ ما يبقى في الأمّ: …%s" % head[-90:].replace("\n", " "))
            for nid, pnum, ar, body, *_ in pieces:
                total += 1
                lbl = "مادة %s مكرر%s" % (pnum, (" " + ar) if ar else "")
                print("    ⇒ %s   [%s]  (%d حرفًا)" % (nid, lbl, len(body)))
                print("       %s…" % body[:110].replace("\n", " "))
            print()
        print("عددُ الكائنات الجديدة: %d | كائناتٌ أمٌّ تُقتطَع: %d" % (total, len(plan)))

        if not apply:
            print("\n[معاينة] لم يُكتب شيء. للتطبيق: أضف --apply")
            return 0

        sys.path.insert(0, "/opt/LegalMind/engine")
        try:
            from normalizer.canonical import normalize_text as nt
        except Exception:
            import unicodedata

            def nt(t):
                t = unicodedata.normalize("NFKC", t).replace("ـ", "")
                t = re.sub(r"[ \t]+", " ", t); t = re.sub(r" *\n *", "\n", t)
                return re.sub(r"\n{3,}", "\n\n", t).strip()

        ins = 0
        for oid, head, pieces, txt in plan:
            for nid, pnum, ar, body, branch, topic, meta in pieces:
                lbl = "مادة %s مكرر%s" % (pnum, (" " + ar) if ar else "")
                md = dict(meta or {})
                md.update({"article_number": "%s مكرر%s" % (pnum, (" " + ar) if ar else ""),
                           "split_from": oid, "split_note": "فُصلت عن الكائن الأمّ؛ الترقيم محقَّقٌ من صور الجريدة"})
                cur.execute(
                    """INSERT INTO knowledge_objects
                       (id,object_type,branch,topic,subtopic,micro_issue,title,original_text,normalized_text,
                        source_key,verification_status,authority_status,usable_as_citation,metadata)
                       VALUES (%s,'legislation_article',%s,%s,NULL,NULL,%s,%s,%s,NULL,
                               'source_verified','source_authority',TRUE,%s)
                       ON CONFLICT (id) DO UPDATE SET
                        original_text=EXCLUDED.original_text,normalized_text=EXCLUDED.normalized_text,
                        title=EXCLUDED.title,metadata=EXCLUDED.metadata,updated_at=now()""",
                    (nid, branch, topic, "%s — قانون الجزاء (16/1960)" % lbl, body, nt(body), Jsonb(md)))
                ins += 1
            cur.execute("UPDATE knowledge_objects SET original_text=%s, normalized_text=%s, updated_at=now() "
                        "WHERE id=%s", (head, nt(head), oid))
        conn.commit()
    print("\n✓ أُنشئ %d كائنًا جديدًا واقتُطعت %d كائناتٍ أمّ. شغّل reindex." % (ins, len(plan)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
