#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""بوابة التحقق الحية لطبقة الاسترجاع v2 — تُشغَّل على الخادم وحده.

قراءة فقط: لا تمسّ نقطة إنتاج، ولا تكتب في القاعدة ولا في الفهرس، ولا تعدّل
حرفًا من `retrieval/`. تستدعي دوال الإنتاج نفسها وتقيس.

السؤال الوحيد: هل v2 تحسّن الوصول الفعلي إلى التشريعات والمبادئ والأحكام
ذات الصلة **دون** زيادة غير مقبولة في الضجيج أو الزمن؟

التشغيل:
    cd /opt/LegalMind; set -a; . deploy/.env; set +a
    nohup /opt/LegalMind/admin/.venv/bin/python tools/retrieval_layer_validate.py \
          > /tmp/v2val.log 2>&1 &
    tail -f /tmp/v2val.log
"""
import sys, os, json, time, statistics

ROOT = "/opt/LegalMind"
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "admin"))

from admin import app                                        # noqa: E402
import kb_types as _kb                                       # noqa: E402
from retrieval import pipeline as PL                          # noqa: E402
from retrieval.model import (LAYER_LEGISLATION as LL, LAYER_PRINCIPLE as LP,
                             LAYER_JUDGMENT as LJ, LAYER_TEMPLATE as LT)

LAYERS = (LL, LP, LJ, LT)
OUT = os.path.join(ROOT, "tools/retrieval_v2_validation.json")
# البند 11: `judgment-civ-754-2013` **لا وجود له في القاعدة** — مرجع خاطئ في
# التوثيق (§26). الكائنات الحقيقية، مُتحقَّقة حيًّا عبر MCP:
#   jprin-754-2013-s1454-50db709d0f  ← مبدأ الطعن 754/2013 أحوال شخصية
#       (جلسة 6/2/2014): «عدم قبول دعوى النسب إذا كان المدعى عليه ميتًا إلا
#        ضمن دعوى حق أخرى» — وهو مضمون الحالة الموصوفة في §26 بالضبط.
#   judgment-civ-697-2013-9e001784   ← حكم تمييز كامل حقيقي في الموضوع نفسه
#       (تصحيح الأسماء ولجنة النسب وم337/338).
# لا كائن وهمي، ولا استبدال بحكم قريب الموضوع.
REG_JUDGMENT_PRINCIPLE = "jprin-754-2013-s1454-50db709d0f"
REG_JUDGMENT_FULL = "judgment-civ-697-2013-9e001784"


# ───────────────────────── أدوات مشتركة ─────────────────────────
_TYPE_CACHE = {}


def layers_of(ids):
    """طبقة كل معرّف من `object_type` الحقيقي في القاعدة — لا تخمين من الشكل."""
    miss = [i for i in set(ids) if i and i not in _TYPE_CACHE]
    for k in range(0, len(miss), 500):
        chunk = miss[k:k + 500]
        try:
            rows = app.db_rows("SELECT id, object_type FROM knowledge_objects "
                               "WHERE id = ANY(%s)", (chunk,))
        except Exception:
            rows = []
        for r in rows:
            ot = r.get("object_type")
            _TYPE_CACHE[r["id"]] = (LL if ot in _kb.LEGISLATION_TYPES else
                                    LP if ot in _kb.PRINCIPLE_TYPES else
                                    LJ if ot in _kb.JUDGMENT_TYPES else
                                    LT if ot in _kb.TEMPLATE_TYPES else "?")
        for i in chunk:
            _TYPE_CACHE.setdefault(i, "?")
    return {i: _TYPE_CACHE.get(i, "?") for i in ids}


def by_layer(ids):
    m = layers_of(list(ids))
    out = {l: 0 for l in LAYERS}
    for i in ids:
        out[m.get(i, "?")] = out.get(m.get(i, "?"), 0) + 1
    return {k: v for k, v in out.items() if k in LAYERS}


def pct(a, b):
    return round(100.0 * a / b, 1) if b else 0.0


# ─────────────── تجميد المحاور: مقارنة مزدوجة حقيقية ───────────────
_FROZEN = {}
_ORIG_SUBQ = app._draft_subqueries


def _frozen_subqueries(client, request_type, facts, madhab, media=None):
    """نداء Haiku **مرة واحدة** لكل حالة، ويُعاد المخرَج نفسه للخطين.

    بلا هذا التجميد تُقارَن نسختان على محاور مختلفة (تفكيك Haiku غير حتمي —
    موثَّق في §prinxref أنه مصدر تقلب الاسترجاع كله)، فيصير الفرق المقيس خليطًا
    من أثر البنية وأثر قرعة المحاور."""
    key = (request_type or "", (facts or "")[:400], madhab or "")
    if key not in _FROZEN:
        _FROZEN[key] = _ORIG_SUBQ(client, request_type, facts, madhab, media)
    return list(_FROZEN[key])


app._draft_subqueries = _frozen_subqueries


# ─────────────── وكلاء تسجيل حول الاعتماديات (بلا مساس بالطبقة) ───────────────
class Rec:
    """يلفّ دوال الإنتاج ليسجّل ما مرّ بكل مرحلة — الطبقة نفسها لا تعلم بوجوده."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.generated = set()      # كل ما أعادته أي قناة قبل أي إزالة تكرار
        self.fetched = set()        # مجموعة ما بعد إزالة التكرار (مدخل الترتيب)
        self.rr_in = set()          # ما عُرض على المرتِّب فعلًا
        self.rr_out = set()         # ما أعطاه المرتِّب درجةً
        self.rr_called = 0
        self.rr_failed = 0

    # الاعتماديات كما تراها الطبقة
    def search(self, vec, types, limit):
        hits = app._draft_search(vec, list(types), limit) or []
        for h in hits:
            oid = (h.get("payload") or {}).get("object_id")
            if oid:
                self.generated.add(oid)
        return hits

    def db_rows(self, sql, params):
        rows = app.db_rows(sql, params)
        for r in (rows or []):
            for k in ("id", "jid"):
                if r.get(k):
                    self.generated.add(r[k])
        return rows

    def fetch_texts(self, ids):
        ids = set(ids)
        self.fetched |= ids
        return app._draft_fetch_texts(ids)

    def rerank(self, q, pairs):
        self.rr_called += 1
        self.rr_in |= {i for i, _t in pairs}
        try:
            out = app._draft_rerank(q, pairs) or {}
        except Exception:
            out = {}
        if not out and pairs:
            self.rr_failed += 1
        self.rr_out |= set(out.keys())
        return out

    @staticmethod
    def resolve_law_prefix(num, year):
        r = app.db_rows("SELECT id FROM knowledge_objects WHERE id LIKE %s "
                        "AND object_type = ANY(%s) LIMIT 1",
                        ("legis-%s-%s-m%%" % (num, year), list(_kb.LEGISLATION_TYPES)))
        return ("legis-%s-%s-" % (num, year)) if r else None

    _rc = {}

    @staticmethod
    def row_of(oid):
        if oid not in Rec._rc:
            r = app.db_rows("SELECT id, verification_status, metadata "
                            "FROM knowledge_objects WHERE id = %s", (oid,))
            Rec._rc[oid] = (r or [{}])[0]
        return Rec._rc[oid]


# ───────────────────────── تشغيل الخطين ─────────────────────────
class _In:
    def __init__(self, rt, q, madhab=None):
        self.request_type, self.facts, self.madhab = rt, q, madhab
        self.branch = None
        self.attachment, self.attachments = None, []


def _client():
    import anthropic
    return anthropic.Anthropic(api_key=app._draft_env("ANTHROPIC_API_KEY"))


def run_baseline(rt, q):
    t0 = time.time()
    ctx = app._draft_build_context(_client(), _In(rt, q), q)
    return ctx, round(time.time() - t0, 2)


def run_v2(rt, q, anchors_extra=()):
    cl = _client()
    inp = _In(rt, q)
    subq = app._draft_subqueries(cl, rt, q, None)
    query = rt + " - " + q[:1500]
    vectors = app._draft_embed_multi([query] + subq)
    extra, direct = [], []
    for i, oid in enumerate(app._draft_bundles(rt, q, subq, None, None), 1):
        extra.append((oid, "bundle", i, 0.0, LL))
    for i, oid in enumerate(app._draft_chap_ids(rt, q, subq), 1):
        # مثبَّتة كما في الإنتاج (0.99): هذه «فصول الاستلزام القانوني» التي لا
        # يصلها تشابه لفظي ولا دلالي — وسقوطها هو ما أفقد m92/m553/m532.
        extra.append((oid, "chapter", i, 1.0, LL, True))
    for i, oid in enumerate(app._draft_direct_ids(rt, q, subq), 1):
        extra.append((oid, "citation", i, 1.0, LL, True))
        direct.append(oid)
    for oid in list(direct):
        for tgt in app._XREF.get(oid, ()):
            extra.append((tgt, "xref", 1, 0.0, LL))
    anchors = (list(anchors_extra) + direct)[:14]
    rec = Rec()
    # المرشحون المحقونون لا يمرّون بأي اعتمادية، فلا يلتقطهم وكيل التسجيل —
    # وبدونهم يخرج DEDUPED أكبر من GENERATED وهو مستحيل منطقيًا (كشفته المحاكاة).
    rec.generated |= {_e[0] for _e in extra}   # الطول متغيّر (5 أو 6 بالتثبيت)
    t0 = time.time()
    res = PL.run(rec, query, vectors, anchor_ids=anchors, phrases=subq,
                 extra=extra, norm_ar=app._draft_norm_ar)
    res["latency"] = round(time.time() - t0, 2)
    res["rec"] = rec
    res["anchors"] = anchors
    return res


def funnel(res):
    """قمع منفصل لكل طبقة سلطة.

    ملاحظة أمانة: `RELATION_VALIDATED` **غير منفَّذة كمرحلة في v2** — الطبقة
    تحتوي تحققًا زمنيًا لا تحققًا من العلاقة، وحقل `Candidate.relation` لا
    يُسنَد في أي مسار. فتُبلَّغ `null` ولا تُختلق لها أرقام."""
    rec = res["rec"]
    adm = [c.object_id for c in res["admitted"]]
    # قياس مستقل: ما وصل النموذج فعلًا يُقرأ من نص السياق نفسه، لا من قائمة
    # المقبولين — فلو سقطت كتلة لغياب نص ظهر الفرق بدل أن يتساوى الرقمان حتمًا.
    import re as _re
    ctx_ids = _re.findall(r'معرف="([^"]+)"', res.get("context") or "")
    return {
        "GENERATED": by_layer(rec.generated),
        "DEDUPED": by_layer(rec.fetched),
        "RELATION_VALIDATED": None,
        "RERANKER_INPUT": by_layer(rec.rr_in),
        "RERANKED": by_layer(rec.rr_out),
        "ADMITTED": by_layer(adm),
        "FINAL_CONTEXT": by_layer(ctx_ids),
    }


# ───────────────────────── الضوابط المجمَّدة ─────────────────────────
def load_controls():
    gt = json.load(open(os.path.join(ROOT, "tools/p27l_controls_ground_truth.json")))["anchors"]
    ex = json.load(open(os.path.join(ROOT, "tools/p27l_exec_in.json")))["cases"]
    qmap = {c["case"]: c for c in ex}
    key = {"A1_labour_limitation": "A1", "A2_prosecution_intervention": "A2",
           "A3_cheque_limitation": "A3"}
    out = []
    for g, a in gt.items():
        c = qmap[key[g]]
        out.append({"case": key[g], "group": g, "question": c["question"],
                    "anchors": c["anchor_ids"],
                    "NAR": [x["id"] for x in a.get("NEAR_AND_RELATED", [])],
                    "RBN": [x["id"] for x in a.get("RELATED_BUT_NONADJACENT", [])],
                    "NBU": [x["id"] for x in a.get("NEAR_BUT_UNRELATED", [])],
                    "nbu_scored": a.get("DISCRIMINATION_POWER") is None})
    return out


def fam(i):
    import re
    m = re.match(r"^(jprin-\d+-\d+)-", i or "")
    return m.group(1) if m else i


def hit(ids, t):
    fams = {fam(i) for i in ids}
    return t in ids or fam(t) in fams


# ───────────────────────── البوابة ─────────────────────────
def main():
    R = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "blocking": []}

    # 1) المرتِّب شرط لا يُتجاوز: بنية v2 تعتمد عليه لتقييم مرشحي القنوات الضعيفة
    probe = app._draft_fetch_texts({"legis-38-1980-m166"})
    pr = {}
    try:
        pr = app._draft_rerank("التكليف بالوفاء قبل أمر الأداء",
                               [(k, v["text"]) for k, v in probe.items()]) or {}
    except Exception as e:
        R["rerank_probe_error"] = repr(e)
    R["reranker_available"] = bool(pr)
    if not pr:
        R["blocking"].append("RERANKER_REQUIRED_BUT_UNAVAILABLE")
        R["verdict"] = "VALIDATION_INCOMPLETE"
        json.dump(R, open(OUT, "w"), ensure_ascii=False, indent=1)
        print("RERANKER_REQUIRED_BUT_UNAVAILABLE — لا يجوز إعلان نجاح بمسار احتياطي.")
        print("VERDICT: VALIDATION_INCOMPLETE")
        sys.exit(2)
    print("reranker: حيّ (%d درجة على مسبار)" % len(pr), flush=True)

    # 2) حارس انتكاس مرجعي (مجموعة التصميم فقط، لا تعميم) — بمعرّفات حقيقية
    pres = {}
    for oid in (REG_JUDGMENT_PRINCIPLE, REG_JUDGMENT_FULL):
        pres[oid] = bool(app.db_rows(
            "SELECT id FROM knowledge_objects WHERE id = %s", (oid,)))
    R["regression_refs_present"] = pres
    if not all(pres.values()):
        R["blocking"].append("REGRESSION_REF_ABSENT")
        print("تنبيه: مرجع حارس غير موجود:", 
              [k for k, v in pres.items() if not v], flush=True)

    # 3) البطارية: خط الأساس مقابل v2 على المدخل نفسه وبالمحاور المجمَّدة نفسها
    cases = json.load(open(os.path.join(ROOT, "battery.json")))
    R["battery"] = []
    tot = {"must": 0, "old": 0, "new": 0}
    lat_o, lat_n, pool_n, rin_n, ctx_n = [], [], [], [], []
    fun_sum = {k: {l: 0 for l in LAYERS} for k in
               ("GENERATED", "DEDUPED", "RERANKER_INPUT", "RERANKED",
                "ADMITTED", "FINAL_CONTEXT")}
    old_layer_sum = {l: 0 for l in LAYERS}
    temporal_sum, judg_proof = {}, []
    for c in cases:
        rt, q = c.get("rt", ""), c.get("q", "")
        must = list(c.get("must") or [])
        try:
            old, lo = run_baseline(rt, q)
            new = run_v2(rt, q)
        except Exception as e:
            R["battery"].append({"name": c.get("name"), "error": repr(e)})
            print("  ✗ %s: %r" % (c.get("name"), e), flush=True)
            continue
        oid_set = set(old["seen"])
        nid_set = {x.object_id for x in new["admitted"]}
        f = funnel(new)
        for k in fun_sum:
            for l in LAYERS:
                fun_sum[k][l] += f[k].get(l, 0)
        for l, v in by_layer(oid_set).items():
            old_layer_sum[l] += v
        for k, v in (new["temporal"] or {}).items():
            temporal_sum[k] = temporal_sum.get(k, 0) + v
        jl = [i for i in nid_set if layers_of([i])[i] == LJ]
        if jl:
            judg_proof.append({"case": c.get("name"), "judgments": jl[:4]})
        lost = [m for m in must if m in oid_set and m not in nid_set]
        if lost:
            R.setdefault("lost_vs_baseline", []).append(
                {"case": c.get("name"), "lost": lost})
        row = {"name": c.get("name"), "lost_vs_baseline": lost,
               "must_total": len(must),
               "must_old": sum(1 for m in must if m in oid_set),
               "must_new": sum(1 for m in must if m in nid_set),
               "missing_new": [m for m in must if m not in nid_set],
               "pool_v2": new["pool_size_raw"],
               "pool_after_dedupe": new["pool_size_after_dedupe"],
               "reranker_input": len(new["rec"].rr_in),
               "admitted_old": len(oid_set), "admitted_new": len(nid_set),
               "ctx_chars_old": len(old["context"]),
               "ctx_chars_new": len(new["context"]),
               "latency_old": lo, "latency_new": new["latency"],
               "selectivity": new["selectivity"], "funnel": f}
        R["battery"].append(row)
        tot["must"] += len(must); tot["old"] += row["must_old"]; tot["new"] += row["must_new"]
        if new["rec"].rr_failed:
            R.setdefault("rerank_failures", []).append(c.get("name"))
        lat_o.append(lo); lat_n.append(new["latency"])
        pool_n.append(new["pool_size_raw"]); rin_n.append(len(new["rec"].rr_in))
        ctx_n.append(len(new["context"]))
        print("  %-34s must %d/%d→%d/%d | تجمّع %d | مرتِّب %d | حكم %d | %.0f→%.0fث"
              % (str(c.get("name"))[:34], row["must_old"], len(must),
                 row["must_new"], len(must), row["pool_v2"], row["reranker_input"],
                 f["FINAL_CONTEXT"].get(LJ, 0), lo, new["latency"]), flush=True)

    # 4) الضوابط: NAR / RBN / NBU بالخط الحقيقي كاملًا
    R["controls"] = []
    C = {"nar": 0, "nar_n": 0, "rbn": 0, "rbn_n": 0, "nbu": 0, "nbu_n": 0,
         "b_nar": 0, "b_rbn": 0, "b_nbu": 0}
    for ct in load_controls():
        try:
            old, _lo = run_baseline("استشارة", ct["question"])
            new = run_v2("استشارة", ct["question"], anchors_extra=ct["anchors"])
        except Exception as e:
            R["controls"].append({"case": ct["case"], "error": repr(e)})
            continue
        o_ids, n_ids = set(old["seen"]), {x.object_id for x in new["admitted"]}
        # أين مات كل هدف: في التجمّع؟ عُرض على المرتِّب؟ أم سقط عند القبول وبأي مرحلة؟
        _stage = {}
        _pool_ids = new["rec"].generated | new["rec"].fetched
        _by_id = {c.object_id: c for c in new["admitted"]}
        for _t in ct["NAR"] + ct["RBN"]:
            if _t in _by_id:
                _stage[_t] = "ADMITTED"
            elif _t in new["rec"].rr_out:
                _stage[_t] = "RERANKED_NOT_ADMITTED"
            elif _t in new["rec"].rr_in:
                _stage[_t] = "RERANKER_INPUT_ONLY"
            elif _t in _pool_ids:
                _stage[_t] = "IN_POOL_ONLY"
            else:
                _stage[_t] = "NEVER_GENERATED"
        row = {"case": ct["case"], "target_stage": _stage,
               "NAR_new": [t for t in ct["NAR"] if hit(n_ids, t)],
               "RBN_new": [t for t in ct["RBN"] if hit(n_ids, t)],
               "NBU_new": [t for t in ct["NBU"] if hit(n_ids, t)],
               "NAR_base": [t for t in ct["NAR"] if hit(o_ids, t)],
               "RBN_base": [t for t in ct["RBN"] if hit(o_ids, t)],
               "NBU_base": [t for t in ct["NBU"] if hit(o_ids, t)],
               "funnel": funnel(new), "latency_new": new["latency"]}
        R["controls"].append(row)
        C["nar"] += len(row["NAR_new"]); C["nar_n"] += len(ct["NAR"])
        C["rbn"] += len(row["RBN_new"]); C["rbn_n"] += len(ct["RBN"])
        C["b_nar"] += len(row["NAR_base"]); C["b_rbn"] += len(row["RBN_base"])
        if ct["nbu_scored"]:
            C["nbu"] += len(row["NBU_new"]); C["nbu_n"] += len(ct["NBU"])
            C["b_nbu"] += len(row["NBU_base"])
        print("    مواضع الأهداف:", _stage, flush=True)
        print("  ضوابط %s: NAR %d/%d (أساس %d) · RBN %d/%d (أساس %d) · NBU %d (أساس %d)"
              % (ct["case"], len(row["NAR_new"]), len(ct["NAR"]), len(row["NAR_base"]),
                 len(row["RBN_new"]), len(ct["RBN"]), len(row["RBN_base"]),
                 len(row["NBU_new"]), len(row["NBU_base"])), flush=True)

    # 4-مكرر) الحالات المرجعية الثلاث (البند 12)
    R["reference_cases"] = []
    REFS = [
        {"id": "نسب", "rt": "استشارة",
         "q": "ما الشرط الإجرائي الواجب توافره قبل قبول دعوى إثبات النسب، "
              "وما حكم رفعها على متوفى؟",
         "expect_judicial": True},
        {"id": "م167", "rt": "استشارة",
         "q": "موكلي يريد استصدار أمر أداء بقيمة شيك مرتد — ما ميعاد التكليف "
              "بالوفاء الواجب قبل تقديم الطلب؟",
         "check_167": True},
        {"id": "الحمض النووي", "rt": "استشارة",
         "q": "دعوى نسب طُلب فيها فحص الحمض النووي ورفض المدعى عليه — ما أثر "
              "الرفض وهل يُقضى بالنسب استنادًا إليه؟",
         "expect_conflict_safe": True},
    ]
    for rf in REFS:
        try:
            new = run_v2(rf["rt"], rf["q"])
        except Exception as e:
            R["reference_cases"].append({"id": rf["id"], "error": repr(e)})
            continue
        ctx = new["context"]
        ids = {x.object_id for x in new["admitted"]}
        lay = by_layer(ids)
        row = {"id": rf["id"], "by_layer": lay,
               "judicial_in_context": lay.get(LP, 0) + lay.get(LJ, 0),
               "conflicts": new.get("conflicts") or [],
               "latency": new["latency"]}
        if rf.get("check_167"):
            # النافذ «عشرة أيام»؛ وأي مبدأ يقتبس «خمسة أيام» يجب أن يحمل التحذير
            row["m167_in_context"] = "legis-38-1980-m167" in ids
            row["five_days_unwarned"] = ("خمسة أيام" in ctx
                                          and "تحذير زمني" not in ctx)
        if rf.get("expect_conflict_safe"):
            row["unsupported_resolution"] = [
                x for x in (new.get("conflicts") or [])
                if x.get("resolution") and not x.get("basis_available")]
        R["reference_cases"].append(row)
        print("  مرجعية %-12s قضاء في السياق %d | تعارضات %d"
              % (rf["id"], row["judicial_in_context"], len(row["conflicts"])),
              flush=True)

    # 5) الخلاصة والحكم
    def p(v, q):
        return round(statistics.quantiles(v, n=100)[q - 1], 1) if len(v) > 2 else (
            round(max(v), 1) if v else 0.0)
    S = {
        "legislative_must_recall_base": round(tot["old"] / max(1, tot["must"]), 4),
        "legislative_must_recall_v2": round(tot["new"] / max(1, tot["must"]), 4),
        "funnel_totals_v2": fun_sum,
        "final_context_by_layer_base": old_layer_sum,
        "controls": C,
        "temporal_statuses": temporal_sum,
        "latency_p50_base": round(statistics.median(lat_o), 1) if lat_o else 0,
        "latency_p95_base": p(lat_o, 95),
        "latency_p50_v2": round(statistics.median(lat_n), 1) if lat_n else 0,
        "latency_p95_v2": p(lat_n, 95),
        "pool_median_v2": round(statistics.median(pool_n), 1) if pool_n else 0,
        "reranker_input_median_v2": round(statistics.median(rin_n), 1) if rin_n else 0,
        "ctx_chars_median_v2": round(statistics.median(ctx_n), 1) if ctx_n else 0,
        "full_judgment_end_to_end": judg_proof[:6],
        "relation_validator": "NOT_IMPLEMENTED_IN_V2",
    }
    R["summary"] = S

    lost_any = bool(R.get("lost_vs_baseline"))
    refs = R.get("reference_cases", [])
    m167 = next((x for x in refs if x.get("id") == "م167"), {})
    dna = next((x for x in refs if x.get("id") == "الحمض النووي"), {})
    nasab = next((x for x in refs if x.get("id") == "نسب"), {})
    ref_fail = (m167.get("five_days_unwarned") is True
                or bool(dna.get("unsupported_resolution"))
                or nasab.get("judicial_in_context", 0) < 1)
    nbu_reg = C["nbu"] > C["b_nbu"]
    leg_reg = S["legislative_must_recall_v2"] < S["legislative_must_recall_base"]
    judg_gain = fun_sum["FINAL_CONTEXT"][LJ] > old_layer_sum.get(LJ, 0)
    prin_reg = fun_sum["FINAL_CONTEXT"][LP] < old_layer_sum.get(LP, 0)
    lat_reg = S["latency_p95_v2"] > 2.0 * max(1.0, S["latency_p95_base"])
    if R.get("rerank_failures"):
        R["blocking"].append("RERANKER_REQUIRED_BUT_UNAVAILABLE")
    ran = len([x for x in R["battery"] if "error" not in x])
    gains = (S["legislative_must_recall_v2"] >= S["legislative_must_recall_base"]
             and C["rbn"] >= C["b_rbn"] and C["nar"] >= C["b_nar"])

    if ran < len(cases) or R["blocking"]:
        verdict = "VALIDATION_INCOMPLETE"
    elif nbu_reg or leg_reg or lat_reg or lost_any or ref_fail:
        verdict = "RETRIEVAL_V2_VALIDATION_FAIL"
    elif gains and C["nbu"] == 0 and not prin_reg and judg_gain:
        verdict = "RETRIEVAL_V2_VALIDATION_PASS"
    else:
        verdict = "RETRIEVAL_V2_PROMISING_WITH_REGRESSIONS"
    R["verdict"] = verdict
    R["regressions"] = {"nbu_worse": nbu_reg, "legislative_worse": leg_reg,
                        "lost_vs_baseline": lost_any, "reference_case_fail": ref_fail,
                        "principles_worse": prin_reg, "latency_p95_doubled": lat_reg,
                        "judgments_gained": judg_gain}
    json.dump(R, open(OUT, "w"), ensure_ascii=False, indent=1)

    print("\n" + "=" * 70)
    print("Legislative must-recall : %.3f → %.3f" % (
        S["legislative_must_recall_base"], S["legislative_must_recall_v2"]))
    print("NAR %d/%d (أساس %d) · RBN %d/%d (أساس %d) · NBU %d (أساس %d)" % (
        C["nar"], C["nar_n"], C["b_nar"], C["rbn"], C["rbn_n"], C["b_rbn"],
        C["nbu"], C["b_nbu"]))
    print("السياق النهائي بالطبقة — أساس: %s" % old_layer_sum)
    print("السياق النهائي بالطبقة — v2  : %s" % fun_sum["FINAL_CONTEXT"])
    print("القمع v2: %s" % json.dumps(fun_sum, ensure_ascii=False))
    print("الحالات الزمنية: %s" % temporal_sum)
    print("زمن p50/p95: أساس %.1f/%.1f  →  v2 %.1f/%.1f ث" % (
        S["latency_p50_base"], S["latency_p95_base"],
        S["latency_p50_v2"], S["latency_p95_v2"]))
    print("وسيط التجمّع %.0f · مدخل المرتِّب %.0f · أحرف السياق %.0f" % (
        S["pool_median_v2"], S["reranker_input_median_v2"], S["ctx_chars_median_v2"]))
    print("سلطات كانت تصل في الأساس وفُقدت في v2: %d حالة" % len(R.get("lost_vs_baseline") or []))
    print("الحالات المرجعية: م167 «خمسة أيام» بلا تحذير=%s · الحمض ترجيح بلا سند=%s · النسب قضاء في السياق=%s"
          % (m167.get("five_days_unwarned"), bool(dna.get("unsupported_resolution")),
             nasab.get("judicial_in_context")))
    print("مُحقِّق العلاقة: NOT_IMPLEMENTED_IN_V2 (تحقق زمني فقط)")
    print("\nVERDICT: %s   — التفصيل في %s" % (verdict, OUT))
    sys.exit(0 if verdict == "RETRIEVAL_V2_VALIDATION_PASS" else 1)


if __name__ == "__main__":
    main()
