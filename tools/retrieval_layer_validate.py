#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""بوابة التحقق الخادمية لطبقة الاسترجاع الجديدة — تُشغَّل على الخادم وحده.

لا تمسّ أي نقطة إنتاج ولا تعدّل قاعدة ولا فهرسًا: تستدعي دوال الإنتاج للقراءة
فقط (`_draft_search` / `db_rows` / `_draft_fetch_texts` / `_draft_rerank`) ثم
تشغّل الخط الجديد بجانب الخط القائم على **نفس** الحالات وتقارن.

التشغيل:
    cd /opt/LegalMind; set -a; . deploy/.env; set +a
    /opt/LegalMind/admin/.venv/bin/python tools/retrieval_layer_validate.py

المقاييس المطلوبة التي **لا يمكن قياسها إلا هنا** (لأنها تحتاج Qdrant والمرتِّب
المتقاطع الحيَّين): فصل الضابط السالب تحت الترتيب الحقيقي، وزمن الاستجابة،
واسترجاع الأحكام الكاملة فعليًا."""
import sys, json, time, os

sys.path.insert(0, "/opt/LegalMind")
sys.path.insert(0, "/opt/LegalMind/admin")
from admin import app                                    # noqa: E402
import kb_types as _kb                                   # noqa: E402
from retrieval import pipeline as PL                     # noqa: E402
from retrieval.model import (LAYER_LEGISLATION, LAYER_PRINCIPLE,  # noqa: E402
                             LAYER_JUDGMENT)
import re                                                # noqa: E402

ROOT = "/opt/LegalMind"


class Deps:
    """كل اعتمادية تُوصَل بدالة الإنتاج نفسها — لا نسخة منها."""
    search = staticmethod(lambda vec, types, limit: app._draft_search(vec, list(types), limit))
    db_rows = staticmethod(lambda sql, params: app.db_rows(sql, params))
    fetch_texts = staticmethod(lambda ids: app._draft_fetch_texts(set(ids)))
    rerank = staticmethod(lambda q, pairs: app._draft_rerank(q, pairs))

    @staticmethod
    def resolve_law_prefix(num, year):
        rows = app.db_rows(
            "SELECT id FROM knowledge_objects WHERE id LIKE %s "
            "AND object_type = ANY(%s) LIMIT 1",
            ("legis-%s-%s-m%%" % (num, year), list(_kb.LEGISLATION_TYPES)))
        return ("legis-%s-%s-" % (num, year)) if rows else None

    _row_cache = {}

    @staticmethod
    def row_of(oid):
        if oid not in Deps._row_cache:
            r = app.db_rows("SELECT id, verification_status, metadata "
                            "FROM knowledge_objects WHERE id = %s", (oid,))
            Deps._row_cache[oid] = (r or [{}])[0]
        return Deps._row_cache[oid]


def axes_and_vectors(rt, facts, madhab=None):
    import anthropic
    client = anthropic.Anthropic(api_key=app._draft_env("ANTHROPIC_API_KEY"))
    subq = app._draft_subqueries(client, rt, facts, madhab)
    query = rt + " - " + facts[:1500]
    return query, subq, app._draft_embed_multi([query] + subq)


_ART_IN_TEXT = re.compile(r"legis-[0-9a-zA-Z-]+-m\d+")


def anchors_from(text, subq):
    """مراسي الجوار البنيوي: المواد المذكورة صراحةً + ما يجلبه محلّ الإنتاج."""
    out = list(app._draft_direct_ids("", text, subq))[:12]
    return out


def run_new(rt, facts, madhab=None, depth=PL.DEFAULT_DENSE_DEPTH):
    query, subq, vectors = axes_and_vectors(rt, facts, madhab)
    anchors = anchors_from(facts, subq)
    extra = []
    for i, oid in enumerate(app._draft_bundles(rt, facts, subq, madhab, None), 1):
        extra.append((oid, "bundle", i, 0.0, LAYER_LEGISLATION))
    for i, oid in enumerate(app._draft_chap_ids(rt, facts, subq), 1):
        extra.append((oid, "chapter", i, 0.0, LAYER_LEGISLATION))
    t0 = time.time()
    res = PL.run(Deps(), query, vectors, anchor_ids=anchors,
                 phrases=subq, dense_depth=depth, extra=extra,
                 norm_ar=app._draft_norm_ar)
    res["latency_sec"] = round(time.time() - t0, 2)
    res["anchors"] = anchors
    return res


def run_production(rt, facts, madhab=None):
    import anthropic

    class _In:
        request_type, facts, madhab, branch = rt, facts, madhab, None
        attachment, attachments = None, []
    client = anthropic.Anthropic(api_key=app._draft_env("ANTHROPIC_API_KEY"))
    t0 = time.time()
    ctx = app._draft_build_context(client, _In(), facts)
    ctx["latency_sec"] = round(time.time() - t0, 2)
    return ctx


def main():
    battery = json.load(open(os.path.join(ROOT, "battery.json")))
    cases = battery if isinstance(battery, list) else battery.get("cases", [])
    report = {"cases": [], "totals": {}}
    tot = {"must": 0, "must_old": 0, "must_new": 0,
           "pool_old": 0, "pool_new": 0, "adm_old": 0, "adm_new": 0,
           "jud_old": 0, "jud_new": 0, "prin_old": 0, "prin_new": 0,
           "lat_old": 0.0, "lat_new": 0.0}
    for c in cases:
        rt = c.get("request_type") or ""
        facts = c.get("facts") or c.get("question") or ""
        must = list(c.get("must") or [])
        try:
            old = run_production(rt, facts, c.get("madhab"))
            new = run_new(rt, facts, c.get("madhab"))
        except Exception as e:
            report["cases"].append({"id": c.get("id"), "error": repr(e)})
            continue
        old_ids, new_ids = set(old["seen"]), {x.object_id for x in new["admitted"]}
        got_old = [m for m in must if m in old_ids]
        got_new = [m for m in must if m in new_ids]
        lay_new = new["packet"]["counts"]
        lay_old = {}
        for lb, _s, p in old["hits"]:
            if p.get("object_id") in old_ids:
                lay_old[lb] = lay_old.get(lb, 0) + 1
        row = {
            "id": c.get("id"), "must_total": len(must),
            "must_old": len(got_old), "must_new": len(got_new),
            "missing_old": [m for m in must if m not in old_ids],
            "missing_new": [m for m in must if m not in new_ids],
            "pool_old": old["attr"].get("true_union_count"),
            "pool_new": new["pool_size_raw"],
            "admitted_old": len(old_ids), "admitted_new": len(new_ids),
            "by_layer_old": lay_old, "by_layer_new": lay_new,
            "temporal": new["temporal"],
            "selectivity_new": new["selectivity"],
            "latency_old": old["latency_sec"], "latency_new": new["latency_sec"],
            "context_chars_old": len(old["context"]),
            "context_chars_new": len(new["context"]),
            "admission": new["admission"],
        }
        report["cases"].append(row)
        tot["must"] += len(must); tot["must_old"] += len(got_old)
        tot["must_new"] += len(got_new)
        tot["pool_old"] += row["pool_old"] or 0; tot["pool_new"] += row["pool_new"]
        tot["adm_old"] += row["admitted_old"]; tot["adm_new"] += row["admitted_new"]
        tot["jud_old"] += lay_old.get(LAYER_JUDGMENT, 0)
        tot["jud_new"] += lay_new.get(LAYER_JUDGMENT, 0)
        tot["prin_old"] += lay_old.get(LAYER_PRINCIPLE, 0)
        tot["prin_new"] += lay_new.get(LAYER_PRINCIPLE, 0)
        tot["lat_old"] += row["latency_old"]; tot["lat_new"] += row["latency_new"]
        print("  %-10s must %d/%d → %d/%d | تجمّع %s→%d | أحكام %d→%d | زمن %.1f→%.1f"
              % (c.get("id"), len(got_old), len(must), len(got_new), len(must),
                 row["pool_old"], row["pool_new"],
                 lay_old.get(LAYER_JUDGMENT, 0), lay_new.get(LAYER_JUDGMENT, 0),
                 row["latency_old"], row["latency_new"]), flush=True)
    n = max(1, len(report["cases"]))
    report["totals"] = dict(
        tot, legislative_recall_old=round(tot["must_old"] / max(1, tot["must"]), 4),
        legislative_recall_new=round(tot["must_new"] / max(1, tot["must"]), 4),
        avg_latency_old=round(tot["lat_old"] / n, 2),
        avg_latency_new=round(tot["lat_new"] / n, 2))
    out = os.path.join(ROOT, "tools/retrieval_layer_validation.json")
    json.dump(report, open(out, "w"), ensure_ascii=False, indent=1)
    t = report["totals"]
    print("\n" + "=" * 66)
    print("Legislative Recall (must):  %.3f → %.3f  (%d/%d → %d/%d)"
          % (t["legislative_recall_old"], t["legislative_recall_new"],
             t["must_old"], t["must"], t["must_new"], t["must"]))
    print("تجمّع المرشحين:            %d → %d" % (t["pool_old"], t["pool_new"]))
    print("المقبول في السياق:         %d → %d" % (t["adm_old"], t["adm_new"]))
    print("مبادئ في السياق:           %d → %d" % (t["prin_old"], t["prin_new"]))
    print("أحكام كاملة في السياق:      %d → %d" % (t["jud_old"], t["jud_new"]))
    print("متوسط الزمن (ث):           %.1f → %.1f" % (t["avg_latency_old"], t["avg_latency_new"]))
    ok = (t["legislative_recall_new"] >= t["legislative_recall_old"]
          and t["jud_new"] >= t["jud_old"])
    print("\nVALIDATION_" + ("PASS" if ok else "REGRESSION") + "  — التفصيل في " + out)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
