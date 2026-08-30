# -*- coding: utf-8 -*-
import re, sys

STOP=set('''الجنسية المدنية بطاقة رقم المحامي المحامية المحاماة الطالب الطالبة الطالبين المستأنف
المستأنفة المستأنفين المدعية المدعي عليه عليها الدعوى الكويت بموجب الموضوع الحكم المحكمة الاستئناف
النفقة الحضانة الزوجية الزوج الزوجة الابن الابنة الأبناء الأولاد المحضون المحضونة الجلسة إدارة الكتاب
التنفيذ العدل وزارة صفته بصفته مندوب الإعلان مكتب الكائن أحوال شخصية كويتي كويتية مصري مصرية أردني
والكائن يعلن ويعلن يقيم مخاطبا الآتي وأعلنته السيد السيدة بناء طلب حاضنة أجرة مسكن خادمة سائق ممرضة'''.split())

NAT=r'(?:كويتي|كويتية|مصري|مصرية|أردني|أردنية|سعودي|سعودية|بحريني|بحرينية|قطري|قطرية|إماراتي|إماراتية|سوري|سورية|لبناني|لبنانية|فلسطيني|فلسطينية|يمني|يمنية|عراقي|عراقية|سوداني|سودانية)'

def tokens_of(span):
    return [w for w in re.split(r'[\s،,–\-/()\.]+', span) if len(w)>=3 and re.match(r'^[ء-يٱآأإؤئ]+$',w) and w not in STOP]

def collect_names(t):
    names=set()
    for m in re.finditer(r'([ء-يٱآأإؤئ\. ]{4,50}?)\s*[–\-]?\s*'+NAT+r'\s+الجنسية', t):
        names.update(tokens_of(m.group(1)))
    for m in re.finditer(r'(?:المحامي(?:ة|ان|ون|ين)?|وكيل\s+\S+|مكتب\s+المحام\S+)\s*/?\s*(?:الدكتور|د\.?|أ\.?|الأستاذ)?\s*/?\s*([ء-يٱآأإؤئ\. ]{4,40})', t):
        names.update(tokens_of(m.group(1)))
    for m in re.finditer(r'(?:أبناء|أولاد|بالأبناء|لأبناء\S*|لأولاد\S*|المحضون\S*|رزقت[^()]{0,25}?)\s*\(\s*([^)]{3,60}?)\s*\)', t):
        names.update(tokens_of(m.group(1)))
    return names

def redact(t):
    t=re.sub(r'[ \t]+',' ',t)
    t=re.sub(r'(?m)^\s*\d{5,}\s*','',t); t=re.sub(r'(?m)^\s*00\s*','',t)
    names=collect_names(t)
    # structural PII
    t=re.sub(r'\(?\s*\b\d{11,12}\b\s*\)?','[رقم مدني]',t)
    t=re.sub(r'(تليفون|هاتف|موبايل|جوال|فاكس)\s*:?\s*[\d/\- ]{6,}', r'\1: [هاتف]', t)
    t=re.sub(r'\b\d{7,9}\b','[رقم]',t)
    t=re.sub(r'\b\d{1,4}\s*/\s*\d{4}\b','[رقم الدعوى]',t)
    t=re.sub(r'[–\-]?\s*'+NAT+r'\s+الجنسية','– [الجنسية]',t)
    t=re.sub(r'(الكائن(?:\s+مقره)?|والكـ?ائـ?ن|ويقيم\s+في|يعلن\s+في|محل[هـ]?ا?\s+المختار|ومحل[هـ]?ا?\s+المختار)\s*:?[^.،]{0,130}',
             r'\1 [العنوان] ', t)
    # blanket name-token redaction
    toks=sorted([n for n in names if len(n)>=3], key=len, reverse=True)
    if toks:
        pat=r'(?<![ء-ي])(?:'+'|'.join(re.escape(x) for x in toks)+r')(?![ء-ي])'
        t=re.sub(pat,'[اسم]',t)
    t=re.sub(r'(\[اسم\]\s*)+','[اسم] ',t)
    t=re.sub(r'[ \t]+',' ',t); t=re.sub(r'\n{2,}','\n',t)
    return t.strip(), names

f=sys.argv[1]
t=open(f+'.txt',encoding='utf-8').read()
r,names=redact(t)
open(f+'.red.txt','w',encoding='utf-8').write(r)
print("### %s | names captured: %d | %s"%(f, len(names), '، '.join(sorted(names))[:120]))
