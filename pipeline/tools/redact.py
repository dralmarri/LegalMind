# -*- coding: utf-8 -*-
import re, sys, json

def redact(t):
    t=re.sub(r'[ \t]+',' ',t)
    # drawing/shape numeric artifacts at line starts
    t=re.sub(r'(?m)^\s*\d{6,}\s*','',t)
    t=re.sub(r'(?m)^\s*00\s*','',t)
    # civil IDs (11-12 digits, often in parens after بطاقة/ب.م)
    t=re.sub(r'\(?\s*\b\d{11,12}\b\s*\)?','[رقم مدني]',t)
    # phones
    t=re.sub(r'(تليفون|هاتف|موبايل|جوال)\s*:?\s*[\d/\- ]{6,}', r'\1: [هاتف]', t)
    # case / appeal / execution file numbers
    t=re.sub(r'\b\d{1,4}\s*/\s*\d{4}\b','[رقم الدعوى]',t)
    t=re.sub(r'\(\s*0\d{7,}\s*\)','[رقم ملف]',t)
    # names anchored by nationality (dash optional):  <name> [–] <nat> الجنسية
    NAT=r'(?:كويتي|كويتية|مصري|مصرية|أردني|أردنية|سعودي|سعودية|بحريني|بحرينية|قطري|قطرية|إماراتي|سوري|سورية|لبناني|لبنانية|فلسطيني|فلسطينية|يمني|يمنية|عراقي|عراقية|سوداني|سودانية|[ء-ي]{3,})'
    t=re.sub(r'[ء-يٱآأإؤئ\.]{2,}(?:\s+[ء-يٱآأإؤئ\.]{2,}){1,5}\s*[–\-]?\s*'+NAT+r'\s+الجنسية',
             '[اسم] – [الجنسية]', t)
    # standalone 8-9 digit numbers (phones/refs)
    t=re.sub(r'\b\d{8,9}\b','[رقم]',t)
    # lawyer / agent slots (keep label, redact name up to delimiter)
    t=re.sub(r'(المحامي(?:ة|ان|ون|ين)?|وكيل\s+(?:الطالب|الطالبة|الطالبين|المستأنف|المستأنفة|المدعي|المدعية))\s*/?\s*'
             r'(?:الدكتور|د\.?|أ\.?|الأستاذ)?\s*/?\s*[ء-ي\.]{2,}(?:\s+[ء-ي\.]{2,}){0,4}',
             r'\1 / [اسم المحامي]', t)
    t=re.sub(r'(مكتب\s+المحام(?:ي|ية|اة))\s*(?:الدكتور|د\.?|أ\.?)?\s*/?\s*[ء-ي\.]{2,}(?:\s+[ء-ي\.]{2,}){0,4}',
             r'\1 / [اسم المحامي]', t)
    # addresses
    t=re.sub(r'(الكائن(?:\s+مقره)?|والكـ?ائـ?ن|ويقيم\s+في|يعلن\s+في|محل[هـ]ا?\s+المختار|ومحل[هـ]ا?\s+المختار)\s*:?[^.]{0,120}?(?=[.،]|$)',
             r'\1 [العنوان]', t)
    # children name lists after cue words
    t=re.sub(r'(أبنائها|أولادها|أبنائه|أولاده|المحضون(?:ة|ين)?|رزقت\s+منه[^()]{0,20}?|وهم)\s*\(\s*[ء-ي]+(?:\s*[،,و]\s*[ء-ي]+){0,6}\s*\)',
             r'\1 ([أسماء المحضونين])', t)
    t=re.sub(r'[ \t]+',' ',t); t=re.sub(r'\n{2,}','\n',t)
    return t.strip()

def scan(t):
    issues=[]
    for m in re.findall(r'\b\d{8,}\b', t): issues.append('digits:'+m)
    if 'الجنسية' in t:
        for m in re.findall(r'.{0,15}الجنسية', t):
            if '[الجنسية]' not in m: issues.append('nat:'+m.strip())
    return issues

f=sys.argv[1]
t=open(f+'.txt',encoding='utf-8').read()
r=redact(t)
open(f+'.red.txt','w',encoding='utf-8').write(r)
iss=scan(r)
print("### %s | %d->%d chars | residual issues: %d"%(f,len(t),len(r),len(iss)))
for i in iss[:12]: print("   ⚠",i)
