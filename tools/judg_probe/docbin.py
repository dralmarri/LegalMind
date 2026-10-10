import olefile, struct, sys
def doc_text(path):
    ole = olefile.OleFileIO(path)
    wd = ole.openstream('WordDocument').read()
    flags = struct.unpack_from('<H', wd, 0x0A)[0]
    tbl = ole.openstream('1Table' if flags & 0x0200 else '0Table').read()
    # FibRgFcLcb97: fcClx at offset 0x01A2 in FIB
    fcClx, lcbClx = struct.unpack_from('<II', wd, 0x01A2)
    clx = tbl[fcClx:fcClx+lcbClx]
    i = 0
    while clx[i] == 0x01:  # Prc
        cb = struct.unpack_from('<H', clx, i+1)[0]; i += 3 + cb
    assert clx[i] == 0x02
    lcb = struct.unpack_from('<I', clx, i+1)[0]; pt = clx[i+5:i+5+lcb]
    n = (lcb - 4) // 12
    cps = struct.unpack_from('<%dI' % (n+1), pt, 0)
    out = []
    for k in range(n):
        pcd = pt[4*(n+1)+8*k: 4*(n+1)+8*k+8]
        fc = struct.unpack_from('<I', pcd, 2)[0]
        cnt = cps[k+1]-cps[k]
        if fc & 0x40000000:
            off = (fc & 0x3FFFFFFF)//2
            out.append(wd[off:off+cnt].decode('cp1256', 'replace'))
        else:
            out.append(wd[fc:fc+2*cnt].decode('utf-16le', 'replace'))
    return ''.join(out)
if __name__ == '__main__':
    t = doc_text(sys.argv[1]); open(sys.argv[2], 'w', encoding='utf-8').write(t); print(len(t))
