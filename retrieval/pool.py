# -*- coding: utf-8 -*-
"""تجمّع المرشحين — يجمع من كل القنوات **بلا أي قصّ**.

القاعدة الوحيدة الحاكمة هنا: لا تُسقِط مرشحًا في هذه المرحلة لأي سبب غير أنه
مكرر. كل قصّ مؤجَّل إلى ما بعد الدمج وتقييم العلاقة والترتيب. هذا عكس الخط
القائم الذي يقصّ الدلوّ الكثيف (caps_n) **قبل** أن يراه المرتِّب إطلاقًا، فما
يقصّه السقفُ لا يحصل على فرصة ترتيب أبدًا."""
from .model import Candidate


class CandidatePool:
    def __init__(self):
        self._by_id = {}
        self.channel_returned = {}   # channel -> كم أعادت القناة خامًا
        self.dup_by_fingerprint = [] # أُزيل كتكرار محتوى (لا كقصّ)

    def __len__(self):
        return len(self._by_id)

    def __contains__(self, oid):
        return oid in self._by_id

    def __iter__(self):
        return iter(self._by_id.values())

    def get(self, oid):
        return self._by_id.get(oid)

    def add(self, object_id, channel, rank, score=0.0, layer="", pinned=False):
        """يضيف مرشحًا أو يدمج ملاحظة قناة جديدة على مرشح قائم."""
        if not object_id:
            return None
        c = self._by_id.get(object_id)
        if c is None:
            c = Candidate(object_id=object_id, layer=layer)
            self._by_id[object_id] = c
        if layer and not c.layer:
            c.layer = layer
        c.pinned = c.pinned or pinned
        c.observe(channel, rank, score)
        self.channel_returned[channel] = self.channel_returned.get(channel, 0) + 1
        return c

    def by_layer(self, layer):
        return [c for c in self._by_id.values() if c.layer == layer]

    def dedupe_by_content(self, fingerprint_of, layers=None):
        """يجمع النسخ المتطابقة نصًا (إعادة نشر المبدأ نفسه عبر المجلدات).

        يُطبَّق **قبل** أي سقف — وهو درس P0-4 المعتمد: النسخ المتطابقة كانت
        تستهلك حصة السقف فتُقصى مبادئ فريدة. ويبقى الأعلى درجةَ دمج.
        `fingerprint_of(object_id) -> str|None`؛ العائد None يعني «لا نص» فلا
        يُدمج (الغياب ليس تطابقًا)."""
        seen = {}
        dropped = []
        order = sorted(self._by_id.values(), key=lambda c: -c.fusion_score)
        for c in order:
            if layers and c.layer not in layers:
                continue
            fp = fingerprint_of(c.object_id)
            if not fp:
                continue
            if fp in seen:
                keep = seen[fp]
                # لا يضيع نسب القناة: تُنقل ملاحظات النسخة المحذوفة للباقية
                for ch, rk in c.channel_ranks.items():
                    keep.observe(ch, rk, c.channel_scores.get(ch, 0.0))
                dropped.append(c.object_id)
                del self._by_id[c.object_id]
                continue
            seen[fp] = c
        self.dup_by_fingerprint = dropped
        return dropped

    def stats(self):
        by_layer, by_channel = {}, {}
        for c in self._by_id.values():
            by_layer[c.layer] = by_layer.get(c.layer, 0) + 1
            for ch in c.channels:
                by_channel[ch] = by_channel.get(ch, 0) + 1
        return {"size": len(self._by_id), "by_layer": by_layer,
                "by_channel": by_channel,
                "content_duplicates_removed": len(self.dup_by_fingerprint)}
