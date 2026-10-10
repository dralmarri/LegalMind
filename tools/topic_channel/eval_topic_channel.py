#!/usr/bin/env python3
# تقييم قناة الاسترجاع بالموضوع (2026-10-10) — قياس خالص لا يمسّ الإنتاج:
# يحمّل نسخة مرقّعة مؤقتة من app.py باسم وحدة مستقلة (admin/_app_topic_eval.py تُحذف في النهاية)، ويشغّل
# _draft_build_context لكل سؤال مرتين — القناة مطفأة (A) ومشغّلة (B) — بمحاور ومتجهات مجمّدة بين الذراعين.
# الحقيقة المرجعية: مبادئ القاعدة التي تطابق بصماتُها قواعدَ العنوان الفرعي في فهرس ملف المالك.
# معيار الحكم مجمَّد هنا قبل أي تشغيل (لا يُعدَّل بعد رؤية الأرقام):
#   TOPIC_EVAL_PASS ⇔ R_B ≥ 1.15·R_A و R_B − R_A ≥ 5 و (حالات انخفاض |مقبول ∩ G|) ≤ 4
#   حيث R = مجموع |المبادئ المقبولة في السياق ∩ G| على الحالات التي |G|>0.
import os, re, sys, json, time, hashlib, importlib, collections
sys.path.insert(0, "/opt/LegalMind"); sys.path.insert(0, "/opt/LegalMind/admin")
import psycopg
HERE = os.path.dirname(os.path.abspath(__file__))
DIAC = 'ً-ْٰـٓ-ٕ'
BOIL = re.compile(r'^(?:و)?(?:من)?(?:ال)?(?:مقرر|مستقرعليه|مستقر)(?:ايضا)?(?:فيالفقهوالقضاء)?(?:فيقضاء(?:هذهالمحكمه|محكمهالتمييز|التمييز))?(?:ايضا)?(?:انه|ان)?')
def letters(t):
    t = re.sub('[%s]' % DIAC, '', t)
    t = re.sub('[أإآٱ]', 'ا', t).replace('ة', 'ه').replace('ى', 'ي').replace('ؤ', 'و').replace('ئ', 'ي')
    return re.sub(r'[^ء-ي]', '', t)
def fp(t, n=50):
    s = BOIL.sub('', letters(t))
    return hashlib.sha1(s[:n].encode()).hexdigest()[:12] if len(s) >= 40 else None

bench = json.load(open(os.path.join(HERE, "bench.json"), encoding="utf-8"))["cases"]
only = sys.argv[1:]   # اختياري: معرفات حالات بعينها لتشغيل تجريبي
if only:
    bench = [c for c in bench if c["id"] in only]
want = {f for c in bench for f in c["gt_fps"]}
kb = collections.defaultdict(set)
with psycopg.connect(os.environ["DATABASE_URL"]) as c, c.cursor() as cur:
    cur.execute("SELECT id, original_text FROM knowledge_objects WHERE object_type = 'judicial_principle'")
    for oid, txt in cur:
        for line in (txt or "").split("\n"):
            f = fp(line)
            if f in want:
                kb[f].add(oid)
print("ground truth resolved: %d/%d fingerprints" % (sum(1 for f in want if kb.get(f)), len(want)), flush=True)

# نسخة مرقّعة مؤقتة باسم مستقل — app.py الحي لا يُمسّ
src = open("/opt/LegalMind/admin/app.py", encoding="utf-8").read()
tmp = "/opt/LegalMind/admin/_app_topic_eval.py"
open(tmp, "w", encoding="utf-8").write(src)
rc = os.system("%s %s %s" % (sys.executable, os.path.join(HERE, "patch_topic_channel.py"), tmp))
if rc != 0:
    os.remove(tmp); print("PATCH_FAILED"); sys.exit(2)
try:
    app = importlib.import_module("admin._app_topic_eval")
    import anthropic
    client = anthropic.Anthropic(api_key=app._draft_env("ANTHROPIC_API_KEY"))
    _sq_orig, _em_orig = app._draft_subqueries, app._draft_embed_multi
    memo_sq, memo_em = {}, {}
    def sq(cl, rt, facts, madhab, media=None):
        k = (rt, facts, madhab)
        if k not in memo_sq:
            memo_sq[k] = _sq_orig(cl, rt, facts, madhab, media)
        return list(memo_sq[k])
    def em(texts):
        k = tuple(texts)
        if k not in memo_em:
            memo_em[k] = _em_orig(list(texts))
        return memo_em[k]
    app._draft_subqueries, app._draft_embed_multi = sq, em
    PRIN = "مبدأ قضائي"
    rows, t0 = [], time.time()
    for case in bench:
        G = set().union(*[kb.get(f, set()) for f in case["gt_fps"]]) if case["gt_fps"] else set()
        res = {}
        for arm, flag in (("A", "0"), ("B", "1")):
            os.environ["LEGALMIND_TOPIC_CHANNEL"] = flag
            inp = app._DraftIn(request_type="استشارة", facts=case["question"])
            ctx = app._draft_build_context(client, inp, case["question"])
            lab = {p.get("object_id"): l for l, s, p in ctx["hits"]}
            adm_p = {o for o in ctx["seen"] if lab.get(o) == PRIN}
            adm_l = {o for o in ctx["seen"] if lab.get(o) == "تشريع"}
            pool_p = {o for o, l in lab.items() if l == PRIN}
            res[arm] = {"adm_p": len(adm_p), "adm_hit": sorted(adm_p & G), "pool_hit": len(pool_p & G),
                        "adm_l": sorted(adm_l), "topic_added": len(ctx.get("topic_added") or []),
                        "topic_admitted": len(adm_p & set(ctx.get("topic_added") or []))}
        row = {"id": case["id"], "subtopic": case["subtopic"], "G": len(G),
               "A": res["A"], "B": res["B"],
               "leg_same": res["A"]["adm_l"] == res["B"]["adm_l"]}
        rows.append(row)
        print("%s |G|=%3d | A: مقبول∩G=%2d/%2d حوض=%2d | B: مقبول∩G=%2d/%2d حوض=%2d أُضيف=%2d دخل=%2d | تشريع %s | %s (%.0fث)" % (
            case["id"], len(G), len(res["A"]["adm_hit"]), res["A"]["adm_p"], res["A"]["pool_hit"],
            len(res["B"]["adm_hit"]), res["B"]["adm_p"], res["B"]["pool_hit"], res["B"]["topic_added"],
            res["B"]["topic_admitted"], "=" if row["leg_same"] else "≠", case["subtopic"][:30], time.time() - t0), flush=True)
finally:
    for _f in [tmp] + [os.path.join("/opt/LegalMind/admin/__pycache__", x)
                       for x in (os.listdir("/opt/LegalMind/admin/__pycache__")
                                 if os.path.isdir("/opt/LegalMind/admin/__pycache__") else [])
                       if x.startswith("_app_topic_eval.")]:
        try: os.remove(_f)
        except OSError: pass
ev = [r for r in rows if r["G"] > 0]
RA = sum(len(r["A"]["adm_hit"]) for r in ev); RB = sum(len(r["B"]["adm_hit"]) for r in ev)
PA = sum(r["A"]["pool_hit"] for r in ev); PB = sum(r["B"]["pool_hit"] for r in ev)
down = [r["id"] for r in ev if len(r["B"]["adm_hit"]) < len(r["A"]["adm_hit"])]
up = [r["id"] for r in ev if len(r["B"]["adm_hit"]) > len(r["A"]["adm_hit"])]
nA = sum(r["A"]["adm_p"] for r in ev); nB = sum(r["B"]["adm_p"] for r in ev)
print("\nحالات مقيسة %d (|G|=0: %d)" % (len(ev), len(rows) - len(ev)))
print("R (المقبول في السياق ∩ الحقيقة): A=%d  B=%d  | الحوض: A=%d  B=%d" % (RA, RB, PA, PB))
print("الدقة: A=%.3f  B=%.3f  | مبادئ مقبولة: A=%d  B=%d" % (RA / max(1, nA), RB / max(1, nB), nA, nB))
print("تحسّن %d حالة %s | انخفاض %d حالة %s | تشريع مختلف في %d حالة" % (len(up), up, len(down), down,
      sum(1 for r in rows if not r["leg_same"])))
ok = RB >= 1.15 * RA and RB - RA >= 5 and len(down) <= 4
out = "/opt/legalmind-data/topic_eval_%s.json" % time.strftime("%Y%m%d_%H%M%S")
json.dump(rows, open(out, "w", encoding="utf-8"), ensure_ascii=False)
print("REPORT:", out)
print("TOPIC_EVAL_PASS" if ok else "TOPIC_EVAL_FAIL")
