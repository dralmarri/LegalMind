# -*- coding: utf-8 -*-
"""راصد النماذج: ترقية OpenAI تلقائيًا عند ظهور أحدث (بنداء حي قبل الاعتماد)،
ورصد أحدث عائلة claude-fable للإبلاغ. يعمل أسبوعيًا عبر cron.weekly."""
import sys, re, datetime
sys.path.insert(0, "/opt/LegalMind")
from admin import llm

LOG = "/opt/legalmind-data/modelwatch.log"


def log(*a):
    line = "[%s] %s" % (datetime.datetime.utcnow().isoformat(timespec="seconds"),
                        " ".join(str(x) for x in a))
    print(line, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def ver(name, pat):
    m = re.fullmatch(pat, name or "")
    if not m:
        return None
    return tuple(int(x) for x in m.group(1).replace("-", ".").split("."))


def check_openai():
    key = llm._env("OPENAI_API_KEY")
    if not key:
        log("openai: لا مفتاح — تخطٍّ")
        return
    from openai import OpenAI
    cli = OpenAI(api_key=key)
    names = [m.id for m in cli.models.list()]
    cands = {}
    for n in names:
        v = ver(n, r"gpt-(\d+(?:\.\d+)?)")   # الاسم الرئيس الصِرف فقط — لا mini/nano/تواريخ
        if v:
            cands[v] = n
    if not cands:
        log("openai: لا مرشح بنمط gpt-N.N في القائمة — لا تدخل")
        return
    best_v = max(cands)
    best = cands[best_v]
    cur = llm._env("LEGALMIND_OPENAI_DRAFT_MODEL") or ""
    cur_v = ver(cur, r"gpt-(\d+(?:\.\d+)?)")
    if cur_v is None:
        log("openai: المضبوط (%s) خارج النمط الرئيس — لا تدخل آلي" % cur)
        return
    if best_v <= cur_v:
        log("openai: المضبوط %s هو الأحدث — لا تغيير" % cur)
        return
    r = cli.responses.create(model=best, input="Reply with exactly one word: OK",
                             max_output_tokens=20)
    if not (getattr(r, "output_text", "") or "").strip():
        log("openai: %s موجود لكنه لم يرد ردًا صالحًا — لا ترقية" % best)
        return
    P = "/opt/LegalMind/deploy/.env"
    src = open(P, encoding="utf-8").read()
    for var in ("LEGALMIND_OPENAI_FAST_MODEL", "LEGALMIND_OPENAI_DRAFT_MODEL"):
        src = re.sub(r"(?m)^%s=.*$" % var, "%s=%s" % (var, best), src)
    open(P, "w", encoding="utf-8").write(src)
    log("openai: ⬆ ترقية تلقائية %s ← %s (نداء حي ناجح؛ تسري فورًا)" % (cur, best))


def check_anthropic():
    key = llm._env("ANTHROPIC_API_KEY")
    if not key:
        log("anthropic: لا مفتاح — تخطٍّ")
        return
    try:
        import anthropic
        cli = anthropic.Anthropic(api_key=key)
        names = [m.id for m in cli.models.list()]
    except Exception as e:
        log("anthropic: تعذر جلب القائمة:", str(e)[:150])
        return
    cur = "claude-fable-5"
    cands = {}
    for n in names:
        v = ver(n, r"claude-fable-(\d+(?:-\d+)?)")
        if v:
            cands[v] = n
    if not cands:
        log("anthropic: لا نماذج بعائلة claude-fable في القائمة")
        return
    best_v = max(cands)
    best = cands[best_v]
    if ver(cur, r"claude-fable-(\d+(?:-\d+)?)") and best_v <= ver(cur, r"claude-fable-(\d+(?:-\d+)?)"):
        log("anthropic: %s هو أحدث عائلة fable — لا جديد" % cur)
        return
    log("anthropic: 🔔 ظهر نموذج أحدث في عائلة fable: %s — نموذج الصياغة الرئيس يُرقّى بقرار المالك (أخبر مساعدك)" % best)


if __name__ == "__main__":
    log("— جولة رصد —")
    try:
        check_openai()
    except Exception as e:
        log("openai: خطأ غير متوقع:", str(e)[:200])
    try:
        check_anthropic()
    except Exception as e:
        log("anthropic: خطأ غير متوقع:", str(e)[:200])
    log("— انتهت —")
