# -*- coding: utf-8 -*-
"""Process the judgments DOCX: segment, dedupe, classify branch, redact parties,
extract principles for أحوال شخصية."""
import zipfile, re, json, hashlib
z=zipfile.ZipFile('jud2.docx')
xml=z.read('word/document.xml').decode('utf-8')
paras=re.findall(r'<w:p[ >].*?</w:p>', xml, re.S)
def text_of(p): return ''.join(re.findall(r'<w:t[^>]*>(.*?)</w:t>', p, re.S)).strip()
rows=[text_of(p) for p in paras if text_of(p)]
def artonum(s): return s.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩','0123456789'))

starts=[i for i,t in enumerate(rows) if re.match(r'^\s*بسم الله الرحمن الرحيم', t)]
segs=[rows[starts[k]:(starts[k+1] if k+1<len(starts) else len(rows))] for k in range(len(starts))]

def branch_of(seg):
    txt='\n'.join(seg)
    m=re.search(r'المقيد بالجدول برقم\s*:?\s*[\d٠-٩]+\s*لسنة\s*[\d٠-٩]+\s*([^/\.\n]{2,30})', txt)
    b=m.group(1).strip() if m else ''
    if any(w in b for w in ['أحوال','احوال','شخصية','مواريث']) or 'دائرة الأحوال الشخصية' in txt: return 'أحوال شخصية'
    if 'إداري' in b or 'اداري' in b or 'إداري' in txt or 'اداري' in txt: return 'إداري'
    return 'غير محدد'

def meta_of(seg):
    txt='\n'.join(seg)
    m=re.search(r'المقيد بالجدول برقم\s*:?\s*([\d٠-٩]+)\s*لسنة\s*([\d٠-٩]+)\s*([^/\n]+?)(?:/|\()', txt)
    num=artonum(m.group(1)) if m else None; yr=artonum(m.group(2)) if m else None
    reg=m.group(3).strip() if m else None
    dt=re.search(r'الموافق\s*([\d/]{6,10})', txt); date=dt.group(1) if dt else None
    circ=next((t for t in seg if 'دائرة' in t), None)
    return {'appeal_no':num,'appeal_year':yr,'register':reg,'session_date':date,'circuit':circ}

# --- party-name redaction: capture names from parties block, redact throughout ---
def capture_parties(seg):
    txt='\n'.join(seg)
    m=re.search(r'المرفوع[^\n:]*من\s*:?(.*?)المقيد بالجدول', txt, re.S)
    block=m.group(1) if m else ''
    names=set()
    for line in block.split('\n'):
        line=re.sub(r'^\s*\d+\s*[-\)]\s*','',line).strip()
        line=re.sub(r'"[^"]*"','',line)  # drop "بصفته" etc
        line=re.sub(r'\b(ضد|ضـد|المرحوم|المرحومة|بصفته|بصفتها|وصياً|على القصر|أولاد|مدير عام|وكيل|الهيئة العامة|وزارة|إدارة|المؤسسة العامة|بصفتهم)\b','',line)
        for w in re.split(r'[\s،,/\(\)]+',line):
            if len(w)>=3 and re.match(r'^[ء-يٱآأإؤئ]+$',w): names.add(w)
    # also المرحوم/ NAME anywhere
    for m2 in re.finditer(r'المرحوم[ة]?\s*/?\s*([ء-ي]+(?:\s+[ء-ي]+){1,4})', txt):
        for w in m2.group(1).split(): 
            if len(w)>=3: names.add(w)
    STOP={'الله','عبد','بصفته','بصفتها','القصر','أولاد','وزير','العدل','الأوقاف','الداخلية','المالية','الصحة',
          'التربية','الأشغال','الكهرباء','المؤسسة','الهيئة','العامة','المدنية','للمعلومات','للرعاية','السكنية',
          'لشئون','القُصَّر','القصر','ورثة','المطعون','ضدهم','ضده','ضدها','الطاعن','الطاعنة','الطاعنين','المستأنف',
          'الطعن','بالتمييز','المرفوع','المرفوعين','أولهما','ثانيهما','التسجيل','العقاري','العقار','لإدارة','مالكين',
          'جميعا','الأول','الثاني','الثالث','الرابع','الخامس','السادس','السابع','على','الشيوع','مدير','عام','وكيل',
          'وزارة','إدارة','بصفتهم','وصيا','وصياً','المرحوم','المرحومة','بنك','شركة','مؤسسة','جمعية','والمقيد',
          'الكويت','دولة','حكومة','ديوان','الخدمة','البلدية','النيابة','العسكري','الجيش','والتعليم','العالي',
          'التجارة','الصناعة','النفط','الاعلام','الاوقاف','الاسلامية','الزراعة'}
    return {n for n in names if n not in STOP}

def redact(txt, party_names):
    txt=re.sub(r'\(?\s*\b\d{11,12}\b\s*\)?','[رقم مدني]',txt)
    toks=sorted([n for n in party_names if len(n)>=3],key=len,reverse=True)
    if toks:
        txt=re.sub(r'(?<![ء-يٱآأإؤئ])(?:و|ف|ب|ل)?(?:'+'|'.join(re.escape(x) for x in toks)+r')(?![ء-يٱآأإؤئ])','[اسم]',txt)
    txt=re.sub(r'(\[اسم\]\s*){2,}','[اسم] ',txt)
    return re.sub(r'[ \t]+',' ',txt).strip()

# --- principle extraction (أحوال شخصية) ---
def principles(txt):
    out=[]
    CUES=r'(?:المقرر|جرى\s+قضاء\s+هذه\s+المحكمة|قضاء\s+هذه\s+المحكمة\s+(?:قد\s+)?جرى|المستقر\s+عليه|المستقر\s+في\s+قضاء)'
    for m in re.finditer(CUES+r'[^.]{0,60}?أن\s+(.{40,650}?)(?=(?:وحيث\b|لما كان ذلك|فلهذه الأسباب|وإذ\b)|\Z)', txt, re.S):
        p=re.sub(r'\s+',' ',m.group(1)).strip().rstrip('،, .')
        if 25<len(p)<750: out.append(p)
    # dedupe
    seen=set(); uniq=[]
    for p in out:
        k=p[:40]
        if k in seen: continue
        seen.add(k); uniq.append(p)
    return uniq

# process all
results=[]
for k,seg in enumerate(segs):
    br=branch_of(seg); md=meta_of(seg)
    txt='\n'.join(seg)
    party=capture_parties(seg)
    red=redact(txt, party)
    ch=hashlib.sha256(re.sub(r'[^ء-ي]','',red)[:2000].encode()).hexdigest()[:16]
    results.append({'seg':k,'branch':br,'meta':md,'chars':len(red),'text':red,
                    'party_names':sorted(party),'content_hash':ch,
                    'principles': principles(red) if br=='أحوال شخصية' else []})

# dedupe by content hash
seen={}; dedup=[]
for r in results:
    if r['content_hash'] in seen: continue
    seen[r['content_hash']]=1; dedup.append(r)
from collections import Counter
print("total segments:", len(results), "| after dedup:", len(dedup))
print("branch (dedup):", dict(Counter(r['branch'] for r in dedup)))
ah=[r for r in dedup if r['branch']=='أحوال شخصية']
print("\nأحوال شخصية unique:", len(ah))
for r in ah:
    print("  seg%-3d %s/%s | %d principles | %d chars"%(r['seg'],r['meta']['appeal_no'],r['meta']['appeal_year'],len(r['principles']),r['chars']))
json.dump(dedup, open('jud_processed.json','w'), ensure_ascii=False)
print("\nsaved jud_processed.json")
