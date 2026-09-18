# -*- coding: utf-8 -*-
"""اختبارات وحدة لطبقة الاسترجاع الجديدة — بلا قاعدة بيانات ولا شبكة.

كل اعتمادية محقونة بمزيَّف، فالاختبار يشغّل **دوال الإنتاج نفسها** لا نسخة
منها. التشغيل: python3 retrieval/test_retrieval_layer.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from retrieval.pool import CandidatePool
from retrieval.fusion import fuse, apply_rerank
from retrieval.admission import admit, build_floors, PRODUCTION_BUDGET
from retrieval import temporal as TP
from retrieval import channels as CH
from retrieval import pipeline as PL
from retrieval.model import (Candidate, LAYER_LEGISLATION, LAYER_PRINCIPLE,
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
check("السعة الميتة تحت 5% من الميزانية",
      rep["dead_capacity"] < 0.05 * rep["total_budget"], rep["dead_capacity"])
check("الميزانية الكلية لم تُتجاوَز",
      sum(rep["used_by_layer"].values()) <= rep["total_budget"])
# طبقة بلا مرشحين إطلاقًا: حدّها يُحرَّر بالكامل ولا يبقى ميتًا (عيب O بعينه)
onlyL = [mk("L%d" % i, LAYER_LEGISLATION, 0.9 - i * 0.001) for i in range(80)]
adm2, rep2 = admit(onlyL, lambda c: 2000)
check("طبقة غائبة لا تجمّد سعتها (عيب 9/9/2 الميت)",
      rep2["dead_capacity"] < 2500, rep2["dead_capacity"])
pin = mk("PIN", LAYER_JUDGMENT, 0.0); pin.pinned = True
adm3, rep3 = admit([pin] + onlyL, lambda c: 2000)
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
res = PL.run(Deps(), "المادة 144 من القانون رقم 6 لسنة 2010",
             [[0.1] * 4, [0.2] * 4], anchor_ids=["legis-9-9999-m9"],
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

print("\n" + "=" * 62)
print("نجح %d / %d" % (len(OK), len(OK) + len(FAIL)))
if FAIL:
    print("الفاشلة:", FAIL)
print("RETRIEVAL_LAYER_TESTS_" + ("PASS" if not FAIL else "FAIL"))
sys.exit(0 if not FAIL else 1)
