#!/usr/bin/env python3
# مسبار قراءة فقط (قناة الاسترجاع بالموضوع، 2026-10-10): كيف يقع تبويب المصدر في القاعدة وفي فهرس Qdrant؟
# يقرأ PG وQdrant ولا يكتب شيئًا. النجاح = PROBE_TAXONOMY_OK
import os, sys, json, hashlib, random, collections, urllib.request
import psycopg
QD = "http://127.0.0.1:6333"; COLL = "legalmind_multilingual_e5_base_v1"
def qd(path, body):
    req = urllib.request.Request(QD + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=60).read())["result"]
def pid(oid):
    return int.from_bytes(hashlib.sha256(oid.encode()).digest()[:8], "big") & ((1 << 63) - 1)
with psycopg.connect(os.environ["DATABASE_URL"]) as c, c.cursor() as cur:
    cur.execute("SELECT id, branch, topic, subtopic, micro_issue, (metadata ? 'taxonomy_source'), "
                "metadata->'taxonomy_source' FROM knowledge_objects WHERE object_type = 'judicial_principle'")
    rows = cur.fetchall()
print("principles:", len(rows), "| with taxonomy_source:", sum(1 for r in rows if r[5]))
for lab, sel in (("all", rows), ("tax", [r for r in rows if r[5]])):
    t = collections.Counter((r[1], r[2]) for r in sel)
    ts = collections.Counter((r[1], r[2], r[3]) for r in sel)
    tsm = collections.Counter((r[1], r[2], r[3], r[4]) for r in sel)
    def pct(cn):
        v = sorted(cn.values()); n = len(v)
        return {"n": n, "p50": v[n // 2], "p90": v[int(n * .9)], "max": v[-1], "singletons": sum(1 for x in v if x == 1)} if n else {}
    print("[%s] topics %s | topic+subtopic %s | +micro %s" % (lab, pct(t), pct(ts), pct(tsm)))
    print("[%s] empty topic %d, empty subtopic %d, empty micro %d" % (lab, sum(1 for r in sel if not r[2]),
          sum(1 for r in sel if not r[3]), sum(1 for r in sel if not r[4])))
tax = [r for r in rows if r[5]]
print("\nbranches (tax):", collections.Counter(r[1] for r in tax).most_common())
print("\ntop topics (tax):")
for (b, tp), n in collections.Counter((r[1], r[2]) for r in tax).most_common(60):
    print("  %5d  %s | %s" % (n, b, (tp or "")[:70]))
print("\ntaxonomy_source sample keys:", collections.Counter(tuple(sorted((r[6] or {}).keys())) for r in tax[:5000] if isinstance(r[6], dict)).most_common(5))
random.seed(11)
for r in random.sample(tax, 6):
    print("  ex:", r[0], "|", (r[2] or "")[:40], "|", (r[3] or "")[:50], "|", (r[4] or "")[:50], "|", json.dumps(r[6], ensure_ascii=False)[:160])
# اتساق حمولة Qdrant مع PG (هل أُعيدت الفهرسة بعد التبويب؟)
samp = random.sample(tax, 400)
pts = qd("/collections/%s/points" % COLL, {"ids": [pid(r[0]) for r in samp], "with_payload": True, "with_vector": False})
by = {p["payload"].get("object_id"): p["payload"] for p in pts}
same = sum(1 for r in samp if r[0] in by and (by[r[0]].get("topic"), by[r[0]].get("subtopic"), by[r[0]].get("micro_issue")) == (r[2], r[3], r[4]))
print("\nqdrant payload: found %d/400, topic+subtopic+micro identical to PG: %d" % (len(by), same))
for r in samp[:400]:
    p = by.get(r[0])
    if p and (p.get("topic"), p.get("subtopic")) != (r[2], r[3]):
        print("  diff:", r[0], "| PG:", (r[2] or "")[:30], "/", (r[3] or "")[:30], "| QD:", (p.get("topic") or "")[:30], "/", (p.get("subtopic") or "")[:30]); break
tp = tax[0]
cnt = qd("/collections/%s/points/count" % COLL, {"exact": True, "filter": {"must": [
    {"key": "object_type", "match": {"value": "judicial_principle"}}, {"key": "topic", "match": {"value": tp[2]}}]}})
print("filter count works: topic=%r → %s" % ((tp[2] or "")[:40], cnt))
print("PROBE_TAXONOMY_OK")
