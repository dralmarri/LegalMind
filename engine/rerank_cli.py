import sys, json
from sentence_transformers import CrossEncoder

data = json.load(sys.stdin)
m = CrossEncoder("cross-encoder/mmarco-mMiniLMv2-L12-H384-v1", max_length=512)
pairs = [(data["query"], t) for _i, t in data["pairs"]]
scores = m.predict(pairs) if pairs else []
out = {}
for (i, _t), s in zip(data["pairs"], scores):
    out[i] = float(s)
print(json.dumps(out, ensure_ascii=False))
