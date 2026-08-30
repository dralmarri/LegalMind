# -*- coding: utf-8 -*-
"""قارئ Claude الإنتاجي لمحرك الإدخال — بمنهجية الرفع اليدوي.
التفعيل: LEGALMIND_CLAUDE_INGEST=1 (في deploy/.env). أي عطل => تراجع تلقائي للمسار الكلاسيكي.
LEGALMIND_CLAUDE_DRYRUN=1 => معاينة كاملة دون أي كتابة أو نقل."""
import base64, hashlib, json, os, shutil, urllib.request
from datetime import datetime
from pathlib import Path

API = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("LEGALMIND_INGEST_MODEL", "claude-sonnet-5")
MIN_CONF = float(os.environ.get("LEGALMIND_CLAUDE_MIN_CONF", "0.8"))

def enabled(): return os.environ.get("LEGALMIND_CLAUDE_INGEST") == "1"
def dryrun(): return os.environ.get("LEGALMIND_CLAUDE_DRYRUN") == "1"

def _eng():
    import legalmind_engine as eng
    return eng

def _key():
    v = os.environ.get("ANTHROPIC_API_KEY")
    if v: return v
    for line in open("/opt/LegalMind/deploy/.env"):
        if line.startswith("ANTHROPIC_API_KEY="):
            return line.strip().split("=", 1)[1]
    raise RuntimeError("ANTHROPIC_API_KEY غير متاح")

SCHEMA = {"type": "object", "required": ["document_kind", "title", "branch", "topic", "reading_quality", "chunks"],
 "properties": {
  "document_kind": {"type": "string", "enum": ["legislation", "judicial_principles_collection", "full_judgment", "judicial_template", "legal_memorandum", "legal_document", "compound_document"]},
  "title": {"type": "string"}, "law_number": {"type": ["string", "null"]}, "law_year": {"type": ["string", "null"]},
  "branch": {"type": "string"}, "topic": {"type": "string"}, "subtopic": {"type": ["string", "null"]},
  "suggested_new": {"type": ["string", "null"]},
  "reading_quality": {"type": "string", "enum": ["clean", "degraded", "partial"]},
  "warnings": {"type": "array", "items": {"type": "string"}},
  "chunks": {"type": "array", "items": {"type": "object", "required": ["local_id", "kind", "title", "text", "confidence"],
    "properties": {"local_id": {"type": "string"}, "kind": {"type": "string"}, "number": {"type": ["string", "null"]},
      "title": {"type": "string"}, "text": {"type": "string"},
      "legislation_mentions": {"type": "array", "items": {"type": "object", "properties": {
        "law_number": {"type": ["string", "null"]}, "law_year": {"type": ["string", "null"]},
        "article_number": {"type": ["string", "null"]}}}},
      "confidence": {"type": "number"}, "notes": {"type": ["string", "null"]}}}}}}

SYSTEM = """أنت محرر قانوني كويتي خبير تفهرس مستندات لمكتبة قانونية محكمة التوثيق.
اقرأ المستند وهيكله كما يفعل محرر بشري دقيق. قواعد صارمة:
- النص يُنقل حرفياً كما ورد، لا تلخص ولا تعد الصياغة. عند القراءة من صورة صحح أخطاء المسح الواضحة فقط واخفض الثقة.
- قانون/مرسوم/لائحة: قطعه مواد كاملة. مجموعة مبادئ: مبدأ مبدأ بعناوين وصفية دقيقة (ممنوع "المبدأ 1"). حكم كامل: كائن واحد بعنوان دقيق (جهة الحكم، رقم الطعن/السنة، الموضوع).
- compound_document فقط إذا جمع الملف مستندات مستقلة مختلفة الأغراض لا يجمعها غرض واحد (كعدد جريدة يضم إعلانات وعقود شركات وقرارات متفرقة). التشريع الواحد ومعه مذكرته الإيضاحية أو ملاحقه = legislation واحد وليس مركباً. الحكم الواحد بمرفقاته = full_judgment واحد.
- استخرج كل إشارة تشريعية (رقم القانون، السنة، رقم المادة) في legislation_mentions.
- صنف حصراً على تصنيفات المكتبة المعطاة (branch ثم topic منها)؛ إن لم يطابق شيء ضع الأقرب واقترح الأدق في suggested_new.
- تجاهل العلامات المائية والأختام الدخيلة على النص القانوني واذكرها في warnings.
- confidence لكل قطعة من 0 إلى 1: أقل من 0.8 = تحتاج مراجعة بشرية مع السبب في notes."""

def _call(blocks, max_tokens=60000):
    body = {"model": MODEL, "max_tokens": max_tokens, "system": SYSTEM,
            "tools": [{"name": "save_structure", "description": "حفظ الهيكل المستخرج للمستند وفق التعليمات",
                       "input_schema": SCHEMA}],
            "tool_choice": {"type": "tool", "name": "save_structure"},
            "messages": [{"role": "user", "content": blocks}]}
    req = urllib.request.Request(API, data=json.dumps(body).encode(),
        headers={"content-type": "application/json", "x-api-key": _key(), "anthropic-version": "2023-06-01"})
    r = json.load(urllib.request.urlopen(req, timeout=600))
    if r.get("stop_reason") == "max_tokens":
        print("[claude_reader] تحذير: الرد بلغ سقف الطول", flush=True)
    for b in r.get("content", []):
        if b.get("type") == "tool_use":
            return b["input"]
    raise RuntimeError("لا tool_use في رد النموذج")

def _taxonomy(eng):
    with eng.psycopg.connect(eng.database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT branch, topic, count(*) FROM knowledge_objects
                           WHERE topic IS NOT NULL GROUP BY 1,2 ORDER BY 3 DESC LIMIT 120""")
            rows = cur.fetchall()
    tx = {}
    for b, t, _ in rows:
        tx.setdefault(b, []).append(t)
    return tx

def _header(tax, metadata):
    h = "تصنيفات المكتبة الحالية (branch: topics):\n" + json.dumps(tax, ensure_ascii=False)
    hints = {k: v for k, v in metadata.items() if k in ("source_type", "branch", "topic", "title", "classification_title") and v}
    if hints:
        h += "\n\nبيانات النموذج من الرافع (استرشادية وقد تكون خاطئة):\n" + json.dumps(hints, ensure_ascii=False)
    return h

def _split_pdf(path, max_pages=15):
    from pypdf import PdfReader, PdfWriter
    import io
    reader = PdfReader(str(path))
    n = len(reader.pages)
    if n <= max_pages and path.stat().st_size <= 25 * 1024 * 1024:
        return None
    out = []
    for s in range(0, n, max_pages):
        w = PdfWriter()
        for pg in reader.pages[s:s + max_pages]:
            w.add_page(pg)
        buf = io.BytesIO(); w.write(buf); out.append(buf.getvalue())
    return out

def _vision_call(data_bytes, prompt):
    return _call([{"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                    "data": base64.b64encode(data_bytes).decode()}},
                  {"type": "text", "text": prompt}])

def _merge_part(merged, r, k):
    ch = (r.get("chunks") or []) if isinstance(r, dict) else []
    for c in ch:
        c["local_id"] = "P%d-%s" % (k, c.get("local_id") or "X")
    if not ch:
        print("[claude_reader] تحذير: الجزء %d لم يرجع قطعا — تخطي" % k, flush=True)
    if merged is None:
        base = r if isinstance(r, dict) else {}
        base["chunks"] = ch
        base.setdefault("warnings", [])
        return base
    merged.setdefault("chunks", []).extend(ch)
    merged["warnings"] = (merged.get("warnings") or []) + ((r.get("warnings") or []) if isinstance(r, dict) else [])
    order = {"clean": 0, "degraded": 1, "partial": 2}
    rq = r.get("reading_quality") if isinstance(r, dict) else None
    if order.get(rq, 1) > order.get(merged.get("reading_quality"), 1):
        merged["reading_quality"] = rq
    return merged

def _split_text(text, max_chars=50000):
    if len(text) <= max_chars + 15000:
        return None
    parts, cur, size = [], [], 0
    for para in text.split("\n"):
        cur.append(para); size += len(para) + 1
        if size >= max_chars:
            parts.append("\n".join(cur)); cur, size = [], 0
    if cur:
        parts.append("\n".join(cur))
    return parts

def _ctx_of(merged, k, n):
    if not (merged and merged.get("chunks")):
        return ""
    tails = [c.get("title", "") for c in merged["chunks"][-3:]]
    return ("\n\nهذا الجزء %d من %d من المستند نفسه. آخر قطع الجزء السابق: %s. "
            "تابع السياق والترقيم من حيث انتهى ولا تكرر ما سبق.") % (k, n, " | ".join(tails))

def _structure(path, text, tax, metadata, progress=None):
    header = _header(tax, metadata)
    used = "text"
    result = None
    if metadata and metadata.get("force_vision"):
        text = None
    if text:
        parts = _split_text(text)
        if parts:
            n = len(parts); merged = None
            for k, seg in enumerate(parts, 1):
                if progress:
                    progress("قراءة الجزء %d من %d (نص)" % (k, n), 25 + int(45 * k / n))
                r = _call([{"type": "text", "text": header + _ctx_of(merged, k, n)
                            + "\n\nالمستند (جزء %d من %d):\n" % (k, n) + seg + "\n\nهيكل هذا الجزء."}])
                merged = _merge_part(merged, r, k)
            result = merged
            confs = [float(c.get("confidence", 0)) for c in (result.get("chunks") or [])] or [0]
            avg = sum(confs) / len(confs)
            if path.suffix.lower() == ".pdf" and (result.get("reading_quality") == "partial" or avg < 0.65):
                print("[claude_reader] النص المقسم رديء (متوسط الثقة %.2f) — إعادة القراءة بالرؤية" % avg, flush=True)
                text = None
        else:
            result = _call([{"type": "text", "text": header + "\n\nالمستند:\n" + text + "\n\nهيكل المستند أعلاه."}])
            confs = [float(c.get("confidence", 0)) for c in result.get("chunks", [])] or [0]
            if path.suffix.lower() == ".pdf" and (result.get("reading_quality") == "partial" or max(confs) < 0.65):
                text = None
    if text is None:
        used = "vision"
        raw = path.read_bytes()
        batches = _split_pdf(path) if path.suffix.lower() == ".pdf" else None
        if not batches:
            result = _vision_call(raw, header + "\n\nاقرأ المستند المرفق قراءة بصرية وهيكله.")
        else:
            n = len(batches); merged = None
            for k, part in enumerate(batches, 1):
                if progress:
                    progress("قراءة الدفعة %d من %d (رؤية)" % (k, n), 25 + int(45 * k / n))
                r = _vision_call(part, header + _ctx_of(merged, k, n) + "\n\nاقرأ هذا الجزء قراءة بصرية وهيكله.")
                merged = _merge_part(merged, r, k)
            result = merged
    result["_read_via"] = used
    return result

def _progress(eng, batch_id, patch):
    if dryrun(): return
    try:
        with eng.psycopg.connect(eng.database_url()) as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE ingestion_batches SET report = coalesce(report,'{}'::jsonb) || %s WHERE batch_id=%s",
                            (eng.Jsonb(patch), batch_id))
            conn.commit()
    except Exception as exc:
        print("[claude_reader] progress:", exc, flush=True)

def ingest(path, archive_root, failed_root):
    eng = _eng()
    metadata = eng.load_metadata(path)
    canonical = None; text = None
    try:
        canonical = eng.normalize(path)
        text = canonical.body
    except Exception as exc:
        if path.suffix.lower() != ".pdf":
            raise RuntimeError(f"التطبيع فشل والملف ليس PDF: {exc}")
        print(f"[claude_reader] التطبيع فشل — سيُقرأ بالرؤية: {exc}", flush=True)
    raw_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    digest = canonical.source_sha256 if canonical else raw_sha
    content_sha = eng.content_digest(text) if text else raw_sha
    batch_id = f"BATCH-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{content_sha[:8].upper()}"
    started = eng.now_iso()

    if not dryrun():
        with eng.psycopg.connect(eng.database_url()) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT source_key FROM sources WHERE content_sha256=%s LIMIT 1", (content_sha,))
                dup = cur.fetchone()
                if dup:
                    cur.execute("""INSERT INTO ingestion_batches(batch_id, source_key, status, report, completed_at)
                                   VALUES (%s,%s,'duplicate',%s,now()) ON CONFLICT (batch_id) DO NOTHING""",
                                (batch_id, dup[0], eng.Jsonb({"file": path.name, "content_sha256": content_sha,
                                                              "duplicate_of": {"source_key": dup[0]}, "percent": 100})))
            conn.commit()
        if dup:
            archive_root.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), archive_root / f"{batch_id}__DUPLICATE__{path.name}")
            sc = path.with_suffix(path.suffix + ".json")
            if sc.exists(): shutil.move(str(sc), archive_root / f"{batch_id}__DUPLICATE__{sc.name}")
            return {"batch_id": batch_id, "status": "duplicate", "content_sha256": content_sha}
        with eng.psycopg.connect(eng.database_url()) as conn:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO ingestion_batches(batch_id, status, report)
                               VALUES (%s,'started',%s) ON CONFLICT (batch_id) DO NOTHING""",
                            (batch_id, eng.Jsonb({"file": path.name, "started_at": started,
                                                  "stage": "قراءة كلود وهيكلة المستند", "percent": 25, "content_sha256": content_sha})))
            conn.commit()
    try:
        tax = _taxonomy(eng)
        result = _structure(path, text, tax, metadata, progress=lambda s, pc: _progress(eng, batch_id, {"stage": s, "percent": pc}))
        chunks = result.get("chunks", [])
        if not chunks:
            raise RuntimeError("القارئ لم يستخرج أي قطع")

        if result.get("document_kind") == "compound_document":
            if dryrun():
                return {"status": "needs_selection (معاينة)", "title": result.get("title"), "chunks": len(chunks)}
            _progress(eng, batch_id, {"stage": "مستند مركب — بانتظار اختيارك", "percent": 60, "structure": result})
            with eng.psycopg.connect(eng.database_url()) as conn:
                with conn.cursor() as cur:
                    cur.execute("UPDATE ingestion_batches SET status='needs_selection' WHERE batch_id=%s", (batch_id,))
                conn.commit()
            sel = archive_root / "needs-selection"; sel.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), sel / f"{batch_id}__{path.name}")
            sc = path.with_suffix(path.suffix + ".json")
            if sc.exists(): shutil.move(str(sc), sel / f"{batch_id}__{sc.name}")
            return {"batch_id": batch_id, "status": "needs_selection", "object_count": 0,
                    "title": result.get("title"), "message": "مستند مركب — حدد الأجزاء المطلوب فهرستها من اللوحة"}

        object_type = result.get("document_kind", "legal_document")
        branch = result.get("branch") or metadata.get("branch", "أحوال شخصية")
        topic = result.get("topic") or metadata.get("topic")
        subtopic = result.get("subtopic") or metadata.get("subtopic") or metadata.get("classification_title")
        title = result.get("title") or metadata.get("title", path.stem)
        base_status = metadata.get("verification_status") or "source_verified"
        if base_status not in eng.VERIFICATION_STATUSES:
            base_status = "source_verified"
        source_key = metadata.get("source_key", f"SRC-{content_sha[:20].upper()}")
        law_id = metadata.get("law_id", eng.slug(result.get("law_number") or path.stem))
        prefix_map = {"legislation": f"LEG-{law_id}",
                      "judicial_principle": f"JUR-{eng.slug(branch)}-{eng.slug(topic or title)}",
                      "judicial_principles_collection": f"JUR-{eng.slug(branch)}-{eng.slug(topic or title)}",
                      "full_judgment": f"JUD-{eng.slug(branch)}-{eng.slug(topic or title)}",
                      "judicial_template": f"TPL-{eng.slug(branch)}-{eng.slug(topic or title)}",
                      "legal_memorandum": f"MEMO-{eng.slug(branch)}-{eng.slug(topic or title)}"}
        prefix = metadata.get("id_prefix", prefix_map.get(object_type, f"OBJ-{eng.slug(branch)}-{eng.slug(topic or title)}"))
        db_type = "judicial_principle" if object_type == "judicial_principles_collection" else object_type

        if dryrun():
            low = sum(1 for c in chunks if float(c.get("confidence", 0)) < MIN_CONF)
            return {"status": "معاينة — لا كتابة", "object_type": object_type, "title": title,
                    "branch": branch, "topic": topic, "chunks": len(chunks), "needs_review": low,
                    "read_via": result.get("_read_via"), "quality": result.get("reading_quality"),
                    "suggested_new": result.get("suggested_new")}

        _progress(eng, batch_id, {"stage": "كتابة الكائنات المعرفية", "percent": 75})
        eng.ensure_collection()
        inserted, embed_rows = [], []
        with eng.psycopg.connect(eng.database_url()) as conn:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO sources(source_key, source_type, title, file_name, sha256, content_sha256,
                                                   branch, topic, first_batch_id, verification_status, metadata)
                               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                               ON CONFLICT (source_key) DO UPDATE SET title=EXCLUDED.title, file_name=EXCLUDED.file_name,
                               sha256=EXCLUDED.sha256, metadata=EXCLUDED.metadata, updated_at=now()""",
                            (source_key, db_type, title, path.name, digest, content_sha, branch, topic, batch_id,
                             base_status, eng.Jsonb({**metadata, "claude_reader": True, "claude_model": MODEL,
                                                     "read_via": result.get("_read_via"),
                                                     "reading_quality": result.get("reading_quality"),
                                                     "claude_warnings": result.get("warnings"),
                                                     "suggested_new": result.get("suggested_new")})))
                for ch in chunks:
                    conf = float(ch.get("confidence", 0))
                    vs = base_status if conf >= MIN_CONF else "machine_pending_human"
                    auth, citable = eng.authority_for(db_type, vs)
                    chash = hashlib.sha256(eng.normalize_text(ch["text"]).encode("utf-8")).hexdigest()[:16]
                    oid = f"{prefix}-{ch['local_id']}-{chash}"
                    md = {**metadata, "batch_id": batch_id, "sha256": digest, "content_sha256": content_sha,
                          "confidence": conf, "claude_notes": ch.get("notes"),
                          "legislation_mentions": ch.get("legislation_mentions"),
                          "chunk_kind": ch.get("kind"), "number": ch.get("number")}
                    cur.execute("""INSERT INTO knowledge_objects(id,object_type,branch,topic,subtopic,micro_issue,title,
                                     original_text,normalized_text,source_key,verification_status,authority_status,
                                     usable_as_citation,metadata)
                                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                                   ON CONFLICT (id) DO UPDATE SET original_text=EXCLUDED.original_text,
                                   normalized_text=EXCLUDED.normalized_text, source_key=EXCLUDED.source_key,
                                   metadata=EXCLUDED.metadata, updated_at=now()""",
                                (oid, db_type, branch, topic, subtopic, metadata.get("micro_issue"), ch["title"],
                                 ch["text"], eng.normalize_text(ch["text"]), source_key, vs, auth, citable, eng.Jsonb(md)))
                    inserted.append(oid); embed_rows.append((oid, ch["title"], ch["text"]))
                cur.execute("""UPDATE ingestion_batches SET status='completed', object_count=%s, report=report||%s,
                               completed_at=now() WHERE batch_id=%s""",
                            (len(inserted), eng.Jsonb({"stage": "اكتمل", "percent": 100, "objects": inserted,
                                                       "needs_review": sum(1 for c in chunks if float(c.get("confidence", 0)) < MIN_CONF),
                                                       "content_sha256": content_sha, "claude_reader": True}), batch_id))
            conn.commit()
        _progress(eng, batch_id, {"stage": "الفهرسة الدلالية", "percent": 90})
        if embed_rows:
            points = eng.build_points(embed_rows, {"object_type": db_type, "branch": branch, "topic": topic,
                                                   "subtopic": subtopic, "micro_issue": metadata.get("micro_issue"),
                                                   "source_key": source_key})
            eng.qdrant_request("PUT", f"/collections/{eng.COLLECTION}/points?wait=true", {"points": points})
        _progress(eng, batch_id, {"stage": "اكتمل", "percent": 100})
        archive_root.mkdir(parents=True, exist_ok=True)
        if canonical:
            (archive_root / f"{batch_id}__{path.stem}.canonical.md").write_text(canonical.to_markdown(), encoding="utf-8")
        shutil.move(str(path), archive_root / f"{batch_id}__{path.name}")
        sc = path.with_suffix(path.suffix + ".json")
        if sc.exists(): shutil.move(str(sc), archive_root / f"{batch_id}__{sc.name}")
        return {"batch_id": batch_id, "source_key": source_key, "status": "completed", "object_type": db_type,
                "object_count": len(inserted), "objects": inserted, "claude_reader": True}
    except Exception as exc:
        if not dryrun():
            try:
                with eng.psycopg.connect(eng.database_url()) as conn:
                    with conn.cursor() as cur:
                        cur.execute("""UPDATE ingestion_batches SET status='failed', report=report||%s, completed_at=now()
                                       WHERE batch_id=%s AND status NOT IN ('completed','needs_selection')""",
                                    (eng.Jsonb({"error": str(exc)}), batch_id))
                    conn.commit()
            except Exception:
                pass
        raise


def materialize_selection(batch_id, indices=None):
    """يثبت الأجزاء المختارة من دفعة needs_selection في المكتبة والفهرس."""
    eng = _eng()
    with eng.psycopg.connect(eng.database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT report FROM ingestion_batches WHERE batch_id=%s AND status='needs_selection'", (batch_id,))
            row = cur.fetchone()
    if not row:
        return {"ok": False, "error": "الدفعة غير موجودة أو ليست بانتظار الاختيار"}
    report = row[0] or {}
    st = report.get("structure") or {}
    chunks = st.get("chunks") or []
    chosen = list(enumerate(chunks)) if indices is None else [(i, chunks[i]) for i in indices if 0 <= i < len(chunks)]
    if not chosen:
        return {"ok": False, "error": "لا قطع مختارة"}
    branch = st.get("branch") or "أحوال شخصية"
    topic = st.get("topic"); subtopic = st.get("subtopic")
    title = st.get("title") or report.get("file") or batch_id
    content_sha = report.get("content_sha256") or hashlib.sha256(json.dumps(st, ensure_ascii=False).encode()).hexdigest()
    source_key = "SRC-" + content_sha[:20].upper()
    kind_map = {"principle": "judicial_principle", "judgment": "full_judgment"}
    inserted, embed_rows = [], []
    eng.ensure_collection()
    with eng.psycopg.connect(eng.database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO sources(source_key, source_type, title, file_name, sha256, content_sha256,
                               branch, topic, first_batch_id, verification_status, metadata)
                           VALUES (%s,'legal_document',%s,%s,%s,%s,%s,%s,%s,'source_verified',%s)
                           ON CONFLICT (source_key) DO UPDATE SET title=EXCLUDED.title, metadata=EXCLUDED.metadata, updated_at=now()""",
                        (source_key, title, report.get("file"), content_sha, content_sha, branch, topic, batch_id,
                         eng.Jsonb({"claude_reader": True, "compound_selection": True, "batch_id": batch_id})))
            for i, ch in chosen:
                conf = float(ch.get("confidence", 0))
                db_type = kind_map.get((ch.get("kind") or "").lower(), "legal_document")
                vs = "source_verified" if conf >= MIN_CONF else "machine_pending_human"
                auth, citable = eng.authority_for(db_type, vs)
                chash = hashlib.sha256(eng.normalize_text(ch["text"]).encode("utf-8")).hexdigest()[:16]
                oid = "SEL-" + eng.slug(branch) + "-" + batch_id[-8:] + "-" + str(ch.get("local_id") or i) + "-" + chash
                md = {"batch_id": batch_id, "confidence": conf, "claude_notes": ch.get("notes"),
                      "legislation_mentions": ch.get("legislation_mentions"),
                      "chunk_kind": ch.get("kind"), "compound_selection_index": i}
                cur.execute("""INSERT INTO knowledge_objects(id,object_type,branch,topic,subtopic,micro_issue,title,
                                 original_text,normalized_text,source_key,verification_status,authority_status,
                                 usable_as_citation,metadata)
                               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                               ON CONFLICT (id) DO UPDATE SET metadata=EXCLUDED.metadata, updated_at=now()""",
                            (oid, db_type, branch, topic, subtopic, None, ch["title"], ch["text"],
                             eng.normalize_text(ch["text"]), source_key, vs, auth, citable, eng.Jsonb(md)))
                inserted.append(oid); embed_rows.append((oid, ch["title"], ch["text"]))
            cur.execute("""UPDATE ingestion_batches SET status='completed', object_count=%s, completed_at=now(),
                           report = report || %s WHERE batch_id=%s""",
                        (len(inserted), eng.Jsonb({"stage": "ثُبت المختار", "percent": 100,
                                                   "objects": inserted, "selected": [i for i, _ in chosen]}), batch_id))
        conn.commit()
    if embed_rows:
        points = eng.build_points(embed_rows, {"object_type": "legal_document", "branch": branch, "topic": topic,
                                               "subtopic": subtopic, "micro_issue": None, "source_key": source_key})
        eng.qdrant_request("PUT", "/collections/" + eng.COLLECTION + "/points?wait=true", {"points": points})
    return {"ok": True, "batch_id": batch_id, "object_count": len(inserted), "objects": inserted}
