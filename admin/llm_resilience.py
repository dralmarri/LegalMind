# -*- coding: utf-8 -*-
"""Production resilience for long LegalMind drafting calls.

Keeps Retrieval v2 untouched.  The drafting pipeline legitimately sends a large,
source-grounded legal context and may need longer than the SDK's ordinary request
window.  Apply a per-provider 30 minute transport timeout without changing the
retrieved authority packet, model, prompt, or output-token budget.
"""

DRAFT_TRANSPORT_TIMEOUT_SECONDS = 1800.0


def install(llm_module):
    """Install transport-timeout hardening idempotently."""
    if getattr(llm_module, "_legalmind_resilience_installed", False):
        return

    original_stream_final = llm_module._stream_final

    def _stream_final_resilient(msgs_api, **kw):
        # Anthropic SDK accepts per-request timeout through the messages API.
        # This affects transport/read timeout only; it does not alter model work.
        kw.setdefault("timeout", DRAFT_TRANSPORT_TIMEOUT_SECONDS)
        return original_stream_final(msgs_api, **kw)

    llm_module._stream_final = _stream_final_resilient

    # OpenAI fallback must have an independent full transport window as well.
    # Otherwise a long first-provider attempt can be followed by a fallback that
    # dies under the SDK's default request timeout for the same large legal packet.
    def _oa_client_resilient():
        key = llm_module._env("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY غير مضبوط في البيئة")
        from openai import OpenAI
        return OpenAI(api_key=key, timeout=DRAFT_TRANSPORT_TIMEOUT_SECONDS, max_retries=2)

    llm_module._oa_client = _oa_client_resilient
    llm_module._legalmind_resilience_installed = True
