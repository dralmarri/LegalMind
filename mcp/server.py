# -*- coding: utf-8 -*-
"""بوابة MCP للقراءة فقط — قاعدة LegalMind القانونية الكويتية.
قراءة فقط بنيويًا: كل استعلامات هذا الملف SELECT حصرًا، ولا أداة تكتب أو تعدل.
البحث الدلالي بنفس محرك الاستوديو حرفيًا: embed_query_cli (البيئة الثقيلة) ← Qdrant ← PG."""
import os
import re
import json
import subprocess

import requests

QDRANT = "http://127.0.0.1:6333/collections/legalmind_multilingual_e5_base_v1/points/search"
HEAVY_PY = "/opt/LegalMind/.venv/bin/python"
EMBED_CLI = "/opt/LegalMind/engine/embed_query_cli.py"
INVENTORY = "/opt/LegalMind/docs/legislation_inventory.md"


def _env(name):
    v = os.getenv(name)
    if v:
        return v
    try:
        with open("/opt/LegalMind/deploy/.env", encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if ln.startswith("export "):
                    ln = ln[7:].strip()
                if ln.startswith(name + "="):
                    return ln.split("=", 1)[1].strip().strip('"').strip("'") or None
    except Exception:
        pass
    return None


def _pg(sql, args=()):
    # قراءة فقط: هذه الدالة تُستدعى بSELECT حصرًا في هذا الملف كله
    import psycopg
    with psycopg.connect(_env("DATABASE_URL")) as c, c.cursor() as cur:
        # وسائط فارغة = تنفيذ مباشر (محلل العلامات يتعثر على % الحرفية في LIKE)
        if args:
            cur.execute(sql, args)
        else:
            cur.execute(sql)
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def _embed(q):
    env = dict(os.environ)
    env.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                "HF_HOME": "/opt/legalmind-data/hf"})
    p = subprocess.run([HEAVY_PY, EMBED_CLI], input=q.encode("utf-8"),
                       capture_output=True, timeout=180, env=env)
    vec = json.loads(p.stdout.decode("utf-8"))
    if not vec:
        raise RuntimeError("تعذر تضمين الاستعلام")
    return vec


def _fmt_row(row, score=None, cap=1600):
    head = "«%s» [%s]" % (row.get("title") or row["id"], row["id"])
    if score is not None:
        head += " (تشابه %.3f)" % score
    if row.get("usable_as_citation") is False:
        head += " — ⚠ صيغة استرشادية غير قابلة للاستشهاد"
    tx = (row.get("txt") or row.get("original_text") or "").strip()
    if len(tx) > cap:
        tx = tx[:cap] + " …(مقتطع — اجلب النص الكامل بأداة get_object)"
    return head + "\n" + tx


def search_legal(query: str, kind: str = "الكل", limit: int = 8) -> str:
    """بحث دلالي في قاعدة المعرفة القانونية الكويتية (58 ألف كائن: تشريعات نافذة بنصوصها
    الرسمية، ومبادئ محكمة التمييز بأسانيدها). kind: «الكل» أو «تشريع» أو «مبدأ»."""
    query = (query or "").strip()
    if len(query) < 2:
        return "اكتب استعلامًا لا يقل عن حرفين."
    limit = max(1, min(int(limit or 8), 20))
    flt = None
    if kind == "تشريع":
        flt = {"must": [{"key": "object_type", "match": {"any": [
            "legislation_article", "legislation_issuing_article", "legislation_preamble"]}}]}
    elif kind == "مبدأ":
        flt = {"must": [{"key": "object_type", "match": {"value": "judicial_principle"}}]}
    body = {"vector": _embed(query), "limit": limit, "with_payload": True}
    if flt:
        body["filter"] = flt
    r = requests.post(QDRANT, json=body, timeout=30).json()
    hits = r.get("result") or []
    ids = [h["payload"]["object_id"] for h in hits
           if h.get("payload", {}).get("object_id")]
    if not ids:
        return "لا نتائج مطابقة."
    rows = _pg("SELECT id, object_type, title, left(original_text, 1700) AS txt, "
               "usable_as_citation FROM knowledge_objects WHERE id = ANY(%s)", (ids,))
    by = {x["id"]: x for x in rows}
    out = []
    for h in hits:
        row = by.get(h["payload"].get("object_id"))
        if row:
            out.append(_fmt_row(row, h.get("score")))
    return "\n\n───\n\n".join(out) if out else "لا نتائج مطابقة."


def get_object(object_id: str) -> str:
    """النص الكامل الموثق لأي كائن بمعرفه (مثل legis-38-1980-m166 أو jprin-911-2006-…)."""
    oid = (object_id or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9._-]{3,80}", oid):
        return "معرف غير صالح."
    rows = _pg("SELECT id, object_type, branch, topic, subtopic, title, original_text, "
               "usable_as_citation FROM knowledge_objects WHERE id = %s", (oid,))
    if not rows:
        return "لا كائن بهذا المعرف: " + oid
    row = rows[0]
    meta = " | ".join(str(row[k]) for k in ("object_type", "branch", "topic", "subtopic") if row.get(k))
    return _fmt_row(row, cap=14000) + "\n\n[التبويب: " + meta + "]"


def get_article(law_number: int, law_year: int, article: str) -> str:
    """نص مادة بعينها من قانون بعينه: get_article(38, 1980, "166") = م166 مرافعات.
    يقبل أرقام المواد ولواحقها (مثل 237-mukarrar-a)."""
    art = re.sub(r"[^0-9A-Za-z-]", "", str(article or ""))
    if not art:
        return "رقم مادة غير صالح."
    base = "legis-%d-%d-m%s" % (int(law_number), int(law_year), art)
    rows = _pg("SELECT id, object_type, title, original_text, usable_as_citation "
               "FROM knowledge_objects WHERE id = %s OR id LIKE %s ORDER BY id LIMIT 6",
               (base, base + "-%"))
    if not rows:
        return ("لا مادة بهذا المعرف (%s). تحقق من رقم القانون وسنته — "
                "استعمل legislation_inventory لجرد القوانين المدخلة." % base)
    return "\n\n───\n\n".join(_fmt_row(r, cap=14000) for r in rows)


def legislation_inventory() -> str:
    """الجرد الحي للتشريعات واللوائح المدخلة في القاعدة (يُراجع قبل أي حكم بوجود قانون أو غيابه).
    يُقرأ من ملف الجرد الموثق إن وُجد، وإلا يُحتسب من القاعدة مباشرة."""
    try:
        with open(INVENTORY, encoding="utf-8") as f:
            tx = f.read()
        if len(tx) > 500:
            return tx[:24000]
    except Exception:
        pass
    rows = _pg(
        "SELECT substring(id from '^((?:legis|regl)-[A-Za-z]*-?[0-9]+-[0-9]+)') AS law, "
        "count(*) AS n, min(title) AS sample "
        "FROM knowledge_objects WHERE id LIKE 'legis-%' OR id LIKE 'regl-%' "
        "GROUP BY 1 HAVING substring(id from '^((?:legis|regl)-[A-Za-z]*-?[0-9]+-[0-9]+)') "
        "IS NOT NULL ORDER BY 1")
    out = ["الجرد الحي (محسوب من القاعدة الآن) — %d تشريعًا/لائحة:" % len(rows), ""]
    for r in rows:
        name = (r.get("sample") or "").split("—")[-1].strip()
        out.append("- %s (%d كائنًا)%s" % (r["law"], r["n"], (" — " + name) if name else ""))
    return "\n".join(out)[:24000]


INSTR = ("قاعدة معرفة قانونية كويتية موثقة (تشريعات بنصوصها الرسمية + مبادئ محكمة التمييز). "
         "قواعد الأمانة ملزمة: استشهد حصرًا بما تعيده هذه الأدوات نصًا، ولا تنسب لمادة أو طعن "
         "ما ليس في نصه، وما لم تجده هنا فأفصح أنه غير موجود في القاعدة بدل الاجتهاد. "
         "الصيغ الموسومة «غير قابلة للاستشهاد» استرشادية فقط.")

try:
    from mcp.server.fastmcp import FastMCP
except ModuleNotFoundError:          # بنية الإصدار 2 من الحزمة الرسمية
    from fastmcp import FastMCP

try:
    _srv = FastMCP("LegalMind", host="127.0.0.1", port=8090,
                   instructions=INSTR, stateless_http=True)
except TypeError:
    _srv = FastMCP("LegalMind", host="127.0.0.1", port=8090, instructions=INSTR)

_srv.tool()(search_legal)
_srv.tool()(get_object)
_srv.tool()(get_article)
_srv.tool()(legislation_inventory)

if __name__ == "__main__":
    _srv.run(transport="streamable-http")
