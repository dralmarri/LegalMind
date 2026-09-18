# -*- coding: utf-8 -*-
"""أثر القنوات الجديدة على نفس الضوابط المجمَّدة — ومحاكاة الترتيب المدمَج.

يقيس ثلاثة أشياء منفصلة، ولا يخلطها:
 (1) ما تصله القناة الكثيفة وحدها عند أي عمق (من 1,959 نتيجة خام حقيقية).
 (2) ما تصله قناة الجوار البنيوي إضافةً — **وهي تصل جيران القانون نفسه بحكم
     بنائها، لا باكتشاف**، والضوابط الموجبة هنا مُعرَّفة أصلًا بقربها الرقمي،
     فالرقم الناتج لا يُقرأ تحسّنًا عامًا في الاسترجاع.
 (3) أين يقع الضابط السالب (NEAR_BUT_UNRELATED) في الترتيب المدمَج — وهو
     السؤال الحقيقي: هل يشتري الاتساعُ تغطيةً بثمن ضجيج مقبول؟"""
import json, re, os, sys
ROOT = "/home/user/LegalMind"
sys.path.insert(0, ROOT)
from retrieval.pool import CandidatePool
from retrieval.fusion import fuse
from retrieval.model import CH_DENSE, CH_ADJACENCY, LAYER_LEGISLATION, LAYER_PRINCIPLE

RAW = json.load(open(ROOT + "/tools/p27o_forensic_raw_calls.json"))
GT = json.load(open(ROOT + "/tools/p27l_controls_ground_truth.json"))["anchors"]
CASE_OF = {"A1_labour_limitation": "A1", "A2_prosecution_intervention": "A2",
           "A3_cheque_limitation": "A3"}
ANCHORS = {"A1": ["legis-6-2010-m144"],
           "A2": ["legis-51-1984-m337", "legis-51-1984-m338"],
           "A3": ["legis-68-1980-m550", "legis-68-1980-m551"]}
ART = re.compile(r"^(.*-)m(\d{1,4})$")


def fam(i):
    m = re.match(r'^(jprin-\d+-\d+)-', i or '')
    return m.group(1) if m else i


def targets_of(case):
    g = [k for k, v in CASE_OF.items() if v == case][0]
    a = GT[g]
    return ({x["id"] for x in a.get("NEAR_AND_RELATED", [])}
            | {x["id"] for x in a.get("RELATED_BUT_NONADJACENT", [])},
            {x["id"] for x in a.get("NEAR_BUT_UNRELATED", [])})


def dense_pool(case, depth):
    """يعيد بناء القناة الكثيفة من النتائج الخام الحقيقية عند عمق depth."""
    p = CandidatePool()
    for c in RAW[case]:
        lay = LAYER_LEGISLATION if c["kind"] == "تشريع" else LAYER_PRINCIPLE
        for h in c["hits"][:depth]:
            p.add(h["object_id"], CH_DENSE, h["rank"], h["score"], lay)
    return p


def add_adjacency(pool, case, window=4):
    """جوار بنيوي محاكًى: نفس بادئة القانون، بموضع ترتيبي ضمن النافذة.

    قائمة مواد القانون هنا تُقرَّب بأرقام المواد الظاهرة في الضوابط والمراسي
    (لا اتصال بالقاعدة من هذه البيئة) — والتقريب **لصالح الضابط السالب**: كل
    جار سالب يدخل التجمّع فعلًا، فلا يُخفى الضجيج."""
    known = set()
    for a in ANCHORS[case]:
        known.add(a)
    rel, nbu = targets_of(case)
    known |= {i for i in (rel | nbu) if ART.match(i)}
    for a in ANCHORS[case]:
        m = ART.match(a)
        if not m:
            continue
        pref, n = m.group(1), int(m.group(2))
        sib = sorted([i for i in known if i.startswith(pref)],
                     key=lambda i: int(ART.match(i).group(2)))
        pos = sib.index(a)
        for j in range(max(0, pos - window), min(len(sib), pos + window + 1)):
            if sib[j] != a:
                pool.add(sib[j], CH_ADJACENCY, abs(j - pos), 0.0, LAYER_LEGISLATION)
    return pool


if __name__ == "__main__":
    DEPTH = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    tot_rel = tot_nbu = 0
    hit_dense = hit_all = adm_nbu = 0
    rows = []
    for case in ("A1", "A2", "A3"):
        rel, nbu = targets_of(case)
        tot_rel += len(rel); tot_nbu += len(nbu)
        pd = dense_pool(case, DEPTH)
        dense_ids = {c.object_id for c in pd}
        dfam = {fam(i) for i in dense_ids}
        hit_dense += sum(1 for t in rel if t in dense_ids or fam(t) in dfam)
        pa = add_adjacency(dense_pool(case, DEPTH), case)
        allids = {c.object_id for c in pa}
        afam = {fam(i) for i in allids}
        hit_all += sum(1 for t in rel if t in allids or fam(t) in afam)
        ranked = fuse(pa)
        order = {c.object_id: i + 1 for i, c in enumerate(ranked)}
        rel_ranks = sorted(order[t] for t in rel if t in order)
        nbu_ranks = sorted(order[t] for t in nbu if t in order)
        rows.append((case, len(ranked), rel_ranks, nbu_ranks))
    print("العمق الكثيف المستعمَل: %d\n" % DEPTH)
    print("Candidate Recall على الضوابط الموجبة (17 هدفًا):")
    print("  كثيف وحده          : %d/%d = %.3f" % (hit_dense, tot_rel, hit_dense / tot_rel))
    print("  + الجوار البنيوي    : %d/%d = %.3f   ← تغطية بنيوية لا اكتشافًا" % (
        hit_all, tot_rel, hit_all / tot_rel))
    print("\nموضع الضابط السالب في الترتيب المدمَج (كلما كبر الرقم كان أبعد عن القبول):")
    print("%-5s %-8s %-28s %s" % ("حالة", "التجمّع", "رتب الأهداف الموجبة", "رتب NEAR_BUT_UNRELATED"))
    for case, n, rr, nr in rows:
        print("%-5s %-8d %-28s %s" % (case, n, rr, nr))
    worst_rel = max((max(r) for _c, _n, r, _nb in rows if r), default=0)
    best_nbu = min((min(nb) for _c, _n, _r, nb in rows if nb), default=10 ** 9)
    print("\nأسوأ رتبة لهدف موجب = %s   |   أفضل رتبة لضابط سالب = %s" % (worst_rel, best_nbu))
    print("الفصل %s" % ("محقَّق (كل موجب يسبق كل سالب)" if worst_rel < best_nbu
                        else "غير محقَّق — تداخل"))
    json.dump({"depth": DEPTH, "dense_recall": hit_dense / tot_rel,
               "with_adjacency": hit_all / tot_rel,
               "rows": [[c, n, r, nb] for c, n, r, nb in rows]},
              open(ROOT + "/tools/channel_gain.json", "w"), ensure_ascii=False, indent=1)
