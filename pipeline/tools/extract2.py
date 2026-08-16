import zipfile, re, struct, olefile, html, sys
def from_docx(p):
    xml=zipfile.ZipFile(p).read('word/document.xml').decode('utf-8')
    xml=re.sub(r'<w:tab[^>]*/?>',' ',xml)
    xml=re.sub(r'</w:p>','\n',xml)
    xml=re.sub(r'<w:br[^>]*/?>','\n',xml)
    txt=re.sub(r'<[^>]+>','',xml)
    return html.unescape(txt)
def from_doc(p):
    ole=olefile.OleFileIO(p); wd=ole.openstream('WordDocument').read()
    flags=struct.unpack_from('<H',wd,0x0A)[0]
    tbl=ole.openstream('1Table' if flags&0x0200 else '0Table').read()
    fcClx=struct.unpack_from('<I',wd,0x01A2)[0]; lcbClx=struct.unpack_from('<I',wd,0x01A6)[0]
    clx=tbl[fcClx:fcClx+lcbClx]; i=0; pcd=None
    while i<len(clx):
        if clx[i]==1: i+=3+struct.unpack_from('<H',clx,i+1)[0]
        elif clx[i]==2: lcb=struct.unpack_from('<I',clx,i+1)[0]; pcd=clx[i+5:i+5+lcb]; break
        else: break
    n=(len(pcd)-4)//12; cps=[struct.unpack_from('<I',pcd,k*4)[0] for k in range(n+1)]
    out=[]
    for k in range(n):
        fcf=struct.unpack_from('<I',pcd,4*(n+1)+k*8+2)[0]
        comp=(fcf&0x40000000)!=0; fc=fcf&0x3FFFFFFF; ln=cps[k+1]-cps[k]
        if comp: out.append(wd[fc//2:fc//2+ln].decode('cp1256','replace'))
        else: out.append(wd[fc:fc+ln*2].decode('utf-16-le','replace'))
    return ''.join(out)
f=sys.argv[1]
txt=from_docx(f) if f.endswith('.docx') else from_doc(f)
txt=re.sub(r'[ \t]+',' ',txt); txt=re.sub(r'\n{2,}','\n',txt).strip()
open(f+'.txt','w',encoding='utf-8').write(txt)
print("### %s | %d chars"%(f,len(txt)))
