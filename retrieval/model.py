# -*- coding: utf-8 -*-
"""أنواع البيانات المشتركة لطبقة الاسترجاع."""
from dataclasses import dataclass, field

# قنوات توليد المرشحين — كل مرشح يحمل قناته الأصلية (نسب المرشح، P1.5)
CH_DENSE      = "dense"
CH_LEXICAL    = "lexical"
CH_CITATION   = "citation"
CH_ADJACENCY  = "adjacency"
CH_XREF       = "xref"
CH_SIBLING    = "sibling_xref"
CH_PRIN_XREF  = "principle_xref"
CH_BUNDLE     = "bundle"
CH_CHAPTER    = "chapter"
CH_JUDGMENT   = "judgment_link"

ALL_CHANNELS = (CH_DENSE, CH_LEXICAL, CH_CITATION, CH_ADJACENCY, CH_XREF,
                CH_SIBLING, CH_PRIN_XREF, CH_BUNDLE, CH_CHAPTER, CH_JUDGMENT)

# طبقات السلطة الثلاث — مستقلة ومتعاونة، لا واحدة ملحقة بأخرى
LAYER_LEGISLATION = "تشريع"
LAYER_PRINCIPLE   = "مبدأ قضائي"
LAYER_JUDGMENT    = "حكم كامل"
LAYER_TEMPLATE    = "نموذج صياغة"
LAYERS = (LAYER_LEGISLATION, LAYER_PRINCIPLE, LAYER_JUDGMENT, LAYER_TEMPLATE)


@dataclass
class Candidate:
    """مرشح واحد في التجمّع، بكل نسبه ودرجاته عبر المراحل.

    `channel_ranks` يحفظ رتبة المرشح **داخل كل قناة** وصلت إليه — وهو المدخل
    الذي يحتاجه الدمج التبادلي (RRF)، ولأن كل رتبة تُسجَّل صراحةً يصير ترتيب
    القبول **قابلًا للاسترداد بعد التشغيل**؛ وهذا بالضبط ما افتقده سجل P2.7-O
    فتعذّر حساب البدائل المضادة عليه."""
    object_id: str
    layer: str = ""
    channels: set = field(default_factory=set)
    channel_ranks: dict = field(default_factory=dict)   # channel -> rank (1-based)
    channel_scores: dict = field(default_factory=dict)  # channel -> raw score
    fusion_score: float = 0.0
    rerank_score: float = None
    final_score: float = 0.0
    pinned: bool = False        # استشهاد صريح من المستخدم — لا يُقصّ
    prior: float = 0.0          # أولوية مسبقة من القناة (حزمة حاكمة مثلًا)
    admitted: bool = False
    drop_stage: str = ""        # أين سقط بالضبط، إن سقط
    temporal_status: str = ""
    relation: str = ""

    def observe(self, channel, rank, score=0.0):
        self.channels.add(channel)
        prev = self.channel_ranks.get(channel)
        if prev is None or rank < prev:
            self.channel_ranks[channel] = rank
            self.channel_scores[channel] = score
        elif score > self.channel_scores.get(channel, -1):
            self.channel_scores[channel] = score
