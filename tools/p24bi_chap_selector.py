#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2.5 — Experiment B2-I: نسخة بنيوية أمينة (structural replica) من آلية `_draft_chap_ids`
الحقيقية الحاكمة — **ليست نسخة حرفية مُعاد التحقق منها على الخادم الحي في هذه الجولة** (ذاك
تحقَّق سابقًا في P2.3/P2.4A وأنتج التشخيص الموثَّق: تسجيل/فرز مجموعات + سقف عام مشترك 30 +
تعبئة على مرحلتين)، بل محاكاة تحافظ على **الخاصية البنيوية الحاسمة** التي تسبِّب الانحدار:
سقف عالمي مشترك + إعادة ترتيب حساسة لرموز الاستعلام + تعبئة جزئية على مرحلتين — وهي الخاصية
الوحيدة التي تحتاجها تجربة B2-I لاختبار سلامة ثلاثة تصاميم دمج مختلفة، بصرف النظر عن تفاصيل
الـregex/التجذيع الدقيقة في الإنتاج (تلك لا تغيّر خاصية السلامة البنيوية المختبَرة هنا).

يستعمل `Dependency.scope_target` (عبارات نطاق بلغة طبيعية) من Arm B v1 المجمَّد كمصدر وحيد
لرموز "A" الإضافية — لا محرك B2-R v2 الجديد إطلاقًا، كما تنص مواصفة P2.5 صراحة."""
import re

CAP = 30

_PREFIXES = ("بال", "فال", "كال", "لل", "وال", "ال")


def _norm(w):
    w = w.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ى", "ي").replace("ة", "ه")
    for p in _PREFIXES:
        if w.startswith(p) and len(w) - len(p) >= 2:
            return w[len(p):]
    return w


def tok(text):
    """أداة توكين عامة مستقلة تمامًا عن أي محرك تعرّف (B2-R) — تطبيع أساسي (همزة/تاء مربوطة/
    ألف مقصورة + إسقاط أداة التعريف الملتصقة) ضروري لمطابقة واقعية بين نص الوقائع الطبيعي
    (يحمل «ال» ملتصقة) وقوائم الرموز الأساسية للمجموعات (مجردة)."""
    return {_norm(w) for w in re.findall(r"[ء-ي]{2,}", text or "")}


def _hit(query_tokens, group):
    strong = query_tokens & group["tokens"]
    if not strong:
        return None
    ratio = len(strong) / max(1, len(group["tokens"]))
    return (len(strong), ratio)


def select_chapters(query_tokens, chapter_index, gates=None, cap=CAP):
    """يُعيد (out_ids: list, provenance: dict{id: {"group": label, "score": (..)}})."""
    scored = []
    for g in chapter_index:
        s = _hit(query_tokens, g)
        if s is not None:
            scored.append((s, g))
    scored.sort(key=lambda sg: sg[0], reverse=True)

    trimmed = []
    for score, g in scored:
        arts = g["arts"]
        if len(arts) > 8:
            arts = arts[:6] + arts[-2:]
        trimmed.append((score, g["label"], arts))

    out, added = [], set()
    prov = {}

    # المرحلة 1: المجموعات الصغيرة (≤6) كاملة، أو أول 3 من المجموعات الكبيرة
    for score, label, arts in trimmed:
        if len(out) >= cap:
            break
        take = arts if len(arts) <= 6 else arts[:3]
        for a in take:
            if a in added or len(out) >= cap:
                continue
            out.append(a)
            added.add(a)
            prov[a] = {"group": label, "score": score, "pass": 1}

    # المرحلة 2: تكملة الباقي بنفس ترتيب الفرز
    for score, label, arts in trimmed:
        if len(out) >= cap:
            break
        for a in arts:
            if a in added or len(out) >= cap:
                continue
            out.append(a)
            added.add(a)
            prov[a] = {"group": label, "score": score, "pass": 2}

    # _GATES: بوابات إلزامية غير مسقوفة — تُضاف كاملة دون تنافس على cap
    for gate_words, gate_arts in (gates or []):
        if query_tokens & gate_words:
            for a in gate_arts:
                if a not in added:
                    out.append(a)
                    added.add(a)
                    prov[a] = {"group": "GATE", "score": None, "pass": "gate"}

    return out, prov
