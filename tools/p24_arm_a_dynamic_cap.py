#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.4 — Arm A: Dynamic Pre-Rerank Candidate Admission.

هدف ضيّق ومحدَّد: علاج `PRE_RERANK_CAP_FAILURE`/`INTERMITTENT_PRE_RERANK_CAP_FAILURE` وحدهما
(الفئة المؤكَّدة تجريبيًا في P2.3 لـ`regl-1-2016-m65` وlegis-20-2015-m49`: اكتشاف كثيف موثوق
5/5، نجاة سقف متذبذبة 1:4 بسبب تنافس حافة عشوائي شبه). **ليست سياسة مصمَّمة لهذين الهدفين
تحديدًا** — بُنيت من خصائص إحصائية عامة لحوض المرشحين فقط، وتُقاس على Gold Set كاملة، لا
عليهما فقط.

**الخصائص المسموح بها حصرًا (كلها من `grouped` نفسه، صفر اطلاع خارجي):**
- كثافة الحوض (عدد المرشحين لكل تسمية مقابل السقف الثابت الأصلي).
- توزيع الدرجات (الفروق المحلية بين الدرجات المتتالية قرب حافة القطع).
- فجوة الدرجة قرب القطع (انخفاض حاد حقيقي = حد فاصل طبيعي بين مجموعتين من الصلة).
- تنوع الأبعاد القانونية (`topic`/`subtopic` من الحمولة نفسها).
- التنوع الكانوني (بادئة القانون المصدر من `object_id`، مثال: `legis-51-1984` من
  `legis-51-1984-m300`).

**آلية التمديد:** يُقبَل السقف الأساسي دومًا (لا تغيير في رأس الترتيب). في "منطقة التمديد"
(من السقف الأساسي حتى حد أقصى مطلق `base_n * (1+MAX_EXTRA_FRAC)` — يمنع انفجار الحوض/التكلفة)
يُحسَب حد فاصل إحصائي محلي (متوسط + `GAP_Z` انحراف معياري لفروق الدرجات حول حافة القطع
الأصلية)؛ يتوقف القبول عند أول فجوة حقيقية تتجاوز هذا الحد. ضمن منطقة التمديد، تُعطى أفضلية
لمرشح يُدخِل (topic, subtopic) جديدًا أو بادئة قانون كانونية جديدة لم تُمثَّل بعد في المقبولين
— هذا هو المعنى العملي لـ"تنوع الأبعاد/الكانوني" هنا: كسر تعادل، لا معيار قبول مستقل."""
import statistics


def _canonical_prefix(oid):
    """بادئة القانون الكانونية من المعرِّف — مثال: legis-51-1984-m300 → legis-51-1984.
    عامة بالكامل (نمط تقسيم لا قائمة معرِّفات)، لا اعتماد على أي حالة بعينها."""
    if not oid:
        return None
    parts = oid.split("-")
    # المعرِّفات القانونية الشائعة: <بادئة>-<رقم>-<سنة>-<مادة...> — نأخذ أول ثلاثة أجزاء
    if len(parts) >= 3 and parts[0] in ("legis", "regl", "lreg", "reg"):
        return "-".join(parts[:3])
    return oid.rsplit("-", 1)[0] if "-" in oid else oid


def dynamic_admission_policy(grouped, base_caps=None, max_extra_frac=0.5, gap_z=1.0,
                              local_window_radius=5):
    """§ArmA — راجع توثيق الوحدة للمنهجية الكاملة. base_caps افتراضيًا = caps_n الإنتاجية
    (مستوردة من p24_offline_pipeline لتفادي ازدواج الرقم الحقيقي)."""
    import p24_offline_pipeline as _pipe
    base_caps = base_caps or _pipe.CAPS_N_PRODUCTION

    admitted, cut_ids = {}, []
    diag = {}  # تشخيص لكل تسمية: extended_by, stopping_gap, pool_density
    for label, items in grouped.items():
        items_sorted = sorted(items, reverse=True, key=lambda x: x[0])
        n = len(items_sorted)
        base_n = base_caps.get(label, 20)

        if n <= base_n:
            admitted[label] = items_sorted
            diag[label] = {"pool_density": n, "extended_by": 0, "stopping_gap": None}
            continue

        scores = [it[0] for it in items_sorted]
        max_n = min(n, base_n + max(1, int(base_n * max_extra_frac)))

        diffs = [scores[i] - scores[i + 1] for i in range(len(scores) - 1)]
        lo = max(0, base_n - local_window_radius)
        hi = min(len(diffs), base_n + local_window_radius)
        local_window = diffs[lo:hi]
        local_mean = statistics.mean(local_window) if local_window else 0.0
        local_std = statistics.pstdev(local_window) if len(local_window) > 1 else 0.0
        threshold = local_mean + gap_z * local_std

        # تنوع المقبولين حتى الآن (للأفضلية داخل منطقة التمديد فقط — لا معيار قبول مستقل)
        seen_topics = set()
        seen_canon = set()
        for _sc, _lb, p in items_sorted[:base_n]:
            seen_topics.add((p.get("topic"), p.get("subtopic")))
            seen_canon.add(_canonical_prefix(p.get("object_id")))

        # حوض المرشحين المتبقين يبقى بترتيب الدرجة الأصلي (نازلًا) — التنوع **لا** يُعيد ترتيبه
        # ككل (ذلك يسمح لمرشح بعيد جدًا في الذيل بالتسلل قبل مرشحين أقرب فعليًا للحافة، وهو عكس
        # المقصود بالضبط: "كسر تعادل، لا معيار قبول مستقل"). بدل ذلك: في كل خطوة، تُحسَب "الجبهة
        # المقبولة الآن" (كل مرشح متتالٍ من الرأس يجتاز فحص الفجوة نسبةً لآخر درجة مقبولة فعليًا)
        # ثم يُكسَر التعادل **داخل هذه الجبهة فقط** بتفضيل الأكثر تنوعًا — فمرشح بعيد الدرجة لا
        # يزاحم أبدًا مرشحًا مؤهَّلًا الآن، ولا يقطع التمديد كله لمجرد وروده في الحوض.
        remaining = list(enumerate(items_sorted[base_n:n], start=base_n))

        def _diversity_key(entry):
            idx, (sc, lb, p) = entry
            introduces_new = (
                (p.get("topic"), p.get("subtopic")) not in seen_topics
                or _canonical_prefix(p.get("object_id")) not in seen_canon
            )
            return (not introduces_new, idx)  # الجديد أولًا (False < True)، ثم ترتيب الدرجة الأصلي

        admit_n = base_n
        stopping_gap = None
        admitted_extension = []
        # الفجوة تُقاس دومًا نسبةً لآخر درجة مقبولة فعليًا (لا الجار المتسلسل بالفهرس الخام) —
        # لازم لأن التعادل يُكسَر بالتنوع لا بترتيب الدرجة وحده.
        last_admitted_score = scores[base_n - 1] if base_n > 0 else (scores[0] if scores else 0.0)
        while remaining and admit_n < max_n:
            admissible = []
            for idx, (sc, lb, p) in remaining:
                gap = last_admitted_score - sc
                if gap > threshold and gap > 0:
                    break  # remaining مرتبة تنازليًا — كل ما يلي أضعف فيفشل الفحص أيضًا
                admissible.append((idx, (sc, lb, p)))

            if not admissible:
                stopping_gap = round(last_admitted_score - remaining[0][1][0], 6)
                break

            admissible.sort(key=_diversity_key)
            win_idx, (win_sc, win_lb, win_p) = admissible[0]

            admitted_extension.append((win_sc, win_lb, win_p))
            last_admitted_score = win_sc
            seen_topics.add((win_p.get("topic"), win_p.get("subtopic")))
            seen_canon.add(_canonical_prefix(win_p.get("object_id")))
            admit_n += 1
            remaining = [(i, t) for i, t in remaining if i != win_idx]

        admitted[label] = items_sorted[:base_n] + admitted_extension
        admitted_ids = {p.get("object_id") for _s, _l, p in admitted[label]}
        cut_ids += [p.get("object_id") for _s, _l, p in items_sorted if p.get("object_id") not in admitted_ids]
        diag[label] = {
            "pool_density": n, "extended_by": len(admitted_extension),
            "stopping_gap": stopping_gap, "threshold": round(threshold, 6),
        }

    return admitted, cut_ids, diag


def dynamic_admission_policy_for_pipeline(grouped):
    """توقيع مطابق لما يتوقعه build_context_offline (يُعيد (admitted, cut_ids) فقط، بلا diag) —
    لاستعمال p24_offline_pipeline.build_context_offline(..., admission_policy=هذه)."""
    admitted, cut_ids, _diag = dynamic_admission_policy(grouped)
    return admitted, cut_ids
