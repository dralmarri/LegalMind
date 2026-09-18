# -*- coding: utf-8 -*-
"""الدمج التبادلي بين القنوات (Reciprocal Rank Fusion).

لماذا RRF لا جمع الدرجات: درجات القنوات **غير قابلة للمقارنة** — تشابه المتجه
E5 يتراوح عمليًا في نطاق ضيق مرتفع (0.82–0.89 في قياساتنا الحية)، بينما القناة
المعجمية بلا درجة أصلًا، وقناة الاستشهاد الصريح ثنائية. جمعُها مباشرةً يجعل
فروقًا لا معنى لها تحكم الترتيب. RRF يستعمل **الرتبة** لا الدرجة، فيصير الدمج
سليمًا بين قنوات غير متجانسة، ويكافئ المرشح الذي **تتفق عليه عدة قنوات** —
وهذه بعينها الإشارة التي نريدها: مادة يجدها المتجه والمعجمي والجوار البنيوي
معًا أجدر من مادة وجدتها قناة واحدة.

الثوابت: K=60 هي القيمة القياسية المنشورة لـRRF وتُترك كما هي لأنها لا تُضبط
على أهداف بعينها. أوزان القنوات تعبّر عن **دقة القناة** لا عن أهمية الهدف:
الاستشهاد الصريح (المستخدم كتب رقم المادة) شبه معدوم الإيجابية الكاذبة فيأخذ
أعلى وزن؛ والجوار البنيوي أوسعُ القنوات فيأخذ أدناها لأنه مولّد مرشحين عالي
التغطية يُفترض أن يُصفّيه ما بعده."""

K = 60

CHANNEL_WEIGHT = {
    "citation":      3.0,   # رقم مادة صريح في السؤال/الأوراق
    "dense":         2.0,
    "lexical":       1.5,
    "principle_xref":1.5,   # مبدأ يذكر المادة صراحةً — جسر مقيس بين لغة المحامي والمشرّع
    "xref":          1.2,
    "sibling_xref":  1.2,
    "judgment_link": 1.2,   # حكم أصل مبدأ مسترجَع
    "chapter":       1.0,
    "bundle":        1.0,
    "adjacency":     0.6,   # أوسع قناة — تغطية عالية، دقة منخفضة عمدًا
}


def fuse(pool, weights=None, k=K):
    """يحسب fusion_score لكل مرشح ويعيد القائمة مرتَّبة تنازليًا."""
    w = dict(CHANNEL_WEIGHT)
    if weights:
        w.update(weights)
    for c in pool:
        s = 0.0
        for ch, rank in c.channel_ranks.items():
            s += w.get(ch, 1.0) / (k + max(1, int(rank)))
        c.fusion_score = round(s, 6)
    return sorted(pool, key=lambda c: (-c.fusion_score, c.object_id))


def apply_rerank(candidates, rerank_scores, alpha=0.5):
    """يدمج درجة المرتِّب المتقاطع مع درجة الدمج.

    المرشح المثبَّت (استشهاد صريح) لا يُمسّ — نفس قاعدة الإنتاج القائمة بأن
    مواد المحلّل بدرجة 0.99 لا يعيد المرتِّب ترتيبها. وغياب درجة مرتِّب
    (فشل الاستدعاء أو خروج المرشح عن سقفه الداخلي) يترك الدرجة كما هي بدل
    تصفيرها — فالفشل الآمن هنا ألا يُعاقَب مرشح على صمت المرتِّب."""
    if not rerank_scores:
        for c in candidates:
            c.final_score = c.fusion_score
        return candidates
    vals = [v for v in rerank_scores.values() if v is not None]
    lo, hi = (min(vals), max(vals)) if vals else (0.0, 1.0)
    # مدى منهار (درجة واحدة أو درجات متطابقة): لا معلومة ترتيب فيه، فتُعطى
    # كل الدرجات 0.5 بدل أن تنهار إلى صفر فتصير إشارةً سلبية لا وجود لها.
    degenerate = (hi - lo) <= 0
    rng = (hi - lo) or 1.0
    fvals = [c.fusion_score for c in candidates] or [0.0]
    flo, fhi = min(fvals), max(fvals)
    frng = (fhi - flo) or 1.0
    # المرشح الذي لم يعطه المرتِّب درجةً (خرج عن سقفه الداخلي أو فشل النداء)
    # يأخذ **المتوسط** لا الصفر: تصفيرُه يجعل صمتَ المرتِّب عقوبةً، فيسقط مرشح
    # لم يُقيَّم أصلًا خلف مرشح قُيِّم تقييمًا سيئًا — وهذا عكس المقصود.
    def _rn(v):
        return 0.5 if degenerate else (v - lo) / rng
    mean_rn = (sum(_rn(v) for v in vals) / len(vals)) if vals else 0.5
    for c in candidates:
        fn = (c.fusion_score - flo) / frng
        r = rerank_scores.get(c.object_id)
        c.rerank_score = r
        if c.pinned:
            c.final_score = 1.0          # استشهاد صريح — لا يعيد المرتِّب ترتيبه
        else:
            rn = mean_rn if r is None else _rn(r)
            c.final_score = round((1 - alpha) * fn + alpha * rn, 6)
    # المثبَّت يسبق عند التعادل: درجته سقفٌ يشاركه فيه غيرُه، وأسبقيتُه قرار لا صدفة ترتيب
    return sorted(candidates, key=lambda c: (not c.pinned, -c.final_score, c.object_id))
