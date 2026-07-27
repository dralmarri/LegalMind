# ─── إضافة: تحليل متعدد الصيغ (نص/ماركداون/JSON/PDF) بنفس بنية السجلات ───
# يُلحق بنهاية tools/kpkg_docx.py . يعيد استعمال tree()/generate_inbox().
import tempfile, subprocess

_HEAD_MD = re.compile(r'^(#{1,6})\s+(.*\S)\s*$')
# بداية سجل نصّي: «1 - ...» أو «المادة/مادة (رقم)»
_REC_START = re.compile(r'^\s*(?:\d+\s*[-–]\s*\S|(?:المادة|مادة)\s*\(?\s*\d+)')

def _rows_from_text(text):
    rows=[]
    for line in text.replace('\r\n','\n').replace('\r','\n').split('\n'):
        t=line.strip()
        if not t: continue
        m=_HEAD_MD.match(t)
        if m: rows.append({"t":m.group(2).strip(),"md":len(m.group(1))})
        else: rows.append({"t":t,"md":0})
    return rows

def _is_head_text(row):
    t=row["t"]
    if _REC_START.match(t): return False
    if CITATION.match(t): return False
    return t.endswith(":") or t in ORDINALS

def _text_level(row):
    t=row["t"]
    if LETTER_PREFIX.match(t) or DASH_PREFIX.match(t): return 3
    if t in ORDINALS: return 1
    return 2

def parse_text(text, branch_hint=None):
    """يحلّل نصًّا/ماركداون هرميًّا. أول سطر = الفرع (أو «الفرع: ...») ما لم يُمرَّر branch_hint."""
    rows=_rows_from_text(text)
    if not rows: return (branch_hint or "غير محدد"), []
    branch=branch_hint or "غير محدد"; start=0
    if not branch_hint:
        first=rows[0]["t"]
        mfb=re.match(r'^الفرع\s*[:：]\s*(.+)$', first)
        if mfb: branch=mfb.group(1).strip(); start=1
        elif not _REC_START.match(first) and len(first)<40:
            branch=first.rstrip(':').strip(); start=1
    stack={}; records=[]; cur=None
    for row in rows[start:]:
        t=row["t"].rstrip(":").strip(); md=row.get("md",0)
        if md>0 or _is_head_text(row):
            lvl=md if md>0 else _text_level(row)
            lvl=min(max(lvl,1),3)
            stack={k:v for k,v in stack.items() if k<lvl}; stack[lvl]=t
            cur=None
        elif _REC_START.match(row["t"]):
            parts=[stack.get(l) for l in sorted(stack) if stack.get(l)]
            cur={"branch":branch,"topic":parts[0] if len(parts)>0 else None,
                 "subtopic":parts[1] if len(parts)>1 else None,
                 "micro_issue":parts[2] if len(parts)>2 else None,"text":row["t"]}
            records.append(cur)
        elif cur is not None:
            cur["text"]+="\n"+row["t"]
    return branch, records

def parse_json(text):
    data=json.loads(text); branch=None
    if isinstance(data, dict):
        branch=data.get("branch")
        recs=data.get("records") if isinstance(data.get("records"), list) else [data]
    elif isinstance(data, list): recs=data
    else: raise ValueError("JSON غير مدعوم: توقّع كائنًا أو مصفوفة سجلات")
    out=[]
    for r in recs:
        if not isinstance(r, dict): continue
        txt=r.get("text") or r.get("original_text")
        if not txt: continue
        out.append({"branch":r.get("branch") or branch or "غير محدد",
                    "topic":r.get("topic"),"subtopic":r.get("subtopic"),
                    "micro_issue":r.get("micro_issue"),"text":str(txt)})
    b=out[0]["branch"] if out else (branch or "غير محدد")
    return b, out

def extract_pdf_text(path):
    try:
        from pypdf import PdfReader
        return "\n".join((pg.extract_text() or "") for pg in PdfReader(path).pages)
    except ImportError: pass
    except Exception: pass
    try:
        r=subprocess.run(["pdftotext","-layout","-enc","UTF-8",path,"-"],capture_output=True,timeout=180)
        if r.returncode==0 and r.stdout.strip(): return r.stdout.decode("utf-8","ignore")
    except Exception: pass
    raise ValueError("تعذّر استخراج نص PDF — ثبّت pypdf أو poppler-utils")

def parse_any(raw, ext, branch_hint=None):
    ext=(ext or "").lower().lstrip(".")
    if ext=="docx":
        with tempfile.NamedTemporaryFile(suffix=".docx",delete=False) as tf: tf.write(raw); p=tf.name
        try: return parse(p)
        finally: os.unlink(p)
    if ext=="json": return parse_json(raw.decode("utf-8","ignore"))
    if ext=="pdf":
        with tempfile.NamedTemporaryFile(suffix=".pdf",delete=False) as tf: tf.write(raw); p=tf.name
        try: txt=extract_pdf_text(p)
        finally: os.unlink(p)
        return parse_text(txt, branch_hint)
    txt=raw.decode("utf-8","ignore")
    if ext in ("html","htm"): txt=re.sub(r"<[^>]+>"," ", txt)
    return parse_text(txt, branch_hint)
