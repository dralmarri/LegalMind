#!/bin/bash
# أمر آلي 4: تمييز أخطاء الرصيد/المصادقة عن أخطاء المراجعة، وعدم حرق محاولات النصوص عندها
set -e
python3 - <<'PYEOF'
# -*- coding: utf-8 -*-
p = "/opt/LegalMind/tools/reviewer.py"
src = open(p, encoding="utf-8").read()

OLD_ERR = '''            print("    HTTP %s: %s" % (e.code, msg), flush=True)
            if e.code == 400:
                return [], "too_long"
            time.sleep(20 * (attempt + 1))'''
NEW_ERR = '''            print("    HTTP %s: %s" % (e.code, msg), flush=True)
            low = msg.lower()
            if ("credit balance" in low or "billing" in low or "payment" in low
                    or "quota" in low or e.code in (401, 402, 403)):
                return [], "api_down"
            if e.code == 400:
                return [], "too_long"
            time.sleep(20 * (attempt + 1))'''
if OLD_ERR in src:
    src = src.replace(OLD_ERR, NEW_ERR, 1)
    print("رُكّب تمييز أخطاء الرصيد ✓")
elif "api_down" in src:
    print("مركب مسبقاً")

OLD_MSG = 'msg = e.read().decode("utf-8", "replace")[:200]'
src = src.replace(OLD_MSG, 'msg = e.read().decode("utf-8", "replace")[:300]', 1)

OLD_RG = '''        unresolved = []
        for vd in vds:
            apply(vd, by_id, unresolved)
        for oid, row in by_id.items():          # لم يصله حكم — يُحتسب ولا يُهمل
            stats["silent"] += 1
            bump(oid, "no_verdict:%s" % (err or "partial"))
        return unresolved'''
NEW_RG = '''        unresolved = []
        if err == "api_down":                   # عطل رصيد/مصادقة: لا نحرق محاولات النصوص
            stats["api_down"] = stats.get("api_down", 0) + 1
            raise RuntimeError("API_DOWN")
        for vd in vds:
            apply(vd, by_id, unresolved)
        for oid, row in by_id.items():          # لم يصله حكم — يُحتسب ولا يُهمل
            stats["silent"] += 1
            bump(oid, "no_verdict:%s" % (err or "partial"))
        return unresolved'''
if OLD_RG in src:
    src = src.replace(OLD_RG, NEW_RG, 1)
    print("رُكّب التوقف الذاتي عند العطل ✓")

OLD_CATCH = '''        except Exception as exc:
            print("  خطأ %s: %s" % (BID, str(exc)[:130]), flush=True)'''
NEW_CATCH = '''        except RuntimeError as exc:
            if "API_DOWN" in str(exc):
                print("  توقف مؤقت: المحرك لا يستجيب (رصيد/مصادقة) — الجولة القادمة تعيد المحاولة تلقائياً",
                      flush=True)
                break
            print("  خطأ %s: %s" % (BID, str(exc)[:130]), flush=True)
        except Exception as exc:
            print("  خطأ %s: %s" % (BID, str(exc)[:130]), flush=True)'''
if OLD_CATCH in src:
    src = src.replace(OLD_CATCH, NEW_CATCH, 1)
    print("رُكّب الخروج الآمن ✓")

open(p, "w", encoding="utf-8").write(src)
PYEOF

/opt/LegalMind/.venv/bin/python -m py_compile /opt/LegalMind/tools/reviewer.py && echo "الكود سليم ✓"

# إرجاع المحاولات التي أُحرقت بسبب أعطال الاتصال لا بسبب النص نفسه
docker exec legalmind-postgres psql -U legalmind -d legalmind -c \
  "UPDATE knowledge_objects
   SET metadata = metadata - 'review_attempts'
   WHERE verification_status='machine_pending_human'
     AND coalesce(metadata->>'review_last_note','') LIKE 'no_verdict:%';"

# فحص حالة المحرك الآن ونشره في التقرير
set -a; source /opt/LegalMind/deploy/.env; set +a
CODE=$(curl -s -o /tmp/anthcheck.json -w '%{http_code}' https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" -H 'anthropic-version: 2023-06-01' \
  -H 'content-type: application/json' \
  -d '{"model":"claude-sonnet-5","max_tokens":8,"messages":[{"role":"user","content":"مرحبا"}]}')
{
  echo "=== فحص محرك القراءة — $(date -u +%F' '%T) UTC ==="
  if [ "$CODE" = "200" ]; then
    echo "الحالة: يعمل ✓ (لا مشكلة رصيد) — المراجعة مستمرة تلقائياً"
  else
    echo "الحالة: متوقف ✗ | رمز: $CODE"
    echo "الرسالة:"; head -c 400 /tmp/anthcheck.json; echo
    echo ""
    echo "المطلوب منك: console.anthropic.com ← Billing ← Retry payment (أو Buy credits)"
    echo "وبمجرد نجاح الدفع تستأنف المراجعة وحدها خلال 20 دقيقة بلا أي تدخل."
  fi
  echo ""
  [ -f /root/review-final.txt ] && cat /root/review-final.txt
} > "/var/www/legalmind-v3/review-$(cat /opt/legalmind-autopilot/token).txt"
rm -f /tmp/anthcheck.json
echo "اكتمل التحصين ونُشرت حالة المحرك في رابط التقرير"
