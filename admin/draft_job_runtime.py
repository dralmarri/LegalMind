# -*- coding: utf-8 -*-
"""Durable orchestration for LegalMind draft calls.

The browser no longer holds one long HTTP request open while Claude/GPT draft.
A short POST creates a server-side job, a daemon worker runs the existing
_draft_run unchanged, and short polling requests collect the persisted result.
The injected fetch adapter is deliberately transparent to the existing UI: code
that POSTs /api/draft still receives an ordinary JSON Response when the job ends.
"""
from __future__ import annotations

import json
import threading
import time
import uuid

from fastapi import Depends, HTTPException
from fastapi.responses import JSONResponse, Response

POLL_SECONDS = 2.0
MAX_WAIT_SECONDS = 1800


def install(app_module):
    if getattr(app_module, "_durable_draft_jobs_installed", False):
        return

    app = app_module.app
    require_auth = app_module.require_auth

    def _db_init():
        import psycopg
        dsn = app_module._draft_env("DATABASE_URL")
        with psycopg.connect(dsn) as c, c.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS draft_jobs (
                    job_id text PRIMARY KEY,
                    created_at timestamptz NOT NULL DEFAULT now(),
                    updated_at timestamptz NOT NULL DEFAULT now(),
                    status text NOT NULL,
                    result jsonb,
                    error text
                )
            """)
            cur.execute("DELETE FROM draft_jobs WHERE created_at < now() - interval '2 days'")
            c.commit()

    def _job_write(job_id, status, result=None, error=None):
        import psycopg
        from psycopg.types.json import Jsonb
        dsn = app_module._draft_env("DATABASE_URL")
        with psycopg.connect(dsn) as c, c.cursor() as cur:
            cur.execute(
                "UPDATE draft_jobs SET status=%s, result=%s, error=%s, updated_at=now() WHERE job_id=%s",
                (status, Jsonb(result) if result is not None else None, error, job_id),
            )
            c.commit()

    def _worker(job_id, inp):
        try:
            res = app_module._draft_run(inp)
            if not isinstance(res, dict):
                res = {"answer": str(res or "")}
            _job_write(job_id, "completed", result=res)
            # Preserve the older client_rid recovery channel as a second copy.
            try:
                app_module._store_draft_result(getattr(inp, "client_rid", None), res)
            except Exception:
                pass
            print("[draft-job] completed", job_id[:12], flush=True)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            msg = "%s: %s" % (type(exc).__name__, str(exc)[:1000])
            try:
                _job_write(job_id, "failed", error=msg)
            finally:
                print("[draft-job] failed", job_id[:12], msg[:200], flush=True)

    _db_init()

    @app.post("/api/draft/job")
    def durable_draft_start(body: dict, _: str = Depends(require_auth)):
        try:
            inp = app_module._DraftIn(**body)
        except Exception as exc:
            raise HTTPException(422, "بيانات طلب الصياغة غير صالحة: %s" % str(exc)[:300]) from exc
        job_id = uuid.uuid4().hex
        import psycopg
        dsn = app_module._draft_env("DATABASE_URL")
        with psycopg.connect(dsn) as c, c.cursor() as cur:
            cur.execute("INSERT INTO draft_jobs(job_id,status) VALUES(%s,'running')", (job_id,))
            c.commit()
        threading.Thread(target=_worker, args=(job_id, inp), daemon=True,
                         name="draft-job-" + job_id[:8]).start()
        return {"job_id": job_id, "status": "running"}

    @app.get("/api/draft/job/{job_id}")
    def durable_draft_status(job_id: str, _: str = Depends(require_auth)):
        import psycopg
        dsn = app_module._draft_env("DATABASE_URL")
        with psycopg.connect(dsn) as c, c.cursor() as cur:
            cur.execute("SELECT status,result,error FROM draft_jobs WHERE job_id=%s", (job_id[:64],))
            row = cur.fetchone()
        if not row:
            raise HTTPException(404, "مهمة الصياغة غير موجودة")
        status, result, error = row
        return {"job_id": job_id, "status": status, "result": result, "error": error}

    # Transparent browser adapter.  Existing UI code continues to call /api/draft;
    # this adapter converts that long request into start + short polling requests.
    script = r'''<script id="legalmind-durable-draft-jobs">
(function(){
  if (window.__LM_DURABLE_DRAFT__) return;
  window.__LM_DURABLE_DRAFT__ = true;
  const nativeFetch = window.fetch.bind(window);
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  window.fetch = async function(input, init){
    const u = (typeof input === 'string') ? input : ((input && input.url) || '');
    const method = String((init && init.method) || (input && input.method) || 'GET').toUpperCase();
    if (!/\/api\/draft(?:\?.*)?$/.test(u) || method !== 'POST') return nativeFetch(input, init);
    let raw = init && init.body;
    if (raw == null && input && typeof input.clone === 'function') raw = await input.clone().text();
    let body;
    try { body = typeof raw === 'string' ? JSON.parse(raw) : raw; }
    catch(e) { return nativeFetch(input, init); }
    const headers = Object.assign({}, (init && init.headers) || {}, {'Content-Type':'application/json'});
    const start = await nativeFetch('/api/draft/job', {method:'POST', headers, credentials:'same-origin', body:JSON.stringify(body)});
    if (!start.ok) return start;
    const sj = await start.json();
    const deadline = Date.now() + 1800000;
    while (Date.now() < deadline) {
      await sleep(2000);
      const p = await nativeFetch('/api/draft/job/' + encodeURIComponent(sj.job_id), {credentials:'same-origin', cache:'no-store'});
      if (!p.ok) continue;
      const j = await p.json();
      if (j.status === 'completed') {
        return new Response(JSON.stringify(j.result || {}), {status:200, headers:{'Content-Type':'application/json'}});
      }
      if (j.status === 'failed') {
        const out = {answer:'تعذر إتمام الصياغة: ' + (j.error || 'خطأ غير معروف'), error:j.error || true, error_type:'draft_job'};
        return new Response(JSON.stringify(out), {status:200, headers:{'Content-Type':'application/json'}});
      }
    }
    const out = {answer:'استمرت مهمة الصياغة أكثر من المهلة المسموحة.', error:'draft_job_timeout', error_type:'timeout'};
    return new Response(JSON.stringify(out), {status:200, headers:{'Content-Type':'application/json'}});
  };
})();
</script>'''

    @app.middleware("http")
    async def _inject_durable_draft_adapter(request, call_next):
        response = await call_next(request)
        ctype = (response.headers.get("content-type") or "").lower()
        if "text/html" not in ctype or request.method != "GET":
            return response
        # Consume HTML responses only; JSON/streaming draft responses are untouched.
        try:
            chunks = []
            async for chunk in response.body_iterator:
                chunks.append(chunk)
            body = b"".join(chunks)
            text = body.decode("utf-8")
            if "legalmind-durable-draft-jobs" not in text:
                text = text.replace("</body>", script + "</body>", 1) if "</body>" in text else text + script
            headers = dict(response.headers)
            headers.pop("content-length", None)
            return Response(content=text, status_code=response.status_code,
                            headers=headers, media_type="text/html")
        except Exception as exc:
            print("[draft-job] html injection skipped:", repr(exc), flush=True)
            return response

    app_module._durable_draft_jobs_installed = True
