# -*- coding: utf-8 -*-
"""طبقة إظهار `metadata.source_note` — في سياق الاستوديو وفي أدوات MCP معًا.

**العلة الموثقة (§13):** كل ملاحظة كُتبت في `metadata.source_note` طوال الجلسات
الماضية **لا تصل أحدًا**: سياق الاستوديو يبني كتلته من (العنوان + النص + النشر)،
وأدوات MCP تطبع (العنوان + النص + قابلية الاستشهاد) — ولا واحدة منهما تقرأ
`source_note` أصلًا. فتنبيه م114/م130 (محكمة سوق المال بعد إلغاء فصلها)، وإحالة
الجدول (2) إلى م44 في لائحة التوثيق، وسهو «في أن» في م1 من 90/2026 — كلها موجودة
في القاعدة وغير مرئية.

**ما يفعله هذا الباتش (موضعان فقط في كل ملف):**
  أ) `admin/app.py`
     1. `_draft_fetch_texts` تقرأ `metadata->>'source_note'` كما تقرأ `publication` سلفًا.
     2. الكتلة المقبولة في السياق يُلحق بها التنبيه عبر `_draft_with_note`.
  ب) `mcp/server.py`
     1. استعلامات الأدوات الثلاث تُضيف `metadata->>'source_note' AS note`.
     2. `_fmt_row` — نقطة العرض الوحيدة للأدوات كلها — تطبع التنبيه.

**ثلاثة قيود مقصودة:**
  1. **التنبيه لا يُزاحم أحدًا:** ميزانية السياق (`LBL_BUDGET`) تُحتسب على الكتلة
     **قبل** إلحاق التنبيه، فلا يمكن للتنبيه أن يُخرج مرشَّحًا من السياق. وهذا
     يجعل أثر الباتش على الاسترجاع **صفرًا بنيويًا** لا احتمالًا.
  2. **لا يُلتبس بالنص الرسمي أبدًا:** يُغلَّف بوسم صريح «ليست من نص الجريدة ولا
     يُستشهد بها» — فقاعدة الموجّه «استشهاد حصري من السياق» لا تتحول إلى بابٍ
     لاقتباس كلامنا نحن على أنه نصُّ المشرّع.
  3. **سقف طول:** 700 حرفًا في الاستوديو و500 في MCP.

النجاح = SRCNOTE_PATCH_OK
"""

import sys, io, os, re, ast, datetime

APP = "/opt/LegalMind/admin/app.py"
MCP = "/opt/LegalMind/mcp/server.py"
STAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

# ═══════════════ مراسٍ حرفية — كلٌّ يجب أن يرد مرة واحدة بالضبط ═══════════════

APP_A1_OLD = '''            "SELECT id, object_type, branch, topic, subtopic, title, original_text, "
            "metadata->>'publication' "
            "FROM knowledge_objects WHERE id = ANY(%s)", (list(ids),))
        for i, ot, br, tp, st, ti, tx, pb in cur.fetchall():
            out[i] = {"object_type": ot, "branch": br, "topic": tp,
                      "subtopic": st, "title": ti, "text": tx, "publication": pb}
    return out
'''

APP_A1_NEW = '''            "SELECT id, object_type, branch, topic, subtopic, title, original_text, "
            "metadata->>'publication', metadata->>'source_note' "
            "FROM knowledge_objects WHERE id = ANY(%s)", (list(ids),))
        for i, ot, br, tp, st, ti, tx, pb, nt in cur.fetchall():
            out[i] = {"object_type": ot, "branch": br, "topic": tp,
                      "subtopic": st, "title": ti, "text": tx, "publication": pb,
                      "note": nt}
    return out


# ─── إظهار ملاحظات المحرِّر (metadata.source_note) في السياق ─────────────────
# كانت مكتوبةً في القاعدة ولا تصل أحدًا (الحدّ الموثق في §13). ثلاثة قيود:
# (1) تُلحق **بعد** احتساب ميزانية الكتلة، فلا تُخرج مرشَّحًا من السياق أبدًا؛
# (2) تُغلَّف بوسم صريح أنها ليست من نص الجريدة ولا يُستشهد بها — فلا تُقتبس
#     ملاحظتنا على أنها نصُّ المشرّع؛ (3) بسقف طول.
_NOTE_CAP_DRAFT = 700
_NOTE_OPEN = "⟦ملاحظة توثيقية من محرِّر القاعدة — ليست من نص الجريدة ولا يُستشهد بها⟧"


def _draft_note_text(note, cap=_NOTE_CAP_DRAFT):
    nt = (note or "").strip()
    if not nt:
        return ""
    if len(nt) > cap:
        nt = nt[:cap].rstrip() + " […]"
    return "\\n\\n" + _NOTE_OPEN + "\\n" + nt


def _draft_with_note(block, note):
    """يُدرج التنبيه داخل الكتلة قبل وسم الإغلاق — لا بعده فيبقى معلّقًا."""
    nt = _draft_note_text(note)
    if not nt:
        return block
    tail = "\\n</مصدر>"
    if block.endswith(tail):
        return block[:-len(tail)] + nt + tail
    return block + nt
'''

APP_A2_OLD = '''        seen.add(oid)
        lbl_used[label] = lbl_used.get(label, 0) + len(block)
        parts.append(block)
    context = "\\n\\n".join(parts)
'''

APP_A2_NEW = '''        seen.add(oid)
        # الميزانية محسوبة على الكتلة وحدها — التنبيه يُلحق بعدها فلا يزاحم مرشَّحًا
        lbl_used[label] = lbl_used.get(label, 0) + len(block)
        parts.append(_draft_with_note(block, t.get("note")))
    context = "\\n\\n".join(parts)
'''

MCP_FMT_OLD = '''    tx = (row.get("txt") or row.get("original_text") or "").strip()
    if len(tx) > cap:
        tx = tx[:cap] + " …(مقتطع — اجلب النص الكامل بأداة get_object)"
    return head + "\\n" + tx
'''

MCP_FMT_NEW = '''    tx = (row.get("txt") or row.get("original_text") or "").strip()
    if len(tx) > cap:
        tx = tx[:cap] + " …(مقتطع — اجلب النص الكامل بأداة get_object)"
    # ملاحظة محرِّر القاعدة (metadata.source_note) — كانت مكتوبة ولا تظهر في أي
    # أداة. تُعرض بوسم صريح أنها ليست من نص الجريدة، فلا تُقتبس كأنها نصٌّ رسمي.
    nt = (row.get("note") or "").strip()
    if nt:
        if len(nt) > _NOTE_CAP:
            nt = nt[:_NOTE_CAP].rstrip() + " […]"
        tx += ("\\n\\n⟦ملاحظة توثيقية من محرِّر القاعدة — ليست من نص الجريدة "
               "ولا يُستشهد بها⟧\\n" + nt)
    return head + "\\n" + tx
'''

MCP_CAP_OLD = '''def _fmt_row(row, score=None, cap=1600):
'''
MCP_CAP_NEW = '''_NOTE_CAP = 500


def _fmt_row(row, score=None, cap=1600):
'''

MCP_SELECTS = [
    ('''    rows = _pg("SELECT id, object_type, title, left(original_text, 1700) AS txt, "
               "usable_as_citation FROM knowledge_objects WHERE id = ANY(%s)", (ids,))''',
     '''    rows = _pg("SELECT id, object_type, title, left(original_text, 1700) AS txt, "
               "usable_as_citation, metadata->>'source_note' AS note "
               "FROM knowledge_objects WHERE id = ANY(%s)", (ids,))'''),
    ('''    rows = _pg("SELECT id, object_type, branch, topic, subtopic, title, original_text, "
               "usable_as_citation FROM knowledge_objects WHERE id = %s", (oid,))''',
     '''    rows = _pg("SELECT id, object_type, branch, topic, subtopic, title, original_text, "
               "usable_as_citation, metadata->>'source_note' AS note "
               "FROM knowledge_objects WHERE id = %s", (oid,))'''),
    ('''    rows = _pg("SELECT id, object_type, title, original_text, usable_as_citation "
               "FROM knowledge_objects WHERE id = %s OR id LIKE %s ORDER BY id LIMIT 6",
               (base, base + "-%"))''',
     '''    rows = _pg("SELECT id, object_type, title, original_text, usable_as_citation, "
               "metadata->>'source_note' AS note "
               "FROM knowledge_objects WHERE id = %s OR id LIKE %s ORDER BY id LIMIT 6",
               (base, base + "-%"))'''),
]


def _apply(src, pairs, label):
    for old, new in pairs:
        n = src.count(old)
        if n != 1:
            raise SystemExit("ANCHOR_FAIL[%s]: مرساة وردت %d مرة (المتوقع 1):\n%s"
                             % (label, n, old[:150]))
        src = src.replace(old, new)
    return src


def main():
    for path in (APP, MCP):
        if not os.path.exists(path):
            raise SystemExit("MISSING_FILE: " + path)

    app_src = io.open(APP, encoding="utf-8").read()
    mcp_src = io.open(MCP, encoding="utf-8").read()

    # إعادة التشغيل عديمة الأثر
    if "_draft_with_note" in app_src and "_NOTE_CAP" in mcp_src:
        print("ALREADY_PATCHED: الطبقة مركّبة سلفًا — لا تغيير.")
        print("\nSRCNOTE_PATCH_OK")
        return

    app_new = _apply(app_src, [(APP_A1_OLD, APP_A1_NEW), (APP_A2_OLD, APP_A2_NEW)], "app")
    mcp_new = _apply(mcp_src, [(MCP_CAP_OLD, MCP_CAP_NEW), (MCP_FMT_OLD, MCP_FMT_NEW)]
                     + MCP_SELECTS, "mcp")

    for name, src in (("app.py", app_new), ("server.py", mcp_new)):
        try:
            ast.parse(src)
        except SyntaxError as e:
            raise SystemExit("SYNTAX_FAIL[%s]: %s" % (name, e))

    # حارس نطاق: لا يتغير في الملفين إلا ما قصدناه
    d_app = len(app_new) - len(app_src)
    d_mcp = len(mcp_new) - len(mcp_src)
    print("حجم التغيير: app.py +%d حرفًا، server.py +%d حرفًا" % (d_app, d_mcp))
    if not (800 < d_app < 2200) or not (400 < d_mcp < 1400):
        raise SystemExit("DELTA_UNEXPECTED: حجم التغيير خارج المدى المتوقع — أوقفت.")

    for path, src in ((APP, app_new), (MCP, mcp_new)):
        bak = path + ".bak_srcnote_" + STAMP
        io.open(bak, "w", encoding="utf-8").write(
            io.open(path, encoding="utf-8").read())
        io.open(path, "w", encoding="utf-8").write(src)
        print("  %s — مرقّع (النسخة الاحتياطية: %s)" % (path, bak))

    print("\nSRCNOTE_PATCH_OK")


if __name__ == "__main__":
    main()
