# -*- coding: utf-8 -*-
"""تنسيق الطبقة كاملةً بالترتيب المعماري الصحيح.

    توليد واسع (كل القنوات) → دمج/إزالة تكرار → تقييم علاقة/زمن → ترتيب
    → قبول واعٍ بالسلطة → حزمة أدلة

ولا قصّ قبل الترتيب إطلاقًا. حجم السياق النهائي يبقى في ميزانية الإنتاج
نفسها (85,000 حرفًا) — يتوسّع التجمّع لا المُرسَل."""
from . import channels as CH
from .pool import CandidatePool
from .fusion import fuse, apply_rerank, rerank_input
from .admission import admit, PRODUCTION_BUDGET, PROTECTED_FRACTION
from .temporal import annotate
from .packet import build as build_packet
from .model import LAYER_PRINCIPLE

# مُشتقٌّ من البيانات لا مخمَّن: منحنى Recall@k على 98 نداء بحث حقيقيًا (1,959
# نتيجة خام، tools/depth_curve.py) يبلغ الهضبة عند k=9 بقيمة 0.706، ولا يزيد
# حرفًا واحدًا حتى k=20. فالعمق 12 = الهضبة + هامش 3، وما بعده **مقيسٌ بصفر
# عائد** على هذه البيانات. وهذا بنفسه أهمّ ما يقوله القياس: تعميقُ القناة
# الكثيفة وحدها **لا يمكن أن يتجاوز 0.706** مهما زاد — فالعلاج قنواتٌ أخرى،
# لا عمقٌ أكبر. (ولهذا تحديدًا لا نطارد 100% بتوسيع أعمى: التوسيع بلا ضبط
# يشتري ضجيجًا لا تغطية.)
DEFAULT_DENSE_DEPTH = 12


def retrieve(deps, query_text, vectors, anchor_ids=(), phrases=(),
             dense_depth=DEFAULT_DENSE_DEPTH, extra=()):
    """يبني تجمّع المرشحين من كل القنوات المتاحة.

    `deps` كائنٌ فيه: search(vec, types, limit) · db_rows(sql, params) ·
    fetch_texts(ids) · rerank(query, [(id,text)]) · resolve_law_prefix(n,y)
    · row_of(id). أي اعتمادية غائبة تُعطَّل قناتها بصمت **ويُسجَّل ذلك**
    (قناة معطَّلة تُعلَن، لا تُنسى — درس «الميزة الآمنة الفشل تموت صامتة»)."""
    pool = CandidatePool()
    disabled = []
    if getattr(deps, "search", None):
        CH.dense(pool, deps.search, vectors, dense_depth)
    else:
        disabled.append("dense")
    if getattr(deps, "db_rows", None):
        CH.lexical(pool, deps.db_rows, phrases)
        CH.citation(pool, deps.db_rows, query_text,
                    getattr(deps, "resolve_law_prefix", None))
        if anchor_ids:
            CH.adjacency(pool, deps.db_rows, anchor_ids)
    else:
        disabled += ["lexical", "citation", "adjacency"]
    for oid, ch, rank, score, layer in extra:      # حزم/فصول/إحالات من الإنتاج
        pool.add(oid, ch, rank, score, layer)
    if getattr(deps, "db_rows", None):
        CH.judgment_link(pool, deps.db_rows,
                         [c.object_id for c in pool.by_layer(LAYER_PRINCIPLE)])
    return pool, disabled


def run(deps, query_text, vectors, anchor_ids=(), phrases=(), issues=None,
        dense_depth=DEFAULT_DENSE_DEPTH, extra=(), budget=None,
        fraction=PROTECTED_FRACTION, norm_ar=None):
    pool, disabled = retrieve(deps, query_text, vectors, anchor_ids, phrases,
                              dense_depth, extra)
    raw_size = len(pool)
    fuse(pool)
    texts = deps.fetch_texts([c.object_id for c in pool]) or {}

    def fp(oid):
        t = texts.get(oid)
        if not t:
            return None
        s = (t.get("text") or "")
        return (norm_ar(s) if norm_ar else s)[:120] or None
    pool.dedupe_by_content(fp, layers=(LAYER_PRINCIPLE,))
    ranked = fuse(pool)

    rr = {}
    if getattr(deps, "rerank", None):
        # حصّة مضمونة لكل قناة: بلا هذا يُقصي القصُّ مرشحي القنوات الضعيفة
        # الوزن قبل أن يراهم المرتِّب، فتُهدر القناة التي وُجدت لتجاوز المتجه
        pairs = [(c.object_id, texts[c.object_id]["text"])
                 for c in rerank_input([c for c in ranked if not c.pinned])
                 if c.object_id in texts]
        try:
            rr = deps.rerank(query_text, pairs) or {}
        except Exception:
            rr = {}
    ranked = apply_rerank(ranked, rr)

    row_of = getattr(deps, "row_of", lambda i: {})
    temporal = annotate(ranked, row_of,
                        lambda i: (texts.get(i) or {}).get("text") or "",
                        getattr(deps, "xref_of", None))

    def block_size(c):
        t = texts.get(c.object_id)
        if not t:
            return None
        return len(t.get("text") or "") + 220        # تقدير وسوم الكتلة
    admitted, arep = admit(ranked, block_size, budget, fraction)
    packet, context = build_packet(admitted, texts, issues)
    return {
        "context": context, "packet": packet, "admitted": admitted,
        "pool_size_raw": raw_size, "pool_size_after_dedupe": len(pool),
        "pool_stats": pool.stats(), "admission": arep,
        "temporal": temporal, "disabled_channels": disabled,
        "reranked": len(rr),
        "selectivity": round(len(admitted) / max(1, len(pool)), 4),
    }
