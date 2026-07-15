# -*- coding: utf-8 -*-
"""تحليل DOCX هرمي لأحكام/مبادئ ⇒ مبادئ موسومة بمسارها الموضوعي.
لا مكتبات خارجية: يقرأ word/document.xml بـ zipfile مباشرة."""
import zipfile, re, hashlib

ORDINALS={"أولاً","أولا","ثانياً","ثانيا","ثالثاً","ثالثا","رابعاً","رابعا","خامساً","خامسا",
          "سادساً","سادسا","سابعاً","ثامناً","تاسعاً","عاشراً","حادي عشر","ثاني عشر"}
PRINCIPLE=re.compile(r"^\s*\d+\s*[-]\s*\S")
CITATION=re.compile(r"^\s*\(?\s*الطعن")
LETTER_PREFIX=re.compile(r"^\s*[أ-يهـ]\s*[–\-:]")
DASH_PREFIX=re.compile(r"^\s*[–\-]\s*\S")

def read_paras(path):
    z=zipfile.ZipFile(path); xml=z.read('word/document.xml').decode('utf-8','ignore')
    out=[]
    for p in re.findall(r'<w:p\b.*?</w:p>',xml,re.S):
        t=''.join(re.findall(r'<w:t[^>]*>(.*?)</w:t>',p,re.S)).strip()
        if not t: continue
        m=re.search(r'<w:pStyle w:val="([^"]+)"',p)
        out.append({"t":t,"style":m.group(1) if m else '',"bold":('<w:b/>' in p or '<w:b>' in p)})
    return out

def _is_heading(row):
    t=row["t"]
    if CITATION.match(t): return False
    if PRINCIPLE.match(t) and not t.endswith(":"): return False
    return t.endswith(":") or (row["bold"] and row["style"] in {"a0","aa","ab"}) or t in ORDINALS \
           or (row["style"] in {"a0","a2","aa","ab"} and len(t)<70)

def parse(path):
    rows=read_paras(path); branch=rows[0]["t"] if rows else "غير محدد"
    stack={}; records=[]; pending=None; cur=None
    for row in rows:
        t=row["t"].rstrip(":").strip()
        if _is_heading(row):
            if row["t"].strip() in ORDINALS: pending=t; continue
            if pending: stack={1:f"{pending} — {t}"}; pending=None
            elif row["bold"] and row["style"]=="a0": stack={1:t}
            elif LETTER_PREFIX.match(row["t"]) or DASH_PREFIX.match(row["t"]):
                stack={k:v for k,v in stack.items() if k<3}; stack[3]=t
            else:
                stack={k:v for k,v in stack.items() if k<2}; stack[2]=t
            cur=None
        elif PRINCIPLE.match(row["t"]) and not row["t"].endswith(":"):
            parts=[stack.get(l) for l in sorted(stack) if stack.get(l)]
            cur={"branch":branch,"topic":parts[0] if len(parts)>0 else None,
                 "subtopic":parts[1] if len(parts)>1 else None,
                 "micro_issue":parts[2] if len(parts)>2 else None,"text":row["t"]}
            records.append(cur)
        elif cur is not None:
            cur["text"]+="\n"+row["t"]
    return branch,records

def clean_label(s):
    if not s: return ""
    s=re.sub(r"^\s*(أولاً|ثانياً|ثالثاً|رابعاً|خامساً|سادساً|سابعاً|ثامناً|تاسعاً|عاشراً|حادي عشر|ثاني عشر)\s*—\s*","",s)
    s=re.sub(r"^\s*\d+\s*[-–:]\s*","",s); s=re.sub(r"^\s*[أ-يهـ]\s*[–\-:]\s*","",s); s=re.sub(r"^\s*[–\-]\s*","",s)
    return s.strip()

def tree(records):
    """شجرة معاينة: قائمة {topic,subtopic,micro_issue,count} مرتّبة."""
    from collections import OrderedDict
    agg=OrderedDict()
    for r in records:
        k=(clean_label(r["topic"]),clean_label(r["subtopic"]),clean_label(r["micro_issue"]))
        agg[k]=agg.get(k,0)+1
    return [{"topic":t,"subtopic":s,"micro_issue":m,"count":c} for (t,s,m),c in agg.items()]

if __name__=="__main__":
    import sys, json
    b,recs=parse(sys.argv[1])
    print(f"الفرع: {b} | مبادئ: {len(recs)} | مسارات: {len(tree(recs))}")
    for row in tree(recs):
        print(f"  {row['topic']} / {row['subtopic'] or '—'} / {row['micro_issue'] or '—'}  ⇐ {row['count']}")


# ─── توليد ملفات inbox من الشجرة المعتمدة ───────────────────────────────────
import json, os, datetime

def _safe(s):
    return re.sub(r"[^\w؀-ۿ]+","_",s or "")[:45].strip("_")

def generate_inbox(records, inbox_dir, overrides=None, verification="source_verified"):
    """يولّد ملف .md + sidecar لكل مسار موضوعي. أسماء فريدة (بادئة رقمية).
    overrides: قائمة اختيارية بنفس ترتيب tree() لاستبدال (topic,subtopic,micro).
    يعيد قائمة الملفات المُنشأة + الإحصاء."""
    from collections import OrderedDict
    groups=OrderedDict()
    for r in records:
        key=(clean_label(r["topic"]),clean_label(r["subtopic"]),clean_label(r["micro_issue"]))
        groups.setdefault(key,[]).append(r["text"])
    # طبّق التصحيحات إن وُجدت (بالمطابقة على المفتاح الأصلي)
    ov={}
    if overrides:
        for o in overrides:
            ov[(o.get("orig_topic"),o.get("orig_subtopic"),o.get("orig_micro"))]=(
                o.get("topic"),o.get("subtopic"),o.get("micro_issue"))
    branch=records[0]["branch"] if records else "غير محدد"
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    os.makedirs(inbox_dir,exist_ok=True)
    created=[]; n_pr=0
    for idx,(key,texts) in enumerate(groups.items(),1):
        topic,sub,micro = ov.get(key, key)
        parts=[re.sub(r"^\s*\d+\s*-\s*",f"{i}- ",t,count=1) for i,t in enumerate(texts,1)]
        body="\n\n".join(parts)
        stem=f"{idx:02d}_"+(_safe("__".join(x for x in [topic,sub,micro] if x)) or f"grp{idx}")
        md=os.path.join(inbox_dir,stem+".md")
        with open(md,"w",encoding="utf-8") as f: f.write(body+"\n")
        sidecar={"source_type":"judicial_principles_collection","object_type":"judicial_principle",
                 "branch":branch,"topic":topic or None,"subtopic":sub or None,"micro_issue":micro or None,
                 "classification_title":(micro or sub or topic or None),"court_level":None,"circuit":None,
                 "title":" / ".join(x for x in [topic,sub,micro] if x),
                 "verification_status":verification,"source_notes":None,
                 "upload_origin":"docx_hierarchical_import","received_at":now,
                 "drafting_status":None,"pasted_chars":len(body)}
        with open(md+".json","w",encoding="utf-8") as f:
            f.write(json.dumps(sidecar,ensure_ascii=False,indent=1))
        created.append(stem+".md"); n_pr+=len(texts)
    return {"files":len(created),"principles":n_pr,"created":created}
