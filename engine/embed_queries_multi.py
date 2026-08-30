#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تضمين عدة استعلامات دفعة واحدة (تحميل واحد للنموذج).
stdin: مصفوفة JSON من السلاسل → stdout: مصفوفة JSON من المتجهات."""
import sys, json
sys.path.insert(0, "/opt/LegalMind")
from engine import embedding

queries = json.loads(sys.stdin.read())
if not isinstance(queries, list) or not queries:
    print("[]"); sys.exit(0)

vecs = None
fn = getattr(embedding, "embed_query", None)
if callable(fn):
    vecs = [fn(q) for q in queries]
else:
    fns = getattr(embedding, "embed_queries", None)
    if callable(fns):
        vecs = fns(queries)
    else:
        # بديل أخير: النموذج مباشرة ببادئة استعلام E5
        model = embedding.get_model() if hasattr(embedding, "get_model") else embedding.model
        vecs = model.encode(["query: " + q for q in queries],
                            normalize_embeddings=True).tolist()

out = [[float(x) for x in v] for v in vecs]
print(json.dumps(out))
