#!/usr/bin/env python3
# رقعة قناة الاسترجاع بالموضوع (2026-10-10) على admin/app.py — خلف علم LEGALMIND_TOPIC_CHANNEL (مطفأة افتراضيًا).
# المبادئ الأقرب للسؤال «تصوّت» بتبويب المصدر الذي وضعها فيه محررو المجموعات (topic/subtopic في حمولة Qdrant)،
# والموضوع الغالب يُبحث داخله بمرشّح Qdrant فتُضاف أقرب مبادئه مرشحاتٍ — تمر بالمرتِّب والميزانية كغيرها.
# الاستعمال: patch_topic_channel.py <app.py> ؛ عديمة الأثر عند التكرار (TOPIC_PATCH_ALREADY).
import sys
path = sys.argv[1]
src = open(path, encoding="utf-8").read()
MARK = "# ==== قناة الاسترجاع بالموضوع"
if MARK in src:
    print("TOPIC_PATCH_ALREADY"); sys.exit(0)

HELPERS = '''# ==== قناة الاسترجاع بالموضوع (2026-10-10) — خلف علم LEGALMIND_TOPIC_CHANNEL، مطفأة افتراضيًا ====
# التبويب المرجعي هو تبويب المصدر وحده (metadata.taxonomy_source — محررو المجموعات) لا فهم النموذج.
_TOPIC_IDX = {"built": False, "sizes": {}}

def _topic_index():
    if not _TOPIC_IDX["built"]:
        _rows = db_rows("SELECT topic, coalesce(subtopic, '') AS sub, count(*) AS n FROM knowledge_objects "
                        "WHERE object_type = 'judicial_principle' AND metadata ? 'taxonomy_source' "
                        "GROUP BY 1, 2")
        _TOPIC_IDX["sizes"] = {((r["topic"] or ""), r["sub"]): int(r["n"]) for r in _rows}
        _TOPIC_IDX["built"] = True
    return _TOPIC_IDX["sizes"]

def _draft_search_must(vector, must, limit):
    body = _djson.dumps({"vector": vector, "limit": limit, "with_payload": True,
                         "filter": {"must": must}}).encode("utf-8")
    req = _durl.Request(_DRAFT_QDRANT + "/collections/" + _DRAFT_COLL + "/points/search",
                        data=body, headers={"Content-Type": "application/json"})
    with _durl.urlopen(req, timeout=30) as r:
        return _djson.loads(r.read())["result"]

def _draft_topic_channel(vectors, best, taken, k_keys=2, per_key=8, min_support=2):
    """best: {oid: (label, score, payload)} من البحث الكثيف قبل القصّ. يعيد (المواضيع المختارة، [(oid, score, payload)])."""
    import collections as _c
    sizes = _topic_index()
    votes, support = _c.defaultdict(float), _c.Counter()
    for _oid, (_lb, _sc, _p) in best.items():
        if _lb != "مبدأ قضائي":
            continue
        _key = ((_p.get("topic") or ""), (_p.get("subtopic") or ""))
        _n = sizes.get(_key, 0)
        # موضوع بلا فرع ضخم (ابتلع ما بعده في الاستخراج) لا يُعتمد وعاءً — ضجيجه أكبر من نفعه
        if _n < 3 or (not _key[1] and _n > 300):
            continue
        votes[_key] += float(_sc or 0.0)
        support[_key] += 1
    chosen = sorted((k for k in votes if support[k] >= min_support), key=lambda k: -votes[k])[:k_keys]
    out, got = [], {}
    for _key in chosen:
        _must = [{"key": "object_type", "match": {"value": "judicial_principle"}},
                 {"key": "topic", "match": {"value": _key[0]}}]
        if _key[1]:
            _must.append({"key": "subtopic", "match": {"value": _key[1]}})
        _cand = {}
        for _v in vectors:
            for _h in _draft_search_must(_v, _must, 4):
                _p = _h.get("payload") or {}
                _oid = _p.get("object_id")
                if _oid and (_oid not in _cand or _h.get("score", 0) > _cand[_oid][0]):
                    _cand[_oid] = (_h.get("score", 0), _p)
        for _oid, (_sc, _p) in sorted(_cand.items(), key=lambda kv: -kv[1][0])[:per_key]:
            if _oid in taken or _oid in got:
                continue
            got[_oid] = 1
            out.append((_oid, _sc, _p))
    return [{"topic": k[0], "subtopic": k[1], "votes": round(votes[k], 3), "support": support[k],
             "size": sizes.get(k, 0)} for k in chosen], out
# ==== نهاية قناة الاسترجاع بالموضوع ====

'''

CALL = '''    # قناة الاسترجاع بالموضوع (خلف علم، مطفأة افتراضيًا): مرشحات إضافية من داخل موضوع المصدر الغالب
    topic_added = []
    if (_draft_env("LEGALMIND_TOPIC_CHANNEL") or "").strip() in ("1", "true", "on"):
        try:
            _tsel, _tout = _draft_topic_channel(vectors, best, {p.get("object_id") for _l, _s, p in hits})
            for _toid, _tsc, _tp in _tout:
                hits.append(("مبدأ قضائي", _tsc, dict(_tp, _source="topic")))
                topic_added.append(_toid)
            print("[draft] topic:", _djson.dumps({"chosen": _tsel, "added": len(topic_added)},
                                                 ensure_ascii=False)[:1500], flush=True)
        except Exception as _te:
            print("[draft] topic-error:", repr(_te), flush=True)
            topic_added = []
'''

def once(s, anchor, new, where="before"):
    n = s.count(anchor)
    if n != 1:
        print("ANCHOR_FAIL", n, anchor[:60]); sys.exit(2)
    return s.replace(anchor, (new + anchor) if where == "before" else (anchor + new))

src = once(src, "def _draft_fetch_texts(ids):", HELPERS)
src = once(src, "    # ضمانة تشريعية: (1) حزم الفصول الحاكمة حسب نوع المطالبة، (2) بحث معجمي عام\n", CALL)
src = once(src, '            "xref_added": len(xref_added),\n', '            "topic_added": len(topic_added),\n', "after")
src = once(src, '"lex_added": lex_added, "sources_used": len(parts),',
           "", "before").replace('"lex_added": lex_added, "sources_used": len(parts),',
                                 '"lex_added": lex_added, "topic_added": topic_added, "sources_used": len(parts),')
open(path, "w", encoding="utf-8").write(src)
print("TOPIC_PATCH_APPLIED")
