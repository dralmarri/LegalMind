import base64,gzip,hashlib,re,pathlib,subprocess
one=pathlib.Path("DEPLOY_book3_bundles.txt").read_text().strip()
b64=re.search(r"printf '%s' '([A-Za-z0-9+/=]+)'",one).group(1)
sh=gzip.decompress(base64.b64decode(b64)).decode()
print("sh SHA:",hashlib.sha256(sh.encode()).hexdigest())
print("matches file:",hashlib.sha256(sh.encode()).hexdigest()==hashlib.sha256(pathlib.Path('run_book3_bundles.sh').read_text(encoding='utf-8').encode()).hexdigest())
# embedded app.py
mm=re.search(r"printf '%s' '([A-Za-z0-9+/=]+)' \| base64 -d \| gunzip > \"\$TMP/app.py\"",sh)
app=gzip.decompress(base64.b64decode(mm.group(1))).decode()
print("embedded app==mirror:",app==pathlib.Path('/tmp/app_patched.py').read_text(encoding='utf-8'))
r=subprocess.run(["bash","-n","run_book3_bundles.sh"],capture_output=True,text=True)
print("bash -n:","OK" if r.returncode==0 else r.stderr)
