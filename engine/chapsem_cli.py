#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""فصول حاكمة دلالية: {rt, facts} من stdin ⇒ معرفات مواد (JSON).
مقاطع حتمية ← مرشحون بالمتجهات ← حسم بالمرتب المتقاطع ← حصص بجولتين."""
import os, re, sys, json, pickle
os.environ.setdefault("HF_HOME", "/opt/legalmind-data/hf")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
import numpy as np
sys.path.insert(0, "/opt/LegalMind")
sys.path.insert(0, "/opt/LegalMind/engine")
from engine import embedding


def main():
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except Exception:
        print("[]")
        return
    facts = (data.get("facts") or "").strip()
    if not facts:
        print("[]")
        return
    with open("/opt/LegalMind/chap_sem2.pkl", "rb") as f:
        idx = pickle.load(f)
    items, vecs, texts = idx["labels"], idx["vecs"], idx["texts"]
    q = ((data.get("rt") or "") + " - " + facts)[:2000]
    segs = []
    for s in re.split(r"[.؟!؛\n]+", q):
        s = s.strip()
        if len(s) >= 15:
            segs.append(s)
    words = q.split()
    for i in range(0, max(1, len(words) - 4), 5):
        w = " ".join(words[i:i + 10])
        if len(w) >= 15:
            segs.append(w)
    segs.append(q[:300])
    seen, uniq = set(), []
    for s in segs:
        k = s[:60]
        if k not in seen:
            seen.add(k)
            uniq.append(s)
    segs = uniq[:12]
    from sentence_transformers import CrossEncoder
    ce = CrossEncoder("cross-encoder/mmarco-mMiniLMv2-L12-H384-v1", max_length=512, device="cpu")
    chosen = {}
    for s in segs:
        qv = np.asarray(embedding.embed_query(s), dtype=np.float32)
        sims = vecs @ qv
        cand = np.argsort(-sims)[:15]
        scores = ce.predict([(s, texts[i]) for i in cand], batch_size=15, show_progress_bar=False)
        order = np.argsort(-np.asarray(scores))
        top1 = float(scores[order[0]])
        for rk in order[:2]:
            sc = float(scores[rk])
            if rk == order[0] or sc >= top1 - 1.5:
                i = int(cand[rk])
                if i not in chosen or sc > chosen[i]:
                    chosen[i] = sc
    ranked = sorted(chosen.items(), key=lambda kv: -kv[1])
    recs = []
    for i, _sc in ranked:
        arts = items[i][2]
        small = len(arts) <= 6
        if len(arts) > 8:
            arts = arts[:6] + arts[-2:]
        recs.append((arts, small))
    out = []
    for arts, small in recs:
        for oid in (arts if small else arts[:3]):
            if oid not in out and len(out) < 24:
                out.append(oid)
    for arts, _sm in recs:
        for oid in arts:
            if oid not in out and len(out) < 24:
                out.append(oid)
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
