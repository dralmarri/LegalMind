#!/bin/bash
# أمر آلي 3: تحويل المراجعة إلى خدمة دائمة ذكية (تحديد الموقع ثم التدقيق) تعمل كل 20 دقيقة
set -e
pkill -f "python /root/deep_review.py" 2>/dev/null || true
rm -f /root/.autorun-deep-lock /root/.autorun-supervisor-lock
mkdir -p /opt/LegalMind/tools

cat > /opt/LegalMind/tools/reviewer.py <<'PYEOF'
# -*- coding: utf-8 -*-
"""خدمة المراجعة الذاتية: تحدد موقع كل نص معلق في مصدره ثم تدققه وتعتمده وتفهرسه."""
import sys, os, re, io, json, glob, time, base64, urllib.request, urllib.error
from collections import defaultdict
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng
from pypdf import PdfReader, PdfWriter

MODEL = os.environ.get("LEGALMIND_INGEST_MODEL", "claude-sonnet-5")
KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MIN_CONF, DEFAULT_CONF = 0.75, 0.85
MAX_PER_RUN = 130          # سقف كل جولة حتى تبقى الجولات قصيرة ومتكررة
GROUP = 4                  # نصوص لكل نداء
MAX_ATTEMPTS = 3           # محاولات لكل نص عبر الجولات
WIN_BEFORE, WIN_AFTER = 2, 4

TOOL = {
    "name": "save_verdicts",
    "description": "حفظ نتائج مراجعة نصوص مقابل المصدر",
    "input_schema": {
        "type": "object", "required": ["verdicts"],
        "properties": {"verdicts": {"type": "array", "items": {
            "type": "object", "required": ["id", "status", "confidence"],
            "properties": {
                "id": {"type": "string"},
                "status": {"type": "string", "enum": ["correct", "corrected", "not_found"]},
                "corrected_text": {"type": "string"},
                "confidence": {"type": "number"},
                "note": {"type": "string"}}}}}}}

PROMPT = ("أنت مدقق نصوص قانونية دقيق. راجع كل نص مما يلي حرفياً مقابل المصدر المرفق:\n"
          "- طابق المصدرَ حرفياً (بتسامح في التشكيل وفواصل الأسطر والترقيم) → correct.\n"
          "- اختلف أو نقص أو زاد → انسخ النص الصحيح كاملاً من المصدر في corrected_text → corrected.\n"
          "- غير موجود في المصدر المرفق → not_found.\n"
          "أعطِ confidence رقمية (0-1) لكل حكم — إلزامي.\n"
          "لا تخمن ولا تكمل من معرفتك؛ انسخ ما تراه في المصدر فقط.\n\n")

_TR = str.maketrans("أإآىة", "اااية")

def nz(t):
    return (t or "").translate(_TR)

def api(blocks, items, max_tokens=20000):
    """يرجع (أحكام, نوع_الخطأ). نوع الخطأ 'too_long' يعني قلّص الطلب."""
    listing = "\n\n".join("### %s\nالعنوان: %s\nالنص المخزن:\n%s" % (i["id"], i["title"], i["text"][:5000])
                          for i in items)
    body = {"model": MODEL, "max_tokens": max_tokens,
            "tools": [TOOL], "tool_choice": {"type": "tool", "name": "save_verdicts"},
            "messages": [{"role": "user", "content": blocks + [{"type": "text", "text": PROMPT + listing}]}]}
    data = json.dumps(body).encode("utf-8")
    for attempt in range(3):
        try:
            req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=data,
                                         headers={"x-api-key": KEY, "anthropic-version": "2023-06-01",
                                                  "content-type": "application/json"})
            with urllib.request.urlopen(req, timeout=900) as r:
                res = json.loads(r.read())
            out = []
            for blk in res.get("content", []):
                if blk.get("type") == "tool_use":
                    for v in (blk["input"].get("verdicts") or []):
                        if isinstance(v, dict):
                            out.append(v)
            return out, None
        except urllib.error.HTTPError as e:
            msg = ""
            try:
                msg = e.read().decode("utf-8", "replace")[:200]
            except Exception:
                pass
            print("    HTTP %s: %s" % (e.code, msg), flush=True)
            if e.code == 400:
                return [], "too_long"
            time.sleep(20 * (attempt + 1))
        except Exception as exc:
            print("    محاولة %d: %s" % (attempt + 1, str(exc)[:110]), flush=True)
            time.sleep(20 * (attempt + 1))
    return [], "failed"

def pdf_b64(rd, a, b):
    w = PdfWriter()
    for p in range(max(0, a), min(b, len(rd.pages))):
        w.add_page(rd.pages[p])
    buf = io.BytesIO(); w.write(buf)
    return base64.b64encode(buf.getvalue()).decode("ascii")

def probes(text, title):
    out = []
    t = nz(re.sub(r"\s+", " ", text or "")).strip()
    for start, ln in ((8, 60), (0, 40), (30, 40)):
        if len(t) >= start + ln:
            out.append(t[start:start + ln])
    ti = nz(re.sub(r"\s+", " ", title or "")).strip()
    if len(ti) >= 18:
        out.append(ti[:40])
    return out

def art_no(title):
    m = re.search(r"(?:الماده|ماده|المادة|مادة|البند)\s*\(?\s*(\d+)", nz(title or ""))
    return m.group(1) if m else None

def locate_page(page_norm, text, title):
    """يرجع رقم أفضل صفحة أو -1"""
    for pr in probes(text, title):
        for i, pg in enumerate(page_norm):
            if pr and pr in pg:
                return i
    n = art_no(title)
    if n:
        pats = ["ماده %s" % n, "ماده (%s)" % n, "ماده(%s)" % n, "( %s )" % n]
        best, bs = -1, 0
        words = {w for w in nz(re.sub(r"\s+", " ", (text or "")[:400])).split() if len(w) > 3}
        for i, pg in enumerate(page_norm):
            s = sum(3 for p in pats if p in pg)
            if s:
                s += sum(1 for w in words if w in pg)
                if s > bs:
                    best, bs = i, s
        if best >= 0:
            return best
    return -1

def part_of(oid):
    m = re.search(r"-P(\d+)-", oid)
    return int(m.group(1)) if m else None

stats = {"ok": 0, "fix": 0, "nf": 0, "silent": 0, "skipped": 0}
started = time.time()

with eng.psycopg.connect(eng.database_url()) as conn:
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("""SELECT authority_status FROM knowledge_objects
                   WHERE verification_status='source_verified' AND authority_status IS NOT NULL LIMIT 1""")
    r = cur.fetchone(); AUTH = r[0] if r else None

    def bump(oid, note=""):
        cur.execute("""UPDATE knowledge_objects
                       SET metadata = metadata || jsonb_build_object(
                             'review_attempts', (coalesce(metadata->>'review_attempts','0')::int + 1),
                             'review_last_note', %s)
                       WHERE id=%s""", (note[:200], oid))

    def apply(vd, by_id, unresolved):
        oid = vd.get("id"); row = by_id.pop(oid, None)
        if row is None:
            return
        st = vd.get("status")
        try:
            cf = float(vd.get("confidence"))
        except Exception:
            cf = DEFAULT_CONF
        if cf <= 0:
            cf = DEFAULT_CONF
        if st == "not_found" or cf < MIN_CONF:
            unresolved.append(row); bump(oid, "%s conf=%.2f" % (st, cf)); stats["nf"] += 1; return
        patch = {"deep_review": st, "deep_conf": cf, "deep_note": (vd.get("note") or "")[:300]}
        txt = (vd.get("corrected_text") or "").strip() if st == "corrected" else ""
        if txt:
            cur.execute("""UPDATE knowledge_objects SET original_text=%s, normalized_text=%s,
                           verification_status='source_verified', usable_as_citation=true,
                           authority_status=coalesce(%s, authority_status),
                           metadata = metadata || %s::jsonb, updated_at=now() WHERE id=%s""",
                        (txt, eng.normalize_text(txt), AUTH, json.dumps(patch), oid))
            common = {"object_type": row[3], "branch": row[4], "topic": row[5],
                      "subtopic": row[6], "micro_issue": row[7], "source_key": row[8]}
            eng.qdrant_request("PUT", "/collections/" + eng.COLLECTION + "/points?wait=true",
                               {"points": eng.build_points([(oid, row[1], txt)], common)})
            stats["fix"] += 1
        else:
            cur.execute("""UPDATE knowledge_objects SET verification_status='source_verified',
                           usable_as_citation=true, authority_status=coalesce(%s, authority_status),
                           metadata = metadata || %s::jsonb, updated_at=now() WHERE id=%s""",
                        (AUTH, json.dumps(patch), oid))
            stats["ok"] += 1

    def run_group(blocks, rows, shrink=None):
        """ينفذ نداءً لمجموعة، ويقلّص عند الحاجة، ويحتسب من لم يصله حكم."""
        by_id = {r[0]: r for r in rows}
        items = [{"id": r[0], "title": r[1], "text": r[2]} for r in rows]
        vds, err = api(blocks, items)
        if err == "too_long" and shrink:
            nb = shrink()
            if nb is not None:
                vds, err = api(nb, items)
        unresolved = []
        for vd in vds:
            apply(vd, by_id, unresolved)
        for oid, row in by_id.items():          # لم يصله حكم — يُحتسب ولا يُهمل
            stats["silent"] += 1
            bump(oid, "no_verdict:%s" % (err or "partial"))
        return unresolved

    cur.execute("""SELECT metadata->>'batch_id', count(*) FROM knowledge_objects
                   WHERE verification_status='machine_pending_human'
                     AND coalesce(metadata->>'human_edited','') <> 'true'
                     AND coalesce(metadata->>'review_attempts','0')::int < %s
                     AND metadata->>'batch_id' IS NOT NULL
                   GROUP BY 1 ORDER BY 2 DESC""", (MAX_ATTEMPTS,))
    batches = cur.fetchall()
    budget = MAX_PER_RUN
    print("جولة: دفعات=%d | معلق قابل للمعالجة=%d | سقف الجولة=%d" %
          (len(batches), sum(b[1] for b in batches), MAX_PER_RUN), flush=True)

    for BID, _n in batches:
        if budget <= 0:
            break
        try:
            cur.execute("""SELECT id, coalesce(title,''), coalesce(original_text,''),
                                  object_type, branch, topic, subtopic, metadata->>'micro_issue', source_key
                           FROM knowledge_objects
                           WHERE metadata->>'batch_id'=%s AND verification_status='machine_pending_human'
                             AND coalesce(metadata->>'human_edited','') <> 'true'
                             AND coalesce(metadata->>'review_attempts','0')::int < %s
                           LIMIT %s""", (BID, MAX_ATTEMPTS, budget))
            pend = cur.fetchall()
            if not pend:
                continue
            files = [f for f in glob.glob("/opt/legalmind-ingest/archive/%s__*" % BID)
                     if not f.endswith(".json") and not f.endswith(".canonical.md")]
            if not files:
                cur.execute("SELECT file_name FROM sources WHERE source_key=%s LIMIT 1", (pend[0][8],))
                fr = cur.fetchone()
                if fr:
                    files = [f for f in glob.glob("/opt/legalmind-ingest/archive/*__" + fr[0])
                             if not f.endswith(".json") and not f.endswith(".canonical.md")]
            if not files:
                for r0 in pend:
                    bump(r0[0], "no_source_file"); stats["skipped"] += 1
                print("== %s: لا ملف مصدر (%d عنصر) ==" % (BID, len(pend)), flush=True)
                continue
            src = files[0]
            print("== %s: %d عنصر | %s ==" % (BID, len(pend), os.path.basename(src)[:50]), flush=True)
            budget -= len(pend)

            if src.lower().endswith(".pdf"):
                rd = PdfReader(src); npg = len(rd.pages)
                pnorm = []
                for pg in rd.pages:
                    try:
                        pnorm.append(nz(re.sub(r"\s+", " ", pg.extract_text() or "")))
                    except Exception:
                        pnorm.append("")
                layered = sum(len(x) for x in pnorm) > 800
                windows = defaultdict(list)
                for row in pend:
                    pi = locate_page(pnorm, row[2], row[1]) if layered else -1
                    if pi < 0:
                        prt = part_of(row[0]) or 1
                        a, b = (prt - 1) * 15, prt * 15
                    else:
                        a, b = pi - WIN_BEFORE, pi + WIN_AFTER
                    windows[(max(0, a), min(npg, b))].append(row)
                for (a, b), rows_w in sorted(windows.items()):
                    for s in range(0, len(rows_w), GROUP):
                        ch = rows_w[s:s + GROUP]
                        blocks = [{"type": "document", "source": {"type": "base64",
                                   "media_type": "application/pdf", "data": pdf_b64(rd, a, b)}}]
                        mid = (a + b) // 2
                        shrink = (lambda: [{"type": "document", "source": {
                            "type": "base64", "media_type": "application/pdf",
                            "data": pdf_b64(rd, max(0, mid - 1), min(npg, mid + 2))}}])
                        print("  صفحات %d-%d: %d نص" % (a, b, len(ch)), flush=True)
                        run_group(blocks, ch, shrink)
            else:
                try:
                    whole = open(src, encoding="utf-8", errors="replace").read()
                except Exception as exc:
                    for r0 in pend:
                        bump(r0[0], "unreadable"); stats["skipped"] += 1
                    print("  تعذرت القراءة: %s" % str(exc)[:80], flush=True); continue
                wn = nz(re.sub(r"[ \t]+", " ", whole))
                buckets = defaultdict(list)
                for row in pend:
                    pos = -1
                    for pr in probes(row[2], row[1]):
                        pos = wn.find(pr)
                        if pos >= 0:
                            break
                    key = (pos // 40000) if pos >= 0 else -1
                    buckets[key].append(row)
                for key, rows_w in sorted(buckets.items()):
                    if key < 0:
                        seg = whole[:70000]
                    else:
                        c = key * 40000
                        seg = whole[max(0, c - 15000): c + 55000]
                    for s in range(0, len(rows_w), GROUP):
                        ch = rows_w[s:s + GROUP]
                        blocks = [{"type": "text", "text": "المصدر:\n" + seg}]
                        shrink = (lambda seg=seg: [{"type": "text", "text": "المصدر:\n" + seg[:25000]}])
                        print("  مقطع نصي %s: %d نص" % (key, len(ch)), flush=True)
                        run_group(blocks, ch, shrink)

            sk = pend[0][8]
            cur.execute("SELECT count(*) FROM knowledge_objects WHERE source_key=%s", (sk,))
            dbn = cur.fetchone()[0]
            qn = eng.qdrant_request("POST", "/collections/" + eng.COLLECTION + "/points/count",
                                    {"exact": True, "filter": {"must": [{"key": "source_key",
                                     "match": {"value": sk}}]}})["result"]["count"]
            if qn < dbn:
                cur.execute("""SELECT id, coalesce(title,''), coalesce(original_text,''),
                                      object_type, branch, topic, subtopic, metadata->>'micro_issue', source_key
                               FROM knowledge_objects WHERE source_key=%s""", (sk,))
                allr = cur.fetchall()
                for s in range(0, len(allr), 48):
                    w = allr[s:s + 48]
                    common = {"object_type": w[0][3], "branch": w[0][4], "topic": w[0][5],
                              "subtopic": w[0][6], "micro_issue": w[0][7], "source_key": w[0][8]}
                    eng.qdrant_request("PUT", "/collections/" + eng.COLLECTION + "/points?wait=true",
                                       {"points": eng.build_points([(r[0], r[1], r[2]) for r in w], common)})
                print("  رُمّم الفهرس (%d→%d) ✓" % (qn, dbn), flush=True)
        except Exception as exc:
            print("  خطأ %s: %s" % (BID, str(exc)[:130]), flush=True)

    print("نتيجة الجولة: اعتُمد=%d صُحّح=%d لم‑يُعثر=%d بلا‑حكم=%d متعذر=%d (%.0f ث)" %
          (stats["ok"], stats["fix"], stats["nf"], stats["silent"], stats["skipped"],
           time.time() - started), flush=True)

    # التقرير المنشور
    cur.execute("""SELECT verification_status, count(*) FROM knowledge_objects GROUP BY 1 ORDER BY 2 DESC""")
    dist = cur.fetchall()
    cur.execute("""SELECT count(*) FROM knowledge_objects
                   WHERE verification_status='machine_pending_human'
                     AND coalesce(metadata->>'human_edited','') <> 'true'
                     AND coalesce(metadata->>'review_attempts','0')::int < %s""", (MAX_ATTEMPTS,))
    queue_left = cur.fetchone()[0]
    cur.execute("""SELECT count(*) FROM knowledge_objects
                   WHERE verification_status='machine_pending_human'
                     AND coalesce(metadata->>'review_attempts','0')::int >= %s""", (MAX_ATTEMPTS,))
    stuck = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM knowledge_objects")
    dbtot = cur.fetchone()[0]
    qtot = eng.qdrant_request("POST", "/collections/" + eng.COLLECTION + "/points/count",
                              {"exact": True})["result"]["count"]
    cur.execute("""SELECT left(coalesce(title,''),68) FROM knowledge_objects
                   WHERE verification_status='machine_pending_human'
                     AND coalesce(metadata->>'review_attempts','0')::int >= %s LIMIT 12""", (MAX_ATTEMPTS,))
    stuck_titles = [r[0] for r in cur.fetchall()]

with open("/root/review-final.txt", "w", encoding="utf-8") as f:
    f.write("=== حالة المراجعة الذاتية — %s UTC ===\n\n" % time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()))
    f.write("[الجولة الأخيرة] اعتُمد: %d | صُحّح: %d | لم يُعثر: %d | بلا حكم: %d | متعذر: %d\n\n"
            % (stats["ok"], stats["fix"], stats["nf"], stats["silent"], stats["skipped"]))
    f.write("[حالة القاعدة]\n")
    for vs, c in dist:
        f.write("   %-24s %d\n" % (vs, c))
    f.write("\n[الطابور] بانتظار المراجعة الآلية: %d\n" % queue_left)
    f.write("[يحتاج نظرك] تعذّر بعد %d محاولات: %d\n" % (MAX_ATTEMPTS, stuck))
    for t in stuck_titles:
        f.write("   - %s\n" % t)
    f.write("\n[الفهرس] القاعدة: %d | الفهرس: %d | %s\n"
            % (dbtot, qtot, "مطابق ✓" if dbtot == qtot else "غير مطابق — سيُرمَّم"))
    f.write("\nالخدمة تعمل تلقائياً كل 20 دقيقة على كل ملف جديد.\n")
PYEOF

cat > /opt/LegalMind/tools/run_reviewer.sh <<'EOF'
#!/bin/bash
set -a; source /opt/LegalMind/deploy/.env; set +a
exec /opt/LegalMind/.venv/bin/python /opt/LegalMind/tools/reviewer.py
EOF
chmod +x /opt/LegalMind/tools/run_reviewer.sh

cat > /etc/cron.d/legalmind-autoreview <<'EOF'
*/20 * * * * root flock -n /var/lock/lmreview.lock /opt/LegalMind/tools/run_reviewer.sh >> /root/reviewer.log 2>&1
EOF
chmod 644 /etc/cron.d/legalmind-autoreview

cat > /opt/legalmind-autopilot/pushlog.sh <<'EOF'
#!/bin/bash
QDIR=/opt/legalmind-autopilot
TOKEN=$(cat "$QDIR/token")
{
  [ -f /root/review-final.txt ] && cat /root/review-final.txt
  echo ""
  echo "----- آخر أسطر التشغيل -----"
  tail -n 25 /root/reviewer.log 2>/dev/null
} > "/var/www/legalmind-v3/review-$TOKEN.txt" 2>/dev/null
exit 0
EOF
chmod 700 /opt/legalmind-autopilot/pushlog.sh

# تشغيل أول جولة فوراً في الخلفية
nohup flock -n /var/lock/lmreview.lock /opt/LegalMind/tools/run_reviewer.sh >> /root/reviewer.log 2>&1 &
echo "خدمة المراجعة الدائمة رُكّبت وانطلقت أول جولة ✓"
