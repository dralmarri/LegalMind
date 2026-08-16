import base64,gzip,hashlib,re,pathlib,subprocess
one=pathlib.Path("DEPLOY_book4.txt").read_text().strip()
b64=re.search(r"printf '%s' '([A-Za-z0-9+/=]+)'",one).group(1)
sh=gzip.decompress(base64.b64decode(b64)).decode()
print("sh SHA matches:",hashlib.sha256(sh.encode()).hexdigest()==hashlib.sha256(pathlib.Path('run_book4_full.sh').read_text(encoding='utf-8').encode()).hexdigest())
for name in ["ingest_book4.py","book4_articles.json"]:
    mm=re.search(r"printf '%s' '([A-Za-z0-9+/=]+)' \| base64 -d \| gunzip > \"\$TMP/"+re.escape(name)+"\"",sh)
    payload=gzip.decompress(base64.b64decode(mm.group(1))).decode()
    print(f"{name}: embedded==orig ->", payload==pathlib.Path(name).read_text(encoding='utf-8'))
print("env-source line present:", "set -a; . /opt/LegalMind/deploy/.env; set +a" in sh)
r=subprocess.run(["bash","-n","run_book4_full.sh"],capture_output=True,text=True)
print("bash -n:","OK" if r.returncode==0 else r.stderr)
