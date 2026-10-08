#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تشخيص تذبذب حالة في البطارية (§17) — قياس خالص، لا يمسّ الإنتاج بحرف.

العلّة المرصودة: الحالة 15 («تعليمات كفاية رأس المال الرقابي»، نوع
legislation_archived، معرّف واجب واحد) تسقط في جولة وتنجح في إعادتها بلا أي
تعديل كود — وذلك يُضعف صمّام الانتكاس من الجهتين: إنذار كاذب يُربك كل دفعة،
والأخطر أنه يُعوِّدنا على تفسير الفشل بـ«تقلّب عابر» فنفوّت انتكاسة حقيقية.

السؤال الذي يحدّد شكل العلاج (درس .bak_gateshik في §6): هل المعرّف الواجب
**مرشَّح يُقص** عند حدّ الحصة (العلاج: توسعة حصة / بوابة) أم **غائب كليًا** من
الترشيح (العلاج: بوابة مُرمَّزة حصرًا)؟ فلكل جولة يُسجَّل:
  • الحكم الرسمي: حضوره في `picked` بدالة البطارية نفسها (لا نسخة منها)
  • القناة التي جلبته (متجه/حزم/محلّ/فصول/معجمي/توسعات)
  • رتبته ودرجته في بحث المتجه بالحصة الحيّة
  • **رتبته في مسبار واسع** (حصة كبيرة على التشريعات) — وهو الذي يفرّق
    «يُقص» من «غائب»، ولا يُحتسب في الحكم أبدًا

الانضباط: المحاور تُقرأ من مخرج `retrieve` نفسه (لا نداء Haiku ثانٍ)،
والتضمين يُلتقط بكاش فلا يُحمَّل النموذج مرتين لنفس النصوص في الجولة.
التشغيل (بيئة الأدمن، من /opt/LegalMind):
  set -a; . deploy/.env; set +a
  admin/.venv/bin/python tools/diag_battery_case.py --case 15 --runs 10
"""
import os, sys, json, argparse, collections, time

ROOT = os.environ.get("LM_ROOT", "/opt/LegalMind")
for p in (ROOT, os.path.join(ROOT, "admin"), os.path.join(ROOT, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

from admin import app                      # noqa: E402
import kb_types as _kb                     # noqa: E402
import battery_run                         # noqa: E402  (دالة الحكم الرسمية)

WIDE = 80          # حصة المسبار الواسع — تشخيصية فقط، لا تمسّ الإنتاج
LIVE_MAIN = 10     # حصة الاستعلام الكامل في الإنتاج (تشريعات)
LIVE_SUB = 8       # حصة كل محور في الإنتاج (تشريعات)


def _install_embed_cache():
    """كاش للتضمين: `retrieve` ثم مرحلة العزو تطلبان النصوص نفسها حرفيًا،
    فلا يُحمَّل النموذج من القرص مرتين في الجولة (قياس سابق: ~34ث للتحميل)."""
    orig = app._draft_embed_multi
    cache = {}

    def wrapper(texts):
        key = tuple(texts)
        if key not in cache:
            cache[key] = orig(texts)
        return cache[key]

    app._draft_embed_multi = wrapper
    return cache


def _vector_ranks(vectors, targets):
    """رتبة ودرجة كل معرّف مطلوب في: (أ) الحصة الحيّة لكل متجه، (ب) المسبار الواسع.
    يُعاد لكل هدف: {"live": (مصدر، رتبة، درجة) أو None، "wide": (مصدر، رتبة، درجة) أو None}"""
    legis = list(_kb.LEGISLATION_TYPES)
    out = {t: {"live": None, "wide": None} for t in targets}
    for i, vec in enumerate(vectors):
        src = "الاستعلام الكامل" if i == 0 else "محور %d" % i
        lim = LIVE_MAIN if i == 0 else LIVE_SUB
        try:
            hits = app._draft_search(vec, legis, WIDE)
        except Exception as e:
            print("   (تعذّر المسبار الواسع على %s: %s)" % (src, e), flush=True)
            continue
        for rank, h in enumerate(hits, 1):
            oid = (h.get("payload") or {}).get("object_id")
            if oid not in out:
                continue
            sc = h.get("score")
            cur = out[oid]
            if cur["wide"] is None or rank < cur["wide"][1]:
                cur["wide"] = (src, rank, sc)
            if rank <= lim and (cur["live"] is None or rank < cur["live"][1]):
                cur["live"] = (src, rank, sc)
    return out


def _channel_attribution(rt, q, sq, targets):
    """أي قناة غير-متجهية تجلب كل هدف — بدوال الإنتاج نفسها لا نسخًا منها."""
    chans = collections.defaultdict(list)
    probes = (
        ("حزم", lambda: app._draft_bundles(rt, q, sq, None, None)),
        ("محلّ الإحالات", lambda: app._draft_direct_ids(rt, q, sq)),
        ("فصول حاكمة", lambda: app._draft_chap_ids(rt, q, sq)),
        ("معجمي", lambda: app._draft_lexical(sq, q)),
    )
    for name, fn in probes:
        try:
            ids = set(fn() or ())
        except Exception as e:
            print("   (قناة %s تعذّرت: %s)" % (name, e), flush=True)
            continue
        for t in targets:
            if t in ids:
                chans[t].append(name)
    return chans


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", type=int, required=True, help="رقم الحالة (1-based كما تُعرض في البطارية)")
    ap.add_argument("--runs", type=int, default=10)
    args = ap.parse_args()

    cases = json.load(open(os.path.join(ROOT, "battery.json")))
    if not (1 <= args.case <= len(cases)):
        raise SystemExit("DIAG_FAIL: رقم حالة خارج المدى (1..%d)" % len(cases))
    c = cases[args.case - 1]
    targets = list(c.get("must", []))
    if not targets:
        raise SystemExit("DIAG_FAIL: الحالة بلا `must` — هذا التشخيص مبنيٌّ على المعرّفات الواجبة")

    print("الحالة %d: %s" % (args.case, c["name"]), flush=True)
    print("المعرّفات الواجبة: %s" % "، ".join(targets), flush=True)
    print("الجولات: %d | المسبار الواسع: %d (تشخيصي لا يُحتسب في الحكم)\n" % (args.runs, WIDE), flush=True)

    _install_embed_cache()
    rows = []
    for n in range(1, args.runs + 1):
        t0 = time.time()
        picked, sq = battery_run.retrieve(c["rt"], c["q"])        # الحكم الرسمي
        query = c["rt"] + " - " + c["q"][:1500]
        vectors = app._draft_embed_multi([query] + sq)            # من الكاش
        ranks = _vector_ranks(vectors, targets)
        chans = _channel_attribution(c["rt"], c["q"], sq, targets)
        dt = time.time() - t0
        for t in targets:
            present = t in picked
            r = ranks[t]
            ch = list(chans.get(t, []))
            # عزو بالاستبعاد: حاضرٌ في الحكم ولم تجلبه قناةٌ مقيسة ولا حصةُ المتجه
            # ⇒ جاء من مرحلة التوسعات (XREF/شقيقات/prin_xref) التي لا تُقاس منفردة هنا
            if present and not ch and not r["live"]:
                ch = ["توسعات (استنتاج بالاستبعاد)"]
            rows.append({"run": n, "id": t, "present": present,
                         "live": r["live"], "wide": r["wide"],
                         "chans": ch, "axes": len(sq)})
            live = ("%s رتبة %d درجة %.3f" % (r["live"][0], r["live"][1], r["live"][2] or 0)) if r["live"] else "لا شيء"
            wide = ("رتبة %d درجة %.3f" % (r["wide"][1], r["wide"][2] or 0)) if r["wide"] else "غائب عن %d الأوائل" % WIDE
            print("جولة %2d/%d | %s %s | متجه حيّ: %s | واسع: %s | قنوات: %s | محاور: %d | مسترجَع: %d | %.0fث"
                  % (n, args.runs, "✓ حاضر" if present else "✗ غائب", t.rsplit("-", 1)[0],
                     live, wide, "، ".join(ch) or "لا شيء", len(sq), len(picked), dt),
                  flush=True)
        if args.runs > 1:
            # المحاور هي المشتبه الأول في التذبذب (درس صمّام سلامة المحاور، §6)
            print("   محاور الجولة: %s" % " | ".join(sq), flush=True)

    print("\n" + "=" * 70, flush=True)
    verdicts = []
    for t in targets:
        mine = [r for r in rows if r["id"] == t]
        hit = [r for r in mine if r["present"]]
        miss = [r for r in mine if not r["present"]]
        print("\n%s" % t, flush=True)
        print("  الحضور: %d/%d" % (len(hit), len(mine)), flush=True)
        if miss:
            trunc = [r for r in miss if r["wide"]]
            absent = [r for r in miss if not r["wide"]]
            if trunc:
                rr = sorted(r["wide"][1] for r in trunc)
                print("  في الجولات الساقطة — **مرشَّح يُقص**: %d جولة، رتبته في المسبار الواسع %s"
                      % (len(trunc), rr), flush=True)
            if absent:
                print("  في الجولات الساقطة — **غائب كليًا** عن %d الأوائل: %d جولة"
                      % (WIDE, len(absent)), flush=True)
            verdicts.append("TRUNCATED" if trunc and not absent else
                            ("ABSENT" if absent and not trunc else "MIXED"))
        else:
            verdicts.append("STABLE")
        if hit:
            lr = sorted(r["live"][1] for r in hit if r["live"])
            ch = collections.Counter(ch for r in hit for ch in r["chans"])
            print("  في الجولات الناجحة — رتب المتجه الحيّ: %s | القنوات: %s"
                  % (lr or "لا شيء (جاءت من قناة غير متجهية)", dict(ch) or "لا شيء"), flush=True)
        ax = collections.Counter(r["axes"] for r in mine)
        print("  عدد المحاور لكل جولة: %s" % dict(ax), flush=True)

    v = "STABLE" if all(x == "STABLE" for x in verdicts) else (
        "TRUNCATED" if all(x in ("STABLE", "TRUNCATED") for x in verdicts) else
        ("ABSENT" if all(x in ("STABLE", "ABSENT") for x in verdicts) else "MIXED"))
    print("\nالحكم: %s" % {
        "STABLE": "لا تذبذب في هذه الجولات — الحضور كامل، فلا رقعة تُبنى على لا شيء",
        "TRUNCATED": "مرشَّح يُقص عند حدّ الحصة ← العلاج توسعة حصة أو بوابة",
        "ABSENT": "غائب كليًا من الترشيح ← العلاج بوابة مُرمَّزة حصرًا (فئة «الاستلزام القانوني»)",
        "MIXED": "الفئتان معًا ← يُفصَّل لكل معرّف بما طُبع أعلاه",
    }[v], flush=True)
    print("DIAG_CASE_%s" % v, flush=True)


if __name__ == "__main__":
    main()
