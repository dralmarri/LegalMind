# -*- coding: utf-8 -*-
"""طبقة النماذج الموحدة — v2: مزوّدان (Anthropic افتراضًا، وOpenAI خلف الواجهة نفسها).

الأدوار تُختار بالبيئة لكل دور على حدة:
    LEGALMIND_FAST_PROVIDER   — المحاور وإحالات الأوراق (افتراضيًا anthropic)
    LEGALMIND_DRAFT_PROVIDER  — التوليد وجولة التنقيح   (افتراضيًا anthropic)
ونماذج OpenAI تُسمّى صراحةً (لا تخمين أسماء):
    LEGALMIND_OPENAI_FAST_MODEL / LEGALMIND_OPENAI_DRAFT_MODEL

المخرج موحَّد: كائن يحمل .content (كتل نصية بـ.type/.text) و.model و.stop_reason —
فلا يتغير حرف في app.py مهما كان المزوّد.
القاعدة المعمارية: ملف واحد يتوسع بما تثبته الأرقام — لا هيكل مسبق."""
import os


def _env(name):
    """قراءة إعداد: بيئة العملية أولًا ثم ملف deploy/.env مباشرة عند كل نداء —
    سلوك مفتاح Anthropic نفسه في app.py: تغيير الملف يسري بلا إعادة تشغيل الخدمة.
    (بيئة خدمة systemd لا تحمل الملف — جذر عطل «OPENAI_API_KEY غير مضبوط».)"""
    v = os.getenv(name)
    if v:
        return v
    try:
        with open("/opt/LegalMind/deploy/.env", encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if ln.startswith("export "):
                    ln = ln[7:].strip()
                if ln.startswith(name + "="):
                    return ln.split("=", 1)[1].strip().strip('"').strip("'") or None
    except Exception:
        pass
    return None


# ── المخرج الموحّد ──────────────────────────────────────────────────────────
class _Block:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _Usage:
    def __init__(self, inp, out):
        self.input_tokens = inp
        self.output_tokens = out


class _Resp:
    def __init__(self, text, model, refusal=False, usage=None):
        self.content = [_Block(text or "")]
        self.model = model
        self.stop_reason = "refusal" if refusal else "end_turn"
        # حزمة الأدلة في app.py تقرأ resp.usage.input_tokens/output_tokens حتمًا —
        # غيابها أسقط جولة GPT كاملة في آخر سطر (AttributeError موثق 2026-08-15)
        self.usage = usage or _Usage(0, 0)


def _role_provider(role, override=None):
    if override:
        return override.strip().lower()
    return (_env("LEGALMIND_%s_PROVIDER" % role.upper()) or "anthropic").strip().lower()


# ── مزوّد OpenAI ────────────────────────────────────────────────────────────
def _oa_client():
    key = _env("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY غير مضبوط في البيئة")
    from openai import OpenAI
    return OpenAI(api_key=key)


def _oa_model(role):
    m = _env("LEGALMIND_OPENAI_%s_MODEL" % role.upper())
    if not m:
        raise RuntimeError("LEGALMIND_OPENAI_%s_MODEL غير مضبوط — يُسمّى النموذج صراحةً"
                           % role.upper())
    return m


def _oa_input(messages):
    """محوّل الوسائط: كتل Anthropic (text/image/document) ← نسق Responses API."""
    out = []
    for m in messages:
        role = m.get("role", "user")
        c = m.get("content")
        if isinstance(c, str):
            kind = "output_text" if role == "assistant" else "input_text"
            out.append({"role": role, "content": [{"type": kind, "text": c}]})
            continue
        blocks = []
        for b in (c or []):
            t = b.get("type")
            if t == "text":
                kind = "output_text" if role == "assistant" else "input_text"
                blocks.append({"type": kind, "text": b.get("text", "")})
            elif t == "image":
                s = b.get("source") or {}
                blocks.append({"type": "input_image", "image_url": "data:%s;base64,%s"
                               % (s.get("media_type") or "image/jpeg", s.get("data", ""))})
            elif t == "document":
                s = b.get("source") or {}
                blocks.append({"type": "input_file", "filename": "document.pdf",
                               "file_data": "data:application/pdf;base64," + (s.get("data") or "")})
        out.append({"role": role, "content": blocks})
    return out


def _oa_call(role, system, messages, max_tokens):
    # ترتيب مقصود: تحقق الإعدادات (مفتاح ثم اسم نموذج) قبل أي استيراد/اتصال فعلي —
    # فرسالة الخطأ الواضحة تصل حتى إن كانت حزمة openai غير مثبتة أو الاتصال معطوبًا
    if not _env("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY غير مضبوط في البيئة")
    model = _oa_model(role)
    cli = _oa_client()
    r = cli.responses.create(model=model, instructions=system,
                             input=_oa_input(messages), max_output_tokens=max_tokens)
    txt = getattr(r, "output_text", "") or ""
    refused = (not txt.strip()) and str(getattr(r, "status", "")) == "incomplete"
    u = getattr(r, "usage", None)
    usage = _Usage(getattr(u, "input_tokens", 0) or 0, getattr(u, "output_tokens", 0) or 0)
    return _Resp(txt, model, refusal=refused, usage=usage)


# ── مزوّد Anthropic ─────────────────────────────────────────────────────────
def _stream_final(msgs_api, **kw):
    # بث متدفق مع تجميع الرسالة النهائية — يتجاوز حد الدقائق العشر
    with msgs_api.stream(**kw) as s:
        return s.get_final_message()


# ── الواجهتان ───────────────────────────────────────────────────────────────
def fast_create(client, *, provider=None, **kw):
    """النموذج السريع (المحاور/إحالات الأوراق/التدقيق المتقاطع).
    provider: تجاوز صريح لهذا النداء وحده — التدقيق المتقاطع يفرض به المزوّد المقابل."""
    prov = _role_provider("fast", provider)
    if prov == "anthropic":
        return client.messages.create(**kw)
    if prov == "openai":
        return _oa_call("fast", kw.get("system"), kw.get("messages") or [],
                        kw.get("max_tokens") or 1500)
    raise RuntimeError("مزوّد غير مدعوم للدور السريع: " + prov)


def draft_create(client, *, model, system, messages, max_tokens=24000, provider=None):
    """التوليد الطويل وجولة التنقيح — سلوك Anthropic مطابق حرفيًا لما كان في app.py.
    provider: تجاوز صريح لدور هذا النداء وحده — لا يمس البيئة العامة ولا طلبات
    أخرى متزامنة — يفعّل اختيار المزوّد لكل جولة استوديو."""
    prov = _role_provider("draft", provider)
    if prov == "openai":
        return _oa_call("draft", system, messages, max_tokens)
    if prov != "anthropic":
        raise RuntimeError("مزوّد غير مدعوم للتوليد: " + prov)
    if model.startswith("claude-fable"):
        # Fable 5: التفكير مفعل دائمًا؛ تراجع تلقائي إلى Opus 4.8 عند رفض الأمان
        return _stream_final(client.beta.messages,
                             model=model, max_tokens=max_tokens,
                             betas=["server-side-fallback-2026-06-01"],
                             fallbacks=[{"model": "claude-opus-4-8"}],
                             system=system, messages=messages)
    return _stream_final(client.messages,
                         model=model, max_tokens=max_tokens,
                         thinking={"type": "adaptive"},
                         system=system, messages=messages)


def healthcheck():
    """تشخيص سريع: أي مزوّد لكل دور، وهل مفتاحه ونموذجه حاضران (بلا كشف قيم)."""
    out = {}
    for role in ("fast", "draft"):
        p = _role_provider(role)
        d = {"provider": p}
        if p == "openai":
            d["key"] = bool(_env("OPENAI_API_KEY"))
            d["model"] = _env("LEGALMIND_OPENAI_%s_MODEL" % role.upper()) or None
        else:
            d["key"] = bool(_env("ANTHROPIC_API_KEY"))
        out[role] = d
    return out
