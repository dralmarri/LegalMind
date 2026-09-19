# -*- coding: utf-8 -*-
"""Production adapter for the tested retrieval v2 pipeline.

Keeps admin.app's public context contract unchanged while routing retrieval through
retrieval.pipeline.  The adapter deliberately reuses the live production helpers
(search, embeddings, reranker, bundles, chapter/direct rules and DB access).
"""
from retrieval import pipeline as PL
from retrieval.model import (
    LAYER_LEGISLATION as LL, LAYER_PRINCIPLE as LP,
    LAYER_JUDGMENT as LJ, LAYER_TEMPLATE as LT,
)

_LABEL = {LL: "تشريع", LP: "مبدأ قضائي", LJ: "حكم كامل", LT: "نموذج صياغة"}


class _Deps:
    def __init__(self, A):
        self.A = A
        self.xref_map = A._XREF
        self._row_cache = {}

    def search(self, vec, types, limit):
        return self.A._draft_search(vec, list(types), limit) or []

    def db_rows(self, sql, params):
        return self.A.db_rows(sql, params)

    def fetch_texts(self, ids):
        return self.A._draft_fetch_texts(set(ids))

    def rerank(self, query, pairs):
        return self.A._draft_rerank(query, pairs) or {}

    def resolve_law_prefix(self, num, year):
        kb = self.A._kb
        rows = self.A.db_rows(
            "SELECT id FROM knowledge_objects WHERE id LIKE %s AND object_type = ANY(%s) LIMIT 1",
            ("legis-%s-%s-m%%" % (num, year), list(kb.LEGISLATION_TYPES)),
        )
        return ("legis-%s-%s-" % (num, year)) if rows else None

    def sibling_xref(self, article_ids):
        ids = list(article_ids)[:60]
        if not ids:
            return []
        texts = self.A._draft_fetch_texts(set(ids))
        hits = [("تشريع", 0.5, {"object_id": i}) for i in ids if i in texts]
        try:
            return list(self.A._sib_expand(hits, texts, set(ids)) or [])
        except Exception:
            return []

    def row_of(self, oid):
        if oid not in self._row_cache:
            rows = self.A.db_rows(
                "SELECT id, verification_status, metadata FROM knowledge_objects WHERE id = %s",
                (oid,),
            )
            self._row_cache[oid] = (rows or [{}])[0]
        return self._row_cache[oid]


def _media(inp):
    out = []
    for a in ([inp.attachment] if getattr(inp, "attachment", None) else []) + list(getattr(inp, "attachments", None) or []):
        kind = getattr(a, "kind", None) or (isinstance(a, dict) and a.get("kind"))
        data = getattr(a, "data", None) or (isinstance(a, dict) and a.get("data"))
        mt = getattr(a, "media_type", None) or (isinstance(a, dict) and a.get("media_type"))
        if kind in ("image", "pdf") and data:
            out.append((kind, mt, data))
    return out


def build(A, client, inp, facts_ret):
    """Return the same dictionary contract as admin.app._draft_build_context."""
    query = inp.request_type + " - " + facts_ret[:1500]
    if getattr(inp, "madhab", None):
        query += " (مذهب " + inp.madhab + ")"

    media = _media(inp)
    subq = A._draft_subqueries(client, inp.request_type, facts_ret, inp.madhab, media)
    vectors = A._draft_embed_multi([query] + subq)

    extra = []
    bundle_added, direct_added, chap_added, lex_added = [], [], [], []
    for i, oid in enumerate(A._draft_bundles(inp.request_type, facts_ret, subq, inp.madhab, inp.branch), 1):
        extra.append((oid, "bundle", i, 0.85 if i <= 18 else 0.0, LL))
        bundle_added.append(oid)

    docrefs = A._draft_doc_refs(client, media) if media else []
    direct = list(A._draft_direct_ids(inp.request_type, facts_ret, subq)) + list(docrefs or [])
    for i, oid in enumerate(direct, 1):
        extra.append((oid, "citation", i, 1.0, LL, True))
        direct_added.append(oid)

    for i, oid in enumerate(A._draft_chap_ids(inp.request_type, facts_ret, subq), 1):
        extra.append((oid, "chapter", i, 1.0, LL, True))
        chap_added.append(oid)

    anchors = list(dict.fromkeys(direct))[:20]
    deps = _Deps(A)
    res = PL.run(
        deps, query, vectors, anchor_ids=anchors, phrases=subq,
        extra=extra, norm_ar=A._draft_norm_ar,
    )

    admitted = res["admitted"]
    seen = {c.object_id for c in admitted}
    hits = [(_LABEL.get(c.layer, c.layer), float(c.final_score or 0.0),
             {"object_id": c.object_id, "_source": ",".join(sorted(c.channels))})
            for c in admitted]
    provenance = [{
        "object_id": c.object_id,
        "object_type": _LABEL.get(c.layer, c.layer),
        "source": ",".join(sorted(c.channels)),
        "pre_rerank_score": c.fused_score,
        "reranker_raw": c.rerank_score,
        "final_score": round(float(c.final_score or 0.0), 4),
        "admitted": True,
    } for c in admitted]

    attr = {
        "retrieval_version": "v2-production",
        "true_union_count": res.get("pool_size_raw", 0),
        "deduped_count": res.get("pool_size_after_dedupe", 0),
        "rerank_output_count": res.get("reranked", 0),
        "budget_admitted_count": len(admitted),
        "final_context_count": len(admitted),
        "disabled_channels": res.get("disabled_channels", []),
        "admission": res.get("admission", {}),
        "conflict_count": len(res.get("conflicts") or []),
    }
    return {
        "context": res["context"], "attr": attr, "seen": seen, "hits": hits,
        "subqueries": subq, "bundle_added": bundle_added,
        "direct_added": direct_added, "chap_added": chap_added,
        "lex_added": lex_added, "sources_used": len(admitted),
        "provenance": provenance, "budget_dropped_full": [],
    }


def install(app_module):
    """Install v2 as the production context builder once, retaining an escape hatch."""
    if getattr(app_module, "_retrieval_v2_installed", False):
        return
    baseline = app_module._draft_build_context

    def _v2(client, inp, facts_ret):
        try:
            return build(app_module, client, inp, facts_ret)
        except Exception as exc:
            # Availability guard: a v2 infrastructure failure must not take drafting down.
            # It is deliberately loud in logs and falls back only on an exception, never
            # on relevance/score outcomes.
            print("[retrieval-v2] runtime failure; baseline fallback:", repr(exc), flush=True)
            return baseline(client, inp, facts_ret)

    app_module._draft_build_context_baseline = baseline
    app_module._draft_build_context = _v2
    app_module._retrieval_v2_installed = True
