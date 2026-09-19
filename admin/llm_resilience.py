# -*- coding: utf-8 -*-
"""Production resilience for long LegalMind drafting calls.

Keeps Retrieval v2 and the authority packet untouched.  This module hardens
provider transport and, specifically, the OpenAI leg used by dual-model drafting.
"""
import time

OPENAI_BACKGROUND_POLL_SECONDS = 2.0
OPENAI_BACKGROUND_MAX_SECONDS = 1500.0

DRAFT_TRANSPORT_TIMEOUT_SECONDS = 1800.0
OPENAI_DRAFT_ATTEMPTS = 3


def _error_text(exc):
    """Return a useful provider error without leaking credentials or request bodies."""
    name = type(exc).__name__
    msg = str(exc).replace("\n", " ").strip()
    if len(msg) > 500:
        msg = msg[:500] + "…"
    return (name + ": " + msg) if msg else name


def install(llm_module):
    """Install transport/retry hardening idempotently."""
    if getattr(llm_module, "_legalmind_resilience_installed", False):
        return

    original_stream_final = llm_module._stream_final

    def _stream_final_resilient(msgs_api, **kw):
        kw.setdefault("timeout", DRAFT_TRANSPORT_TIMEOUT_SECONDS)
        return original_stream_final(msgs_api, **kw)

    llm_module._stream_final = _stream_final_resilient

    def _oa_client_resilient():
        key = llm_module._env("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY غير مضبوط في البيئة")
        from openai import OpenAI
        return OpenAI(api_key=key, timeout=DRAFT_TRANSPORT_TIMEOUT_SECONDS, max_retries=2)

    llm_module._oa_client = _oa_client_resilient

    # Replace the OpenAI call itself, not Retrieval v2.  The previous adapter could
    # return an empty _Resp when Responses API ended as incomplete, which the UI
    # later rendered as a boolean-looking failure ("reason: true").  A dual-model
    # leg must either return usable text or raise a concrete provider error.
    def _oa_call_resilient(role, system, messages, max_tokens):
        if not llm_module._env("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY غير مضبوط في البيئة")
        model = llm_module._oa_model(role)
        payload = llm_module._oa_input(messages)
        last = None
        for attempt in range(1, OPENAI_DRAFT_ATTEMPTS + 1):
            try:
                cli = llm_module._oa_client()
                kwargs = {
                    "model": model,
                    "instructions": system,
                    "input": payload,
                    "max_output_tokens": max_tokens,
                }
                # GPT-5.6 supports explicit reasoning effort.  Low is deliberate
                # here: retrieval already supplies the legal authorities, and the
                # parallel drafting leg must finish reliably rather than spend its
                # output budget on hidden reasoning.
                if str(model).startswith("gpt-5.6"):
                    kwargs["reasoning"] = {"effort": "low"}
                # Long legal drafts run in Responses background mode so a transient
                # HTTP disconnect cannot destroy a valid generation.  We submit once,
                # then poll the response object by id until it reaches a terminal state.
                # Fast-role calls stay synchronous below because they are short.
                if role == "draft":
                    kwargs["background"] = True
                    r = cli.responses.create(**kwargs)
                    rid = getattr(r, "id", None)
                    started = time.monotonic()
                    while str(getattr(r, "status", "") or "") in ("queued", "in_progress"):
                        if time.monotonic() - started > OPENAI_BACKGROUND_MAX_SECONDS:
                            raise TimeoutError(
                                "انتهت مهلة انتظار GPT في الخلفية بعد %d ثانية" %
                                int(OPENAI_BACKGROUND_MAX_SECONDS)
                            )
                        if not rid:
                            raise RuntimeError("OpenAI background response بلا response id")
                        time.sleep(OPENAI_BACKGROUND_POLL_SECONDS)
                        r = cli.responses.retrieve(rid)
                else:
                    r = cli.responses.create(**kwargs)

                txt = getattr(r, "output_text", "") or ""
                status = str(getattr(r, "status", "") or "")
                if txt.strip():
                    u = getattr(r, "usage", None)
                    usage = llm_module._Usage(
                        getattr(u, "input_tokens", 0) or 0,
                        getattr(u, "output_tokens", 0) or 0,
                    )
                    return llm_module._Resp(txt, model, refusal=False, usage=usage)

                details = getattr(r, "incomplete_details", None)
                reason = getattr(details, "reason", None) if details is not None else None
                err = getattr(r, "error", None)
                err_msg = getattr(err, "message", None) if err is not None else None
                last = RuntimeError(
                    "OpenAI أعاد نتيجة بلا نص (status=%s, reason=%s%s)" %
                    (status or "unknown", reason or "unknown",
                     (", error=" + str(err_msg)) if err_msg else "")
                )
            except Exception as exc:
                last = exc

            if attempt < OPENAI_DRAFT_ATTEMPTS:
                time.sleep(2 * attempt)

        raise RuntimeError(
            "فشل مسار GPT بعد %d محاولات مستقلة: %s" %
            (OPENAI_DRAFT_ATTEMPTS, _error_text(last or RuntimeError("سبب غير معروف")))
        )

    llm_module._oa_call = _oa_call_resilient
    llm_module._legalmind_resilience_installed = True
