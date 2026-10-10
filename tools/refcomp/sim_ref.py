import os, sys, subprocess, psycopg, json, gzip, base64
from psycopg.types.json import Jsonb
S = sys.argv[1]; DB = "postgresql://root:x@localhost:55499/lmtest"
F = "/home/user/LegalMind/tools/ingest_reference_missing_20261005.py"
env = dict(os.environ, DATABASE_URL=DB, LM_ROOT=S + "/fakeroot", FAKE_QDRANT_LOG=S + "/qlog.txt")
ok = []
def check(c, m): print(("✓ " if c else "✗ ") + m); ok.append(bool(c))
def q(sql, a=()):
    with psycopg.connect(DB) as c, c.cursor() as cur:
        cur.execute(sql, a); return cur.fetchall()
def run(*a, extra=None):
    e = dict(env, **(extra or {}))
    p = subprocess.run([sys.executable, F] + list(a), env=e, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr
ALL = "SELECT md5(string_agg(id||'|'||coalesce(title,'')||'|'||coalesce(original_text,'')||'|'||coalesce(metadata::text,''),'#' ORDER BY id)) FROM knowledge_objects"
def fx(extra=None):
    with psycopg.connect(DB) as c, c.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS knowledge_objects")
        cur.execute("""CREATE TABLE knowledge_objects(id text primary key, object_type text, branch text, topic text,
          subtopic text, micro_issue text, title text, original_text text, normalized_text text, source_key text,
          verification_status text CHECK (verification_status IN ('source_verified','operationally_accepted','machine_pending_human','historical_only','requires_post_2026_reassessment','superseded')),
          metadata jsonb, authority_status text CHECK (authority_status IN ('source_authority','non_authoritative','human_verified_authority')),
          usable_as_citation boolean, updated_at timestamptz default now())""")
        for i in ("legis-dustur-1962-m1", "legis-12-1960-m1", "legis-120-2013-m1", "legis-37-2014x-m1", "legis-63-20155-m1"):
            cur.execute("INSERT INTO knowledge_objects(id,object_type,title,original_text,metadata,verification_status,authority_status,usable_as_citation) VALUES (%s,'legislation_article','t','x',%s,'source_verified','source_authority',true)", (i, Jsonb({})))
        if extra == "collide":
            cur.execute("INSERT INTO knowledge_objects(id,object_type,title,original_text,metadata) VALUES ('legis-15-1959-m99','legislation_article','t','قديم','{}')")
        c.commit()
os.makedirs(S + "/simout", exist_ok=True)
fx(); h0 = q(ALL)[0][0]
rc, out = run("--ids-out", S + "/simout/ids1.txt"); print(out[-1200:])
check(rc == 0 and "INGEST_REFMISSING_OK" in out, "الإدخال ينجح")
n = q("SELECT count(*) FROM knowledge_objects")[0][0]
check(n == 5 + 504, "العدد 509: %d" % n)
ids1 = open(S + "/simout/ids1.txt").read().split()
check(len(ids1) == 504, "ملف المعرفات الجديدة 504")
r = q("SELECT verification_status, count(*) FROM knowledge_objects WHERE id LIKE 'legis-%%' AND metadata ? 'text_provenance' GROUP BY 1 ORDER BY 1")
check(dict(r) == {"machine_pending_human": 48, "operationally_accepted": 456}, "توزيع الحالة: %s" % r)
r = q("SELECT count(*) FROM knowledge_objects WHERE metadata->>'extraction_uncertain'='true' AND NOT (metadata ? 'source_note')")
check(r[0][0] == 0, "كل موسوم يحمل source_note ظاهرة")
r = q("SELECT original_text FROM knowledge_objects WHERE id='legis-120-2023-m35'")
check(r[0][0] == "يكون الانتخاب عامًا وسريًا ومباشرًا.", "120/2023 م35 بنصّها")
r = q("SELECT metadata->'missing_articles_in_source' FROM knowledge_objects WHERE id='legis-70-2020-preamble'")
check(r[0][0] == [25], "70/2020 م25 مسجَّلة غائبة: %s" % r)
r = q("SELECT count(*) FROM knowledge_objects WHERE original_text ~ '\\(\\(\\(|جزاء العتيبي|^#'")
check(r[0][0] == 0, "لا علامات إحالة ولا اسم مُعِدّ ولا عناوين Markdown")
r = q("SELECT title FROM knowledge_objects WHERE id='legis-61-2015-m1'")
check("61/2015" in r[0][0], "الكاميرات برقم المتن 61/2015")
r = q("SELECT count(*) FROM knowledge_objects WHERE id IN ('legis-12-1960-m1','legis-120-2013-m1','legis-37-2014x-m1','legis-63-20155-m1') AND original_text='x'")
check(r[0][0] == 4, "البادئات المتشابهة لم تُمسّ")
r = q("SELECT original_text, verification_status, metadata->>'extraction_method' FROM knowledge_objects WHERE id='legis-12-1963-m5'")
check(r[0][0].startswith("لكل ناخب") and "مرشحًا فيها" in r[0][0] and r[0][1]=="operationally_accepted" and r[0][2].startswith("visual"), "م5 بنص الصورة وبلا وسم")
r = q("SELECT count(*) FROM knowledge_objects WHERE original_text ~ '(تم|عدلت?|معدلة|مضافة|مستبدلة)\\s+[^\\n]{0,30}(بموجب|وفق)\\s+(ال)?(قانون|مرسوم)[^\\n]{0,30}لسنة\\s*[0-9٠-٩]{4}\\s*$' AND id LIKE 'legis-%%' AND metadata ? 'text_provenance'")
check(r[0][0] == 0, "لا حاشية تعديل في ذيل أي مادة: %s" % r)
r = q("SELECT metadata->>'source_note' FROM knowledge_objects WHERE id='legis-12-1963-m16'")
check("عدم دستورية المادة 16" in (r[0][0] or ""), "م16 تحمل حاشية الحكم الدستوري")
# إعادة التشغيل
h1 = q(ALL)[0][0]
rc, out = run("--ids-out", S + "/simout/ids2.txt")
check(rc == 0 and "قائم سلفًا من هذه الدفعة 504،" in out and open(S + "/simout/ids2.txt").read() == "", "إعادة التشغيل: لا جديد")
h2 = q("SELECT md5(string_agg(id||'|'||coalesce(title,'')||'|'||coalesce(original_text,'')||'|'||coalesce(metadata::text,''),'#' ORDER BY id)) FROM knowledge_objects")[0][0]
check(h2 == h1, "إعادة التشغيل بلا أثر في المحتوى")
# التراجع
open(S + "/qlog.txt", "w").close()
rc, out = run("--rollback", S + "/simout/ids1.txt")
ql = [json.loads(l) for l in open(S + "/qlog.txt")]
check(rc == 0 and "ROLLBACK_DONE" in out and q(ALL)[0][0] == h0, "التراجع يعيد القاعدة بايتًا ببايت")
check(ql and ql[0]["n"] == 504 and "points/delete" in ql[0]["p"], "التراجع يحذف 504 نقطة Qdrant: %s" % ql)
# تراجع يرفض معرّفًا غريبًا
open(S + "/simout/evil.txt", "w").write("legis-16-1960-m1\n")
rc, out = run("--rollback", S + "/simout/evil.txt")
check(rc != 0 and "ROLLBACK_REFUSED" in out, "التراجع يرفض معرّفًا ليس من الدفعة")
# فشل Qdrant في التراجع يُعلن لا يُبتلع
fx(); run("--ids-out", S + "/simout/ids3.txt")
rc, out = run("--rollback", S + "/simout/ids3.txt", extra={"FAKE_QDRANT_FAIL": "1"})
check(rc == 2 and "QDRANT_DELETE_FAILED" in out, "فشل حذف Qdrant يُعلَن برمز 2")
# تصادم بادئة
fx("collide"); hc = q(ALL)[0][0]
rc, out = run("--ids-out", S + "/simout/ids4.txt")
check(rc != 0 and "PREFIX_COLLISION" in out and q(ALL)[0][0] == hc, "تصادم البادئة يُسقط بلا أثر")
print("%d/%d" % (sum(ok), len(ok))); print("SIM_REFMISSING_PASS" if all(ok) else "SIM_REFMISSING_FAIL")
