import zipfile, re, html, json
z=zipfile.ZipFile('labor2.docx')
xml=z.read('word/document.xml').decode('utf-8')
lines=[html.unescape(''.join(re.findall(r'<w:t[^>]*>(.*?)</w:t>',p,re.S))).strip()
       for p in re.split(r'</w:p>',xml)]
lines=[l for l in lines if l]
art_re=re.compile(r'^مادة\s+([0-9]+)\s*$')
arts={}; order=[]; cur=None; buf=[]
def flush():
    global cur,buf
    if cur: arts[cur]="\n".join(buf).strip()
    buf=[]
started=False
for l in lines:
    m=art_re.match(l)
    if m:
        flush(); cur=m.group(1); order.append(cur); buf=[]; started=True; continue
    if not started: continue          # preamble handled separately
    # stop at امير الكويت (signatures)
    if l.startswith("أمير الكويت") or l.startswith("امير الكويت"):
        flush(); cur=None; break
    buf.append(l)
flush()
json.dump({"articles":arts,"order":order}, open('labor2_parsed.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
print("articles:",len(arts),"->",",".join(order))
for n in order:
    print(f"--- م{n} ---\n{arts[n][:150]}\n")
