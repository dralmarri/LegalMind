# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, "/opt/LegalMind/engine")
import legalmind_engine as eng
import claude_reader as cr
from pathlib import Path

BID = sys.argv[1]
PDF = Path(sys.argv[2])
print("الدفعة:", BID, flush=True)
print("الملف:", PDF, flush=True)
tax = cr._taxonomy(eng)
print("بدء القراءة البصرية الكاملة (دفعات صفحات)...", flush=True)
result = cr._structure(PDF, None, tax, {}, progress=lambda s, p: print(s, "-", p, "%", flush=True))
chunks = result.get("chunks", [])
print("قطع الرؤية:", len(chunks), flush=True)

def norm_no(x):
    if x is None:
        return None
    s = str(x).strip().translate(str.maketrans("0123456789", "0123456789")).translate(
        str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    return s or None

vis, dupv = {}, set()
for c in chunks:
    nno = norm_no(c.get("number"))
    if not nno:
        continue
    if nno in vis:
        dupv.add(nno)
    else:
        vis[nno] = c
for d in dupv:
    vis.pop(d, None)
print("مواد الرؤية القابلة للمطابقة:", len(vis), flush=True)

with eng.psycopg.connect(eng.database_url()) as conn:
    with conn.cursor() as cur:
        cur.execute("""SELECT id, coalesce(metadata->>'number',''), coalesce(metadata->>'human_edited','')
                       FROM knowledge_objects WHERE metadata->>'batch_id'=%s""", (BID,))
        rows = cur.fetchall()
print("كائنات القاعدة:", len(rows), flush=True)
existing, dupe = {}, set()
for oid, nno, edited in rows:
    nno = norm_no(nno)
    if not nno:
        continue
    if nno in existing:
        dupe.add(nno)
    else:
        existing[nno] = (oid, edited)
for d in dupe:
    existing.pop(d, None)

updated, skipped_edit, unmatched = [], 0, 0
embed_rows = []
with eng.psycopg.connect(eng.database_url()) as conn:
    with conn.cursor() as cur:
        for nno, c in vis.items():
            if nno not in existing:
                unmatched += 1
                continue
            oid, edited = existing[nno]
            if edited.lower() == "true":
                skipped_edit += 1
                continue
            conf = float(c.get("confidence", 0))
            vs = "source_verified" if conf >= 0.8 else "machine_pending_human"
            auth, citable = eng.authority_for("legislation", vs)
            cur.execute("""UPDATE knowledge_objects SET original_text=%s, normalized_text=%s, title=%s,
                           verification_status=%s, authority_status=%s, usable_as_citation=%s,
                           metadata = metadata || %s, updated_at=now() WHERE id=%s""",
                        (c["text"], eng.normalize_text(c["text"]), c["title"], vs, auth, citable,
                         eng.Jsonb({"vision_repaired": True, "confidence": conf}), oid))
            updated.append(oid)
            embed_rows.append((oid, c["title"], c["text"]))
    conn.commit()
print("حُدث:", len(updated), "| تُخطي (معدل يدويا):", skipped_edit, "| بلا مطابق:", unmatched, flush=True)
if embed_rows:
    for s in range(0, len(embed_rows), 64):
        w = embed_rows[s:s + 64]
        pts = eng.build_points(w, {"object_type": "legislation", "branch": "تجاري", "topic": "النقل",
                                   "subtopic": None, "micro_issue": None, "source_key": "maritime-vision-repair"})
        eng.qdrant_request("PUT", "/collections/" + eng.COLLECTION + "/points?wait=true", {"points": pts})
        print("إعادة الفهرسة:", s + len(w), "/", len(embed_rows), flush=True)
print("== اكتمل الإصلاح بالرؤية ==", flush=True)
