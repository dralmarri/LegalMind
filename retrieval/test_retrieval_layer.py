# -*- coding: utf-8 -*-
"""اختبارات وحدة لطبقة الاسترجاع الجديدة — بلا قاعدة بيانات ولا شبكة.

كل اعتمادية محقونة بمزيَّف، فالاختبار يشغّل **دوال الإنتاج نفسها** لا نسخة
منها. التشغيل: python3 retrieval/test_retrieval_layer.py"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from retrieval.pool import CandidatePool
from retrieval.fusion import fuse, apply_rerank
from retrieval.admission import admit, build_floors, PRODUCTION_BUDGET
from retrieval import temporal as TP
from retrieval import channels as CH
from retrieval import pipeline as PL
from retrieval.model import (Candidate, LAYER_LEGISLATION, LAYER_PRINCIPLE, LAYER_TEMPLATE,
                             LAYER_JUDGMENT, CH_DENSE, CH_LEXICAL)

OK, FAIL = [], []


def check(name, cond, detail=""):
    (OK if cond else FAIL).append(name)
    print(("  ✓ " if cond else "  ✗ ") + name + (("  — " + str(detail)) if detail and not cond else ""))


# ---------------------------------------------------------------- 1. pool
print("\n[1] تجمّع المرشحين — لا قصّ، وإزالة تكرار لا تُفقد النسب")
p = CandidatePool()
for i in range(200):
    p.add("L%03d" % i, CH_DENSE, i + 1, 0.9 - i * 0.001, LAYER_LEGISLATION)
check("لا قصّ: 200 مرشح تدخل و200 تبقى", len(p) == 200, len(p))
p2 = CandidatePool()
p2.add("a", CH_DENSE, 5, 0.80, LAYER_PRINCIPLE)
p2.add("b", CH_DENSE, 1, 0.90, LAYER_PRINCIPLE)
p2.add("b", CH_LEXICAL, 2, 0.0, LAYER_PRINCIPLE)
fuse(p2)
TEXT = {"a": "قاعدة مكررة حرفيًا", "b": "قاعدة مكررة حرفيًا", }
dropped = p2.dedupe_by_content(lambda i: TEXT.get(i, "")[:120], layers=(LAYER_PRINCIPLE,))
check("النسخة الأدنى درجةً هي التي تُحذف", dropped == ["a"], dropped)
check("نسبُ المحذوفة يُنقل للباقية", CH_DENSE in p2.get("b").channels)
p3 = CandidatePool()
p3.add("x", CH_DENSE, 1, 0.9, LAYER_PRINCIPLE)
p3.add("y", CH_DENSE, 2, 0.8, LAYER_PRINCIPLE)
n = p3.dedupe_by_content(lambda i: None, layers=(LAYER_PRINCIPLE,))
check("غياب النص ليس تطابقًا فلا يُدمج", n == [] and len(p3) == 2)

# -------------------------------------------------------------- 2. fusion
print("\n[2] الدمج التبادلي — اتفاق القنوات يعلو، والمثبَّت لا يُمسّ")
p = CandidatePool()
p.add("multi", CH_DENSE, 9, 0.80, LAYER_LEGISLATION)
p.add("multi", CH_LEXICAL, 3, 0.0, LAYER_LEGISLATION)
p.add("multi", "adjacency", 1, 0.0, LAYER_LEGISLATION)
p.add("single", CH_DENSE, 5, 0.88, LAYER_LEGISLATION)
r = fuse(p)
check("مرشح تتفق عليه ثلاث قنوات يسبق مرشحًا من قناة واحدة أعلى رتبةً",
      r[0].object_id == "multi", [(c.object_id, c.fusion_score) for c in r])
p.add("pin", "citation", 1, 1.0, LAYER_LEGISLATION, pinned=True)
r = apply_rerank(fuse(p), {"multi": 9.0, "single": 8.0, "pin": -9.0})
check("المثبَّت يبقى في القمة رغم درجة مرتِّب كارثية",
      r[0].object_id == "pin" and r[0].final_score == 1.0,
      [(c.object_id, c.final_score) for c in r])
r2 = apply_rerank(fuse(p), {})
check("صمت المرتِّب لا يصفّر الدرجات", all(c.final_score >= 0 for c in r2))
r3 = apply_rerank(fuse(p), {"multi": 9.0})
check("مرشح بلا درجة مرتِّب لا يُعاقَب بالتصفير",
      next(c for c in r3 if c.object_id == "single").final_score > 0)

# ----------------------------------------------------------- 3. admission
print("\n[3] القبول — حدٌّ محميٌّ ثم فائض مشترك")
def mk(oid, layer, score):
    c = Candidate(oid, layer); c.final_score = score; return c
cands = ([mk("L%d" % i, LAYER_LEGISLATION, 0.99 - i * 0.001) for i in range(60)]
         + [mk("P%d" % i, LAYER_PRINCIPLE, 0.98 - i * 0.001) for i in range(60)])
cands.sort(key=lambda c: -c.final_score)
size = lambda c: 2000 if c.layer == LAYER_LEGISLATION else 1400
adm, rep = admit(list(cands), size)
check("لا طبقة تُزيح أخرى تحت حدّها المحمي",
      rep["used_by_layer"][LAYER_LEGISLATION] >= build_floors()[LAYER_LEGISLATION]
      and rep["used_by_layer"][LAYER_PRINCIPLE] >= build_floors()[LAYER_PRINCIPLE],
      rep["used_by_layer"])
check("الحدّ غير المستعمَل لطبقة بلا مرشحين يُحرَّر للمشترك",
      rep["released_unused_floor"] > 0, rep["released_unused_floor"])
check("السعة الميتة تحت 8% من الميزانية (مع سقوف الطبقات)",
      rep["dead_capacity"] < 0.08 * rep["total_budget"], rep["dead_capacity"])
check("الميزانية الكلية لم تُتجاوَز",
      sum(rep["used_by_layer"].values()) <= rep["total_budget"])
# طبقة بلا مرشحين إطلاقًا: حدّها يُحرَّر بالكامل ولا يبقى ميتًا (عيب O بعينه)
# المقصد: حدُّ طبقة **غائبة** لا يُجمَّد. (السيناريو أحادي الطبقة كان يخلط هذا
# بالسقف المتعمَّد لكل طبقة، فأُعيد إلى حالة واقعية: تشريع ومبادئ حاضران،
# والأحكام والنماذج غائبة تمامًا — فيجب أن يُحرَّر حدّاهما لا أن يموتا.)
twoL = ([mk("L%d" % i, LAYER_LEGISLATION, 0.9 - i * 0.001) for i in range(40)]
        + [mk("P%d" % i, LAYER_PRINCIPLE, 0.85 - i * 0.001) for i in range(40)])
adm2, rep2 = admit(twoL, lambda c: 2000)
check("حدّ الطبقة الغائبة يُحرَّر لا يُجمَّد (عيب 9/9/2 الميت)",
      rep2["released_unused_floor"] >= build_floors()[LAYER_JUDGMENT]
      + build_floors()[LAYER_TEMPLATE], rep2["released_unused_floor"])
check("السعة الميتة تبقى صغيرة مع حضور طبقتين",
      rep2["dead_capacity"] < 0.05 * rep2["total_budget"], rep2["dead_capacity"])
pin = mk("PIN", LAYER_JUDGMENT, 0.0); pin.pinned = True
adm3, rep3 = admit([pin] + twoL, lambda c: 2000)
check("المثبَّت يُقبل رغم أدنى درجة", pin.admitted)
for c in cands:
    if not c.admitted:
        check("كل ساقط يحمل مرحلة سقوطه", bool(c.drop_stage), c.object_id)
        break

# ------------------------------------------------------------ 4. temporal
print("\n[4] الطبقة الزمنية")
check("استخراج مدة كتابية", TP.periods("خلال خمسة أيام") == {(5, "يوم")})
check("استخراج مدة بقوس رقمي", (10, "يوم") in TP.periods("عشرة (10) أيام"))
conf = TP.detect_conflict("التكليف بالوفاء خلال خمسة أيام",
                          "لا يصدر الأمر إلا بعد عشرة أيام من التكليف")
check("تعارض زمني حقيقي يُرصد", conf and conf["status"] == TP.CONFLICT_DETECTED, conf)
check("تطابق المدة لا يولّد تنبيهًا",
      TP.detect_conflict("خلال عشرة أيام", "خلال عشرة أيام") is None)
check("اختلاف الوحدة وحده ليس تعارضًا",
      TP.detect_conflict("خلال خمسة أيام", "خلال ستة أشهر") is None)
check("غياب مدة في أحد الطرفين لا يولّد تنبيهًا",
      TP.detect_conflict("نص بلا مدة", "خلال عشرة أيام") is None)
st, _ = TP.classify_object({"verification_status": "superseded",
                            "metadata": {"repealed_by": "80/2026"}})
check("الملغى بلا صكّ = SUPERSEDED", st == TP.SUPERSEDED, st)
st, _ = TP.classify_object({"verification_status": "superseded",
                            "metadata": {"repealed_by": "80/2026",
                                         "repeal_date": "2026-08-26"}})
check("الملغى بصكّه = TRANSITION_VERIFIED", st == TP.TRANSITION_VERIFIED, st)
st, _ = TP.classify_object({"metadata": {"previous_versions": [1]}})
check("نسخة سابقة محفوظة = TRANSITION_VERIFIED", st == TP.TRANSITION_VERIFIED, st)
check("بلا إشارة = CURRENT", TP.classify_object({"metadata": {}})[0] == TP.CURRENT)
check("metadata كسلسلة JSON تُفكّ",
      TP.classify_object({"metadata": '{"repealed_by":"x"}'})[0] == TP.SUPERSEDED)

# ------------------------------------------------------------ 5. channels
print("\n[5] القنوات")
for txt, exp in [("والمادة 144 من القانون", ["144"]),
                 ("المواد 57، 61، 63 و196", ["57", "61", "63", "196"]),
                 ("المواد من 56 إلى 61", ["56", "57", "58", "59", "60", "61"]),
                 ("رقم 5947 وتوكيل رقم 25787", []),
                 ("م167", ["167"])]:
    check("أرقام المواد: %s" % txt[:28], CH.article_numbers(txt) == exp,
          CH.article_numbers(txt))
LAW = ["legis-9-9999-m%d" % n for n in (1, 2, 5, 9, 10, 11, 40)]
def db_law(sql, params):
    if "source_judgment_id" in sql:
        return [{"id": "jprin-1-2000-a", "jid": "judgment-civ-1-2000"}]
    if "ORDER BY id" in sql and "LIKE" in sql and "m%" in str(params):
        return [{"id": i} for i in LAW]
    return [{"id": "jprin-9-1999-a", "object_type": "judicial_principle"},
            {"id": "judgment-civ-5-2005", "object_type": "full_judgment"}]
pa = CandidatePool(); CH.adjacency(pa, db_law, ["legis-9-9999-m9"], window=2)
got = sorted(c.object_id for c in pa)
check("الجوار بالموضع الترتيبي لا بالمدى الرقمي (يتخطى الثغرات)",
      got == ["legis-9-9999-m10", "legis-9-9999-m11", "legis-9-9999-m2",
              "legis-9-9999-m5"], got)
pl = CandidatePool(); CH.lexical(pl, db_law, ["قاعدة عدم سماع الدعوى بمضي المدة"])
layers = {c.layer for c in pl}
check("المعجمي يعيد مبادئ وأحكامًا لا تشريعًا فقط",
      LAYER_PRINCIPLE in layers and LAYER_JUDGMENT in layers, layers)
pj = CandidatePool(); CH.judgment_link(pj, db_law, ["jprin-1-2000-a"])
check("كل مبدأ يجرّ حكمه الأم",
      [c.object_id for c in pj] == ["judgment-civ-1-2000"])
pc = CandidatePool()
CH.citation(pc, db_law, "الطعن رقم 441 لسنة 2014", None)
check("رقم الطعن يجلب مبدأه مثبَّتًا",
      any(c.pinned and c.layer == LAYER_PRINCIPLE for c in pc))

# --------------------------------------------- 5b. حصّة المرتِّب لكل قناة
print("\n[5b] مدخل المرتِّب — حصّة مضمونة لكل قناة")
from retrieval.fusion import rerank_input
pq = CandidatePool()
for i in range(1, 501):
    pq.add("D%03d" % i, CH_DENSE, (i % 12) + 1, 0.9, LAYER_LEGISLATION)
for i in range(1, 31):
    pq.add("ADJ%02d" % i, "adjacency", (i % 4) + 1, 0.0, LAYER_LEGISLATION)
rq = fuse(pq)
adj_rank = [k for k, c in enumerate(rq, 1) if "adjacency" in c.channels]
check("مقيس: مرشح الجوار وحده يقع دون كل مرشحي المتجه في الدمج",
      min(adj_rank) > sum(1 for c in rq if CH_DENSE in c.channels) * 0.9,
      (min(adj_rank), len(rq)))
naive = sum(1 for c in rq[:300] if "adjacency" in c.channels)
withq = sum(1 for c in rerank_input(rq, cap=300, min_per_channel=12)
            if "adjacency" in c.channels)
check("القصّ الساذج يُقصي قناة الجوار كليًا عن المرتِّب", naive == 0, naive)
check("الحصّة تضمن تقييم القناة رغم ذيل الترتيب", withq >= 12, withq)
check("الحصّة لا تتجاوز السقف", len(rerank_input(rq, cap=300)) == 300)

# ------------------------------------------------------------ 6. pipeline
print("\n[6] الخط كاملًا (اعتماديات مزيَّفة)")
class Deps:
    def search(self, vec, types, limit):
        t0 = types[0]
        pre = {"legislation_article": "legis-1-1000-m", "judicial_principle": "jprin-1-1000-",
               "full_judgment": "judgment-x-", "judicial_template": "tpl-"}.get(t0, "obj-")
        # كل متجه يعيد نافذة مختلفة (تداخل جزئي) كما يقع فعليًا بين المحاور
        off = int(abs(vec[0]) * 100)
        return [{"payload": {"object_id": pre + str(off + i)}, "score": 0.9 - i * 0.002}
                for i in range(1, limit + 1)]
    def db_rows(self, sql, params):
        return db_law(sql, params)
    def fetch_texts(self, ids):
        return {i: {"text": "نص المصدر " + i + " " * 2400, "branch": "مدني",
                    "topic": "ت", "title": "ع", "publication": ""} for i in ids}
    def rerank(self, q, pairs):
        return {oid: 1.0 / (1 + k) for k, (oid, _t) in enumerate(pairs)}
    def row_of(self, i):
        return {"metadata": {}}
    resolve_law_prefix = staticmethod(lambda n, y: "legis-%s-%s-" % (n, y))
# العمق يُمرَّر صراحةً: الاختبار يفحص سلوك الخط لا قيمة الثابت الافتراضي
res = PL.run(Deps(), "المادة 144 من القانون رقم 6 لسنة 2010",
             [[0.1] * 4, [0.2] * 4, [0.3] * 4, [0.4] * 4],
             anchor_ids=["legis-9-9999-m9"], dense_depth=24,
             phrases=["عدم سماع الدعوى بمضي المدة"])
check("التجمّع أوسع بكثير من المقبول", res["pool_size_raw"] > 4 * len(res["admitted"]),
      (res["pool_size_raw"], len(res["admitted"])))
check("الأحكام الكاملة تصل السياق فعلًا",
      res["packet"]["counts"].get(LAYER_JUDGMENT, 0) > 0, res["packet"]["counts"])
check("الطبقات الثلاث متعايشة في الحزمة",
      all(res["packet"]["counts"].get(l, 0) > 0
          for l in (LAYER_LEGISLATION, LAYER_PRINCIPLE, LAYER_JUDGMENT)),
      res["packet"]["counts"])
check("السياق داخل ميزانية الإنتاج نفسها (85k)",
      len(res["context"]) <= sum(PRODUCTION_BUDGET.values()), len(res["context"]))
check("الانتقاء صارم (نسبة القبول ≤ 0.35)", res["selectivity"] <= 0.35, res["selectivity"])
check("كل مقبول يحمل سلسلة نسبه", all(x["channels"] for x in res["packet"]["provenance"]))
check("لا قناة معطَّلة صامتة", res["disabled_channels"] == [], res["disabled_channels"])
# حارس الثابت: العمق الافتراضي مشتقٌّ من منحنى Recall@k المقيس (هضبة عند 9)
_curve = json.load(open(os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "tools/depth_curve.json")))
check("العمق الافتراضي = هضبة المنحنى المقيس + هامش 3",
      PL.DEFAULT_DENSE_DEPTH == _curve["plateau_k"] + 3,
      (PL.DEFAULT_DENSE_DEPTH, _curve["plateau_k"]))
check("المنحنى لا يزيد بعد الهضبة (تعميق القناة وحده لا يكفي)",
      _curve["curve"]["20"] == _curve["curve"][str(_curve["plateau_k"])],
      _curve["curve"]["20"])

# ---------------------------------------- 7. القصّ واستعادة التغطية
print("\n[7] سقوف النص واستهلاك الميزانية (العلّة المقيسة حيًّا)")
from retrieval.packet import clip_text, block_chars, CAPS, temporal_warning
from retrieval import conflicts as CF
from retrieval.temporal import CONFLICT_DETECTED, SUPERSEDED
check("سقوف v2 مطابقة لسقوف الإنتاج حرفيًا",
      CAPS[LAYER_LEGISLATION] == 2200 and CAPS[LAYER_PRINCIPLE] == 1400
      and CAPS[LAYER_JUDGMENT] == 3500, CAPS)
_long = "ن" * 6000
check("المادة الطويلة تُقصّ لسقفها", len(clip_text(LAYER_LEGISLATION, _long)) <= 2300,
      len(clip_text(LAYER_LEGISLATION, _long)))
_prin = "ق" * 3000 + "\n(الطعن 754/2013 أحوال شخصية جلسة 6/2/2014)"
check("سند المبدأ الختامي يبقى بعد القصّ",
      "الطعن 754/2013" in clip_text(LAYER_PRINCIPLE, _prin))
check("النص القصير لا يُمسّ", clip_text(LAYER_LEGISLATION, "قصير") == "قصير")
check("تكلفة الميزانية = طول المطبوع + وسوم",
      block_chars(LAYER_LEGISLATION, _long)
      == len(clip_text(LAYER_LEGISLATION, _long)) + 220)
# استعادة التغطية: نفس الميزانية ونفس المرشحين، بقصّ وبلا قصّ
_cands = [mk("L%d" % i, LAYER_LEGISLATION, 0.9 - i * 0.001) for i in range(80)]
_adm_clip, _ = admit([mk(c.object_id, c.layer, c.final_score) for c in _cands],
                     lambda c: block_chars(LAYER_LEGISLATION, _long))
_adm_raw, _ = admit([mk(c.object_id, c.layer, c.final_score) for c in _cands],
                    lambda c: len(_long) + 220)
check("القصّ يعيد التغطية: مصادر مقبولة أكثر بنفس الميزانية",
      len(_adm_clip) > 2 * len(_adm_raw), (len(_adm_clip), len(_adm_raw)))

# ---------------------------------------- 8. الحماية الزمنية في الكتلة
print("\n[8] الحماية الزمنية — وسمُ المتجاوَز لا حذفُ المبدأ")
_c = Candidate("jprin-240-2002-x", LAYER_PRINCIPLE)
_c.temporal_status = CONFLICT_DETECTED
_c.temporal_conflict = {"clashes": [{"unit": "يوم", "principle_value": 5,
                                     "article_values": [10]}],
                        "article_id": "legis-38-1980-m167"}
_w = temporal_warning(_c)
check("التحذير يذكر القديم والنافذ معًا", "5" in _w and "10" in _w, _w)
check("التحذير ينهى عن تقديم القديم نافذًا", "لا تقدّم التفصيل القديم" in _w)
check("المبدأ يبقى صالحًا فيما عدا النقطة", "يبقى المبدأ صالحًا" in _w)
_s = Candidate("legis-23-1990-m1", LAYER_LEGISLATION); _s.temporal_status = SUPERSEDED
check("الملغى يُوسَم صراحةً", "ملغى" in temporal_warning(_s))
check("المصدر النافذ بلا تحذير", temporal_warning(Candidate("x", LAYER_LEGISLATION)) == "")

# ---------------------------------------- 9. كشف التعارض بلا حسم آلي
print("\n[9] التعارض — ثلاثة محاور، وبلا ترجيح غير مسنود")
_a = Candidate("jprin-a", LAYER_PRINCIPLE); _a.temporal_status = CONFLICT_DETECTED
_a.temporal_conflict = {"clashes": [{"unit": "يوم", "principle_value": 5,
                                     "article_values": [10]}],
                        "article_id": "legis-38-1980-m167"}
_b = Candidate("jprin-b", LAYER_PRINCIPLE)
_d = Candidate("jprin-d", LAYER_PRINCIPLE)
_sup = Candidate("legis-23-1990-m5", LAYER_LEGISLATION); _sup.temporal_status = SUPERSEDED
_cur = Candidate("legis-80-2026-m5", LAYER_LEGISLATION)
_txt = {"jprin-a": "المادة 167 والميعاد خمسة أيام",
        "jprin-b": "المادة 167 الميعاد عشرة أيام",
        "jprin-d": "المادة 167 الميعاد خمسة أيام",
        "legis-23-1990-m5": "نص ملغى", "legis-80-2026-m5": "نص نافذ"}
_rows = {"legis-23-1990-m5": {"metadata": {"repealed_by": "80/2026"}}}
_cf = CF.detect([_a, _b, _d, _sup, _cur], lambda i: _txt.get(i, ""),
                lambda i: _rows.get(i, {}))
_ax = {x["axis"] for x in _cf}
check("محور تشريع↔قضاء مرصود", "statute_vs_judicial" in _ax, _ax)
check("محور قضاء↔قضاء مرصود", "judicial_vs_judicial" in _ax, _ax)
check("محور نافذ↔ملغى مرصود", "current_vs_superseded" in _ax, _ax)
check("كل تعارض يحمل الوسم المطلوب",
      all(x["flag"] == "POTENTIAL_AUTHORITY_CONFLICT" for x in _cf))
check("لا ترجيح حيث لا سند",
      all(x["resolution"] is None for x in _cf if not x["basis_available"]))
check("الترجيح مسموح حيث السند موجود (سند إلغاء)",
      any(x["basis_available"] and x["resolution"] for x in _cf
          if x["axis"] == "current_vs_superseded"))
_clean = CF.detect([_b], lambda i: _txt.get(i, ""), lambda i: {})
check("بلا تعارض حقيقي لا يُولَّد وسم", _clean == [], _clean)

# ---------------------------------------- 10. مسار السلطة القضائية
print("\n[10] مسار السلطة القضائية بالاتجاهين")
_p = CandidatePool()
CH.statute_to_judicial(_p, db_law, ["legis-68-1980-m550"])
check("المادة تجرّ سلطاتها القضائية (تشريع ← قضاء)",
      {c.layer for c in _p} == {LAYER_PRINCIPLE, LAYER_JUDGMENT},
      {c.layer for c in _p})
check("معرّف بلا شكل مادة لا يُطلق استعلامًا",
      len(CH.statute_to_judicial(CandidatePool(), db_law, ["LEG-غير-منتظم"])) == 0)

# ------------------------------- 11. أعطال رصدتها البوابة الحية وأُصلحت
print("\n[11] انحدارات البوابة الحية — الأعطال الثلاثة")
from retrieval.admission import LAYER_CEILING
# D1: السلطة الحتمية المثبَّتة تُقبل ولو كانت أدنى الدرجات
_gate = mk("legis-51-1984-m92", LAYER_LEGISLATION, 0.0); _gate.pinned = True
_flood = [mk("F%d" % i, LAYER_LEGISLATION, 0.99) for i in range(60)]
_adm, _rep = admit([_gate] + _flood, lambda c: 2420)
check("البوابة الحتمية المثبَّتة تنجو من الزحام (D1)", _gate.admitted, _rep)
# D2: سقف الطبقة يمنع الأحكام والنماذج من التهام حصة التشريع
# الطبقات الأربع حاضرة (كحال كل جولة حقيقية) فلا يقع توزيع سقفِ غائب
_j = [mk("J%d" % i, LAYER_JUDGMENT, 0.99) for i in range(40)]
_t = [mk("T%d" % i, LAYER_TEMPLATE, 0.98) for i in range(40)]
_pp = [mk("PR%d" % i, LAYER_PRINCIPLE, 0.50 - i * 0.0001) for i in range(40)]
_l = [mk("L%d" % i, LAYER_LEGISLATION, 0.10 - i * 0.0001) for i in range(40)]
_adm2, _rep2 = admit(_j + _t + _pp + _l, lambda c: 3720 if c.layer in
                     (LAYER_JUDGMENT, LAYER_TEMPLATE) else 2420)
_u, _eff = _rep2["used_by_layer"], _rep2["layer_ceiling"]
check("لا طبقة تتجاوز سقفها الفعلي (D2)",
      all(_u.get(l, 0) <= _eff.get(l, 10 ** 9) for l in _eff), (_u, _eff))
check("سقوف الطبقات الحاضرة لم تُرفع (لا غائب يوزَّع)",
      _eff[LAYER_JUDGMENT] == LAYER_CEILING[LAYER_JUDGMENT], _eff)
check("النماذج محصورة بسقفها الضيق (غير قابلة للاستشهاد)",
      _u.get(LAYER_TEMPLATE, 0) <= LAYER_CEILING[LAYER_TEMPLATE], _u)
check("التشريع يبقى حاضرًا رغم اكتساح الأحكام بالدرجة (D2)",
      _u.get(LAYER_LEGISLATION, 0) > 0, _u)
check("الساقط بالسقف يُوسَم بمرحلته",
      any(c.drop_stage == "layer_ceiling" for c in _j + _t))
# D3: الكشف الزمني يعمل بلا xref_of خارجي
class _D3:
    def search(self, v, t, l):
        pre = {"legislation_article": "legis-38-1980-m", "judicial_principle": "jprin-240-2002-",
               "full_judgment": "judgment-x-", "judicial_template": "tpl-"}.get(t[0], "o-")
        return [{"payload": {"object_id": pre + ("167" if pre.startswith("legis") else str(i))},
                 "score": 0.9} for i in range(1, 3)]
    def db_rows(self, sql, params): return []
    def fetch_texts(self, ids):
        m = {"legis-38-1980-m167": "لا يصدر الأمر إلا بعد التكليف بالوفاء بعشرة أيام",
             "jprin-240-2002-1": "المادة 167 توجب التكليف بالوفاء خلال خمسة أيام",
             "jprin-240-2002-2": "المادة 167 والتكليف بالوفاء خلال خمسة أيام"}
        return {i: {"text": m.get(i, "نص " + i), "branch": "", "topic": "",
                    "title": "", "publication": ""} for i in ids}
    def rerank(self, q, pairs): return {}
    def row_of(self, i): return {"metadata": {}}
_r3 = PL.run(_D3(), "أمر أداء", [[0.1] * 4])
check("الكشف الزمني يعمل بلا اعتمادية خارجية (D3)",
      _r3["temporal"].get("CONFLICT_DETECTED", 0) > 0, _r3["temporal"])
check("«خمسة أيام» لا تخرج بلا تحذير زمني (D3)",
      ("خمسة أيام" not in _r3["context"]) or ("تحذير زمني" in _r3["context"]))
check("التعارض يُوسَم ولا يُحسم بلا سند",
      all(x["resolution"] is None for x in _r3["conflicts"]
          if not x.get("basis_available")), _r3["conflicts"])

# ------------------- 12. ترتيب الفائض بأولوية الطبقة (سبب سقوط m146/m442)
print("\n[12] الفائض بأولوية الطبقة — التشريع لا يُزاحَم بعد ضمان القضاء")
_hi_j = [mk("HJ%d" % i, LAYER_JUDGMENT, 0.99) for i in range(30)]
_hi_p = [mk("HP%d" % i, LAYER_PRINCIPLE, 0.97) for i in range(30)]
_lo_l = [mk("LL%d" % i, LAYER_LEGISLATION, 0.05 - i * 0.0001) for i in range(40)]
_a12, _r12 = admit(_hi_j + _hi_p + _lo_l,
                   lambda c: 3400 if c.layer == LAYER_JUDGMENT else 1500)
_u12 = _r12["used_by_layer"]
check("التشريع الأدنى درجةً يبلغ سقفه رغم اكتساح الأعلى درجةً",
      _u12.get(LAYER_LEGISLATION, 0) >= 0.9 * _r12["layer_ceiling"][LAYER_LEGISLATION],
      _u12)
check("القضاء يبقى حاضرًا بحدّه المحمي (المكسب محفوظ)",
      _u12.get(LAYER_JUDGMENT, 0) >= build_floors()[LAYER_JUDGMENT] * 0.8, _u12)
check("المبادئ تبقى حاضرة", _u12.get(LAYER_PRINCIPLE, 0) > 0, _u12)
_n_l = sum(1 for c in _a12 if c.layer == LAYER_LEGISLATION)
check("عدد السلطات التشريعية المقبولة يقارب طاقة سقفها",
      _n_l >= 25, _n_l)

print("\n" + "=" * 62)
print("نجح %d / %d" % (len(OK), len(OK) + len(FAIL)))
if FAIL:
    print("الفاشلة:", FAIL)
print("RETRIEVAL_LAYER_TESTS_" + ("PASS" if not FAIL else "FAIL"))
sys.exit(0 if not FAIL else 1)
