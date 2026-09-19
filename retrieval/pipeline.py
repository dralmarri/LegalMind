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
from .packet import build as build_packet, block_chars
from .conflicts import detect as detect_conflicts, _cited_articles
import re as _re
_ART_ID = _re.compile(r"^.*-m(\d{1,4})$")
from .model import LAYER_PRINCIPLE, LAYER_LEGISLATION, LAYER_JUDGMENT

# مُشتقٌّ من البيانات لا مخمَّن: منحنى Recall@k على 98 نداء بحث حقيقيًا (1,959
# نتيجة خام، tools/depth_curve.py) يبلغ الهضبة عند k=9 بقيمة 0.706، ولا يزيد
# حرفًا واحدًا حتى k=20. فالعمق 12 = الهضبة + هامش 3، وما بعده **مقيسٌ بصفر
# عائد** على هذه البيانات. وهذا بنفسه أهمّ ما يقوله القياس: تعميقُ القناة
# الكثيفة وحدها **لا يمكن أن يتجاوز 0.706** مهما زاد — فالعلاج قنواتٌ أخرى،
# لا عمقٌ أكبر. (ولهذا تحديدًا لا نطارد 100% بتوسيع أعمى: التوسيع بلا ضبط
# يشتري ضجيجًا لا تغطية.)
DEFAULT_DENSE_DEPTH = 12

# حجم الدفعة = سقف `_draft_rerank` الداخلي حرفيًا، وعدد الدفعات يحدّ الزمن
RERANK_BATCH = 300
MAX_RERANK_BATCHES = 3


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
    for _e in extra:                              # حزم/فصول/إحالات من الإنتاج
        oid, ch, rank, score, layer = _e[:5]
        pool.add(oid, ch, rank, score, layer,
                 pinned=bool(_e[5]) if len(_e) > 5 else False,
                 prior=float(_e[6]) if len(_e) > 6 else 0.0)
    xmap = getattr(deps, "xref_map", None)
    if xmap:
        n = 0
        for c in list(pool):
            for tgt in (xmap.get(c.object_id) or ()):
                if tgt in pool or n >= 24:
                    continue
                n += 1
                pool.add(tgt, CH.T.CH_XREF, n, 0.0, LAYER_LEGISLATION, prior=0.30)
    if getattr(deps, "sibling_xref", None):
        # F3: إحالات المادة إلى شقيقاتها في قانونها نفسه (نظير _sib_expand الإنتاجي)
        try:
            for i, sid in enumerate(deps.sibling_xref(
                    [c.object_id for c in pool.by_layer(LAYER_LEGISLATION)]) or [], 1):
                if sid not in pool:
                    pool.add(sid, CH.T.CH_SIBLING, i, 0.0, LAYER_LEGISLATION, prior=0.30)
        except Exception:
            pass
    if getattr(deps, "db_rows", None):
        # مسار السلطة القضائية بالاتجاهين: المبدأ ← حكمه الأم، والمادة ← سلطاتها
        CH.judgment_link(pool, deps.db_rows,
                         [c.object_id for c in pool.by_layer(LAYER_PRINCIPLE)])
        CH.statute_to_judicial(pool, deps.db_rows,
                               [c.object_id for c in pool.by_layer(LAYER_LEGISLATION)])
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
        # دالة المرتِّب في الإنتاج تقصّ **داخليًا عند 300 زوج** (`[:300]` في
        # `_draft_rerank`)، فأي مرشح بعد الثلاثمئة يصل إليها ولا يعود له درجة —
        # ويظهر `RERANKER_INPUT_ONLY`. وتجمّع v2 يتجاوز 300 بانتظام (159 تشريعًا
        # + 63 مبدأً + 76 حكمًا + 27 نموذجًا في حالة واحدة مقيسة). العلاج
        # **تقطيعٌ لا قصّ**: تُنادى الدالة على دفعات بحجم سقفها ثم تُدمج
        # مخرجاتها، فيُقيَّم كل مرشح بلا استثناء. السقف ثلاث دفعات يحدّ الزمن.
        allp = [(c.object_id, texts[c.object_id]["text"])
                for c in ranked if not c.pinned and c.object_id in texts]
        batches = [allp[i:i + RERANK_BATCH]
                   for i in range(0, min(len(allp), RERANK_BATCH * MAX_RERANK_BATCHES),
                                  RERANK_BATCH)]
        if len(allp) > RERANK_BATCH * MAX_RERANK_BATCHES:
            # ما يفوق طاقة الدفعات يُنتقى بحصّة لكل قناة لا بالقصّ الأعمى
            batches = [rerank_input(
                [c for c in ranked if not c.pinned],
                cap=RERANK_BATCH * MAX_RERANK_BATCHES)]
            batches = [[(c.object_id, texts[c.object_id]["text"])
                        for c in batches[0] if c.object_id in texts]]
            batches = [batches[0][i:i + RERANK_BATCH]
                       for i in range(0, len(batches[0]), RERANK_BATCH)]
        for _b in batches:
            try:
                rr.update(deps.rerank(query_text, _b) or {})
            except Exception:
                continue
    ranked = apply_rerank(ranked, rr)

    row_of = getattr(deps, "row_of", lambda i: {})
    _txt = lambda i: (texts.get(i) or {}).get("text") or ""

    def _xref_of(c):
        """المواد التي يفسّرها هذا المصدر — تُشتق من نصّه هو لا من اعتمادية خارجية.

        كانت الطبقة تنتظر `deps.xref_of` ولا أحد يمرّره، فبقي كشف التعارض
        الزمني **ميتًا صامتًا** (صفر CONFLICT_DETECTED في التشغيل الحي، وحالة
        م167 أخرجت «خمسة أيام» بلا تحذير). الاشتقاق الآن داخلي فيعمل دائمًا."""
        if c.layer not in (LAYER_PRINCIPLE, LAYER_JUDGMENT):
            return []
        nums = _cited_articles(_txt(c.object_id))
        out = []
        for cand in ranked:
            if cand.layer != LAYER_LEGISLATION:
                continue
            m = _ART_ID.match(cand.object_id or "")
            if m and m.group(1) in nums:
                out.append(cand.object_id)
        return out[:4]
    temporal = annotate(ranked, row_of, _txt,
                        getattr(deps, "xref_of", None) or _xref_of)

    def block_size(c):
        t = texts.get(c.object_id)
        if not t:
            return None
        # **نفس دالة الطباعة**: القياس والطباعة من مصدر واحد، وإلا عاد عيب
        # إنفاق الميزانية على نص كامل ثم طباعة نص مقصوص (أو العكس).
        return block_chars(c.layer, t.get("text"))
    admitted, arep = admit(ranked, block_size, budget, fraction)
    try:
        confl = detect_conflicts(admitted,
                                 lambda i: (texts.get(i) or {}).get("text") or "",
                                 row_of)
    except Exception as _ce:
        print("[retrieval] conflicts-error:", repr(_ce), flush=True)
        confl = []
    packet, context = build_packet(admitted, texts, issues, conflicts=confl)
    return {
        "context": context, "packet": packet, "admitted": admitted,
        "pool_size_raw": raw_size, "pool_size_after_dedupe": len(pool),
        "pool_stats": pool.stats(), "admission": arep,
        "temporal": temporal, "disabled_channels": disabled,
        "conflicts": confl,
        "reranked": len(rr),
        "selectivity": round(len(admitted) / max(1, len(pool)), 4),
    }
