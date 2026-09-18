# -*- coding: utf-8 -*-
"""اشتقاق عمق المرشحين من البيانات لا من التخمين (Recall@k).

المصدر: 98 نداء بحث حقيقيًا من تشغيل P2.7-O (limit=20 لكل نداء، 1,959 نتيجة
خام بمعرّفاتها ورتبها)، والأهداف: مجموعة الضوابط المجمَّدة نفسها
(NEAR_AND_RELATED + RELATED_BUT_NONADJACENT) التي لم تتغير منذ P2.7-L.

يقيس: أي نسبة من الأهداف **تظهر أصلًا** في نتائج الاستعلامات عند عمق k، لكل
k من 1 إلى 20. هذا `Candidate Recall` الخام — الطابق الأول من القمع — ولا
يقيس نجاة المرشح إلى السياق النهائي."""
import json, re, sys, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = json.load(open("/home/user/LegalMind/tools/p27o_forensic_raw_calls.json"))
GT = json.load(open(os.path.join(ROOT, "tools/p27l_controls_ground_truth.json")))["anchors"]
CASE_OF = {"A1_labour_limitation": "A1", "A2_prosecution_intervention": "A2",
           "A3_cheque_limitation": "A3"}


def fam(i):
    m = re.match(r'^(jprin-\d+-\d+)-', i or '')
    return m.group(1) if m else i


targets = []      # (case, id, class)
for g, a in GT.items():
    for cls in ("NEAR_AND_RELATED", "RELATED_BUT_NONADJACENT"):
        for x in a.get(cls, []):
            targets.append((CASE_OF[g], x["id"], cls))

def curve(ks):
    out = {}
    for k in ks:
        seen = set()
        for case, tid, cls in targets:
            f = fam(tid)
            for c in RAW[case]:
                for h in c["hits"][:k]:
                    if h["object_id"] == tid or fam(h["object_id"]) == f:
                        seen.add((case, tid))
                        break
                if (case, tid) in seen:
                    break
        out[k] = len(seen)
    return out


if __name__ == "__main__":
    ks = list(range(1, 21))
    cv = curve(ks)
    n = len(targets)
    print("الأهداف المقيسة: %d  (NAR %d + RBN %d)" % (
        n, sum(1 for t in targets if t[2] == "NEAR_AND_RELATED"),
        sum(1 for t in targets if t[2] == "RELATED_BUT_NONADJACENT")))
    print("\n k   ظهر  Candidate-Recall   الفرق عن k-1")
    prev = 0
    for k in ks:
        v = cv[k]
        print("%2d   %3d   %6.3f            %+d" % (k, v, v / n, v - prev))
        prev = v
    print("\nنقاط القرار:")
    for k in (8, 12, 16, 20):
        print("  Recall@%-2d = %.3f  (%d/%d)" % (k, cv[k] / n, cv[k], n))
    plateau = None
    for k in ks[2:]:
        if cv[k] == cv[k - 1] == cv[k - 2]:
            plateau = k - 2
            break
    print("\nأول هضبة (ثلاث قيم متتالية بلا زيادة): k = %s" % plateau)
    json.dump({"targets": n, "curve": cv, "plateau_k": plateau},
              open(os.path.join(ROOT, "tools/depth_curve.json"), "w"),
              ensure_ascii=False, indent=1)
