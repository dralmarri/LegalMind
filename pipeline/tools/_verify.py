import base64,gzip,hashlib,subprocess,re,pathlib
# 1) run the one-liner logic: decode DEPLOY_book3.txt
one=pathlib.Path("DEPLOY_book3.txt").read_text().strip()
m=re.search(r"printf '%s' '([A-Za-z0-9+/=]+)'",one)
b64=m.group(1)
sh=gzip.decompress(base64.b64decode(b64)).decode("utf-8")
sh_sha=hashlib.sha256(sh.encode()).hexdigest()
print("decoded .sh SHA:", sh_sha)
print("matches file :", sh_sha==hashlib.sha256(pathlib.Path('run_book3_full.sh').read_text(encoding='utf-8').encode()).hexdigest())
# 2) extract embedded payloads from the .sh and decode
for name in ["ingest_book3.py","book3_articles.json"]:
    mm=re.search(r"printf '%s' '([A-Za-z0-9+/=]+)' \| base64 -d \| gunzip > \"\$TMP/"+re.escape(name)+"\"",sh)
    payload=gzip.decompress(base64.b64decode(mm.group(1))).decode("utf-8")
    orig=pathlib.Path(name).read_text(encoding="utf-8")
    print(f"{name}: embedded==orig ->", payload==orig, "sha", hashlib.sha256(payload.encode()).hexdigest()[:16])
# 3) bash syntax check of the .sh
r=subprocess.run(["bash","-n","run_book3_full.sh"],capture_output=True,text=True)
print("bash -n:", "OK" if r.returncode==0 else r.stderr)
