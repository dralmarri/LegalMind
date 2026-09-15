# P2.1 Closure Measurement — التقرير الشامل النهائي

**التاريخ:** 2026-09-15. **نقطة التجميد المرجعية:** P2.1A `601107b303a3a400f57c27f2e0b9c41d62614de3` — Shadow B runner `fa39c83`.
**قيود التجميد المُلتزَم بها طوال هذا القياس بالكامل:** لا قواعد A3 جديدة، لا retrieval mechanisms جديدة، لا Hybrid/BM25، لا تغييرات ميزانية، لا تغييرات مرتِّب، لا إصلاح لأي فشل ظهر أثناء القياس، لا تفعيل إنتاجي، لا توسعة قواعد مبنية على النتائج.
**Gold Set المجمَّد (الحقيقة الأرضية المستقلة):** SHA-256 `0ef4ddb91fa51695f130ab7da07af2656c5e001d0ba0819186ec3d291e98588d` — 40 حالة، 142 بُعدًا (`133 verified` / `7 partially_verified` / `2 unresolved`)، مؤلَّفة بمنهج **أعمى** (بلا اطلاع على أي مُخرَج Backbone/Shadow) + تحقُّق MCP مباشر لكل سند.

---

## 1) Baseline

### 1.1 Search Coverage
من 7 ظهورات A3 مُفعَّلة عبر التشغيلة الرئيسية لـShadow B: **6/7 (85.7%)** وُجدت عبر قناة استرجاع حقيقية فعلية في الإنتاج (`chapter`×4، `bundle`×2)؛ **1/7** (`legis-1-2016-m30`، القضية `gs-0036`) لم تجدها أي قناة — لا الإنتاج الحقيقي ولا `broad_channel_search` المستقل الأوسع (`also_discovered_by=[]`).

### 1.2 Survival (الأداء الخام على الحقيقة الأرضية المستقلة، خط أساس كل تشغيلة)
| المقياس | خط أساس Shadow A | خط أساس Shadow B |
|---|---:|---:|
| Verified Dimension-Level Micro Recall | 81.62% | 80.88% |
| Critical-Dimension Recall | 85.85% | 83.96% |
| Case-Level Strict Scope Completeness | 50.00% (18/36) | 50.00% (18/36) |
| Critical Case Failure Count | 11 | 12 |

(الفارق الطفيف بين الخطين طبيعي — تشغيلتان حيّتان مستقلّتان، تذبذب اكتشاف معروف موثَّق سابقًا، لا خطأ قياس.)

### 1.3 استقرار 5x (previously_stable) — على مستوى الأربعين حالة كاملة
- **Pass B التاريخية** (20 حالة `hard`/`adversarial`، موثَّقة مسبقًا في `docs/retrieval_evaluation_consolidated_report.md §G`): 27 هدفًا قِيس عبر 17 حالة (3 استُبعدت تلقائيًا) — **20 مستقر (5/5) | 1 تذبذب طفيف (4/5) | 6 غير مستقر**.
- **Baseline20 الجديد** (20 حالة غير مغطاة سابقًا، بنفس منهجية `stability_metrics.py` بلا أي تعديل): 15 هدفًا قِيس عبر 11 حالة (9 استُبعدت تلقائيًا) — **11 مستقر (5/5) | 0 تذبذب طفيف | 4 غير مستقر**.
- **الإجمالي المُجمَّع:** 42 هدفًا قِيس عبر الأربعين حالة — **31 previously_stable (73.8%) | 1 تذبذب طفيف (2.4%) | 10 غير مستقر (23.8%)**.

**اكتشاف جديد غير مُصلَح (كما أمر المالك — سُجِّل كما هو):** `gs-0038` (`jprin-101-1995-f1574-ce8b49f13f`) — نفس المعرِّف المصحَّح تاريخيًا (تحقُّق مزدوج `search_legal`←`get_object` وقت Pass A، وساهم حينها في نجاح 41/42 Candidate Recall) — أظهر **0/5 اكتشاف تمامًا** في هذا القياس الخماسي الجديد. تناقض حقيقي بين نتيجة تشغيلة مفردة تاريخية وتكرار خماسي حالي، غير مُفسَّر، **غير مُصلَح، غير مُخمَّن سببه**.

### 1.4 previously_stable_mandatory_authorities (بوابة عدم الانحدار الرسمية)
```
previously_stable_mandatory_authorities_total               = 31
previously_stable_mandatory_authorities_survived_shadow_a    = 31
previously_stable_mandatory_authorities_survived_shadow_b    = 31
previously_stable_mandatory_authorities_lost_shadow_a        = 0
previously_stable_mandatory_authorities_lost_shadow_b        = 0
```
**تحقق مضاعف:** (أ) مقارنة مباشرة لـ11 هدف baseline20 الجديدة أظهرت 11/11 باقية في `shadow_a_final_context` **و**`shadow_b_final_context` معًا. (ب) فحص عام أوسع: `all_authorities_lost` (كل شيء فُقد من `current_final_context`، بصرف النظر عن التصنيف) = **صفر عبر كل الأربعين حالة في كلا التشغيلين** — يشمل بنيويًا العشرين هدفًا من Pass B التاريخية أيضًا. **البوابة: PASS.**

---

## 2) Shadow A

### 2.1 Admission Rescue
`m166`/`m167` (القضية `gs-0013`) — مُرقَّاتان عبر تصنيف A3 + حجز محدود، لا اعتمادًا على حظ القناة الكثيفة. **دليل مباشر عبر 8 مشاهدات حيّة مستقلة** (3 من التشغيلة الرئيسية + 5 من تكرار `gs-0013`×5): m166 = **0/8** بقاء طبيعي (تحتاج الحجز في كل مرة)، m167 = 6/8 بقاء طبيعي (أحيانًا يكفيها الاسترجاع العادي، لكن حين لا يكفي — 2/8 — الحجز يتداركها). في **كل الحالات الثمانية بلا استثناء**، كلتاهما وصلت `FINAL_CONTEXT=True`.

### 2.2 Lost Authorities
**صفر** — `all_authorities_lost=[]` في كل الأربعين حالة (Shadow A).

### 2.3 Context Delta
+1453 حرفًا (`gs-0013`) — صافي إضافة، لا حذف.

### 2.4 توزيع A1/A2/A3/S (التشغيلة الرئيسية)
| الطبقة | فريد | ظهورات |
|---|---:|---:|
| A1 (استشهاد صريح موضوعي) | 4 | 6 |
| A2 (XREF عمق واحد) | 0 | 0 |
| A3 (قاعدة اعتمادية مُقنَّنة) | 3 | 7 |
| S (مادة نفاذ/إصدار هيكلية) | 3 | 5 |

### 2.5 Anchor Precision
**10/10 = 100%** صحة وجود (تحقُّق MCP مباشر: `get_object`/`get_article` لكل معرِّف — نص مطابق حرفيًا في كل الحالات). بعد فصل S عن A1: **A1_substantive_anchor_precision = 4/4 = 100%** (الثلاثة الأخرى مواد نفاذ آلية صُنِّفت S بحقها، لا "خطأ" باقيًا في A1).

### 2.6 Mechanism Effect (مقارنة زوجية صحيحة، خط أساس Shadow A نفسه)
```
fixed_by_mechanism        = [gs-0013]
newly_failed_by_mechanism = []          ← صفر انحدار
still_failing_both        = 10 حالة (فجوات استرجاع عامة خارج نطاق القاعدتين المُقنَّنتين)
```

---

## 3) Shadow B

### 3.1 Discovery Rescue — m30 (السلسلة السببية الكاملة)
```
SCOPED=T → A3_TRIGGERED=T → CANDIDATE_GENERATED=T → RETRIEVED_OR_FETCHED=T
→ GOVERNING_VERIFIED=T → RESERVED=T → ADMITTED=T → FINAL_CONTEXT=T
```
`current_hit=False`، `authority_resolution_method=direct_id_fetch` (**لا استرجاعًا** — قراءة بالمعرِّف من PostgreSQL مباشرة)، `retrieval_channels=[]`، `also_discovered_by=[]`. **الصياغة الدقيقة المعتمدة (بأمر المالك):** *"m30 لم تُكتشف عبر أي من قنوات البحث الحالية في التشغيلات المختبرة، بما فيها broad_channel_search المستقل المستخدم في Shadow B. ضمن نطاق هذه التجربة، كان deterministic A3 dependency هو المسار الوحيد الذي أوصل m30 إلى final context."* `rescue_primary_cause=A3_dependency/deterministic_backbone`.

### 3.2 Admission Rescue
مطابق لـ§2.1 — Shadow B يرث نفس تصنيف/حجز m166/m167 حين تكون حاضرة في `hits` الحقيقية (الفارق الوحيد عن Shadow A هو معالجة الفجوة الكاملة لـm30).

### 3.3 Scope Recall مقابل required_dimensions المستقلة
| المقياس | القيمة |
|---|---:|
| Verified Dimension-Level Micro Recall | **82.35%** (112/136) |
| Critical-Dimension Recall | **85.85%** |
| Case-Level Strict Scope Completeness | **50.00% (18/36)** |
| Critical Case Failure Count | 11 |
| Unresolved (مُستبعَدة من كل مقام) | 2 (`gs-0010`, `gs-0015`) |
| Confirmed-Absent (ضوابط سلبية، مُحصاة منفصلة) | 4 |

**ملاحظة تفسيرية إلزامية:** هذا الرقم (82.35%) يقيس تغطية **الاسترجاع العام** لكامل الحقيقة الأرضية المستقلة (142 بُعدًا عبر 40 مسألة قانونية متنوعة) — **لا** يقيس أداء آلية P2.1 (A3/الحجز/الجلب المباشر) بمعزل، لأن تلك الآلية مصمَّمة حصرًا لبُعدين اثنين (`m30`، `m166/m167`). القياس العادل لأثر الآلية نفسها هو §3.7 أدناه.

### 3.4 Strict Case Scope Completeness
**18/36 = 50%** (الحالات الأربع المتبقية من الأربعين بلا أبعاد إيجابية وجوبية للقياس أصلًا).

### 3.5 Context Delivery
+617 حرفًا (`gs-0036`) — نص m30 الحقيقي وصل فعليًا للسياق، لا مجرد تصنيف بلا أثر.

### 3.6 Causal Funnels
مُفصَّلة كاملة في §3.1 (m30) و§2.1 (m166/m167)؛ صفر تناقض منطقي (`SHADOW_B_LOGIC_OK` مؤكَّد آليًا في كل تشغيلة).

### 3.7 Lost Authorities & Mechanism Effect (مقارنة زوجية صحيحة، خط أساس Shadow B نفسه)
```
all_authorities_lost      = صفر عبر كل الأربعين حالة
fixed_by_mechanism        = [gs-0036]
newly_failed_by_mechanism = []          ← صفر انحدار
still_failing_both        = 11 حالة (فجوات استرجاع عامة خارج نطاق القاعدتين المُقنَّنتين)
```

---

## 4) Stability

| السلطة | Discovery (تاريخي) | Survival (تاريخي) | مشاهدات هذه الجولة (8 مستقلة) | الخلاصة |
|---|---|---|---|---|
| `legis-1-2016-m30` | **0/5** (Pass A + Pass B) | 0/5 | 0/8 native (Shadow A/B)، `also_discovered_by=[]` حتى ببحث حر أوسع | **Discovery Failure صرف، حتمي — لا تذبذب** |
| `legis-38-1980-m166` | 5/5 | **0/5** | **0/8 native** (لم تنجُ ذاتيًا ولا مرة) | **Evidence Admission Failure صرف — أشد ثباتًا من العيّنة التاريخية الأصغر** |
| `legis-38-1980-m167` | 5/5 | 1/5 | 6/8 native | **Evidence Admission Failure متذبذبة — تنجو غالبًا، لا دومًا** |

**previously_stable must_find كلها:** 31/31 نجت في Shadow A و31/31 في Shadow B (§1.4) — صفر فقد.

---

## 5) Cost

*[يُستكمَل بعد تشغيل `cost_measurement_runner.py` حيًّا]*

---

## 6) Safety

- **False anchors:** صفر. 10/10 معرِّف A1/A3 (Shadow A+B) تحقَّق وجودها ونصها عبر MCP مباشرة (`get_object`/`get_article`) — مطابقة حرفية تامة.
- **Benchmark leakage checks:** `BENCHMARK_ISOLATION_PASS` — فحص آلي (`tools/benchmark_isolation_test.py`) يؤكد أن `required_dimensions` ممنوعة كليًا من كل الملفات الستة (4 ملفات قرار + مُشغِّلا Shadow)، وأن `must_find`/`must_not_miss` ممنوعتان تمامًا من ملفات القرار الأربعة (ومسموحتان في المُشغِّلين حصرًا خارج أي نداء فعلي لدوال القرار — إخراج بعدي فقط). **اختباران سلبيان متعمَّدان** (حقن `required_dimensions` في نسخة من `p2_backbone.py`، وحقن `must_find` داخل نداء فعلي لـ`admit()` في نسخة من `shadow_a_runner.py`) أثبتا أن البوابة تكتشف الانتهاك فعليًا، لا تمرّ صوريًا.
- **Production mutation checks:** `ISOLATION_TEST_PASS` (مؤكَّد سابقًا على `admin/app.py` الحي — صفر استيراد/إشارة لأي وحدة P2.1). كل عمليات Shadow A/B قراءة/جلب مباشر بلا أي كتابة على بيانات الإنتاج.
- **Rule isolation checks:** `shadow_candidate_rules.json` معزول فيزيائيًا عن أي ملف قواعد إنتاجي — لا وجود لملف قواعد إنتاجي مقابل أصلًا في هذه المرحلة (P2.1 بأكملها Offline Replay).

---

## 7) Remaining Gaps (كما هي، بلا إصلاح)

1. **`gs-0038` (§1.3):** تناقض حقيقي غير مُفسَّر بين تشغيلة Pass A المفردة (نجاح) وتكرار خماسي جديد (0/5 فشل تام). لم يُشخَّص السبب، لم يُصلَح.
2. **required_dimensions ذات `unresolved` (2):** `gs-0010` (افتراض غياب ابن/أب للمورث غير مصرَّح به في نص السؤال) و`gs-0015` (أساس اختصاص البنك المركزي الرقابي — لا نص تأسيسي مستقل في القاعدة). لم يُختلَق سند لأيٍّ منهما.
3. **7 أبعاد `partially_verified`:** تفاصيلها في ملف `required_dimensions` نفسه (مثال: `gs-0029` نطاق الاستثناءات الصريحة بعد تعديل 148/2025 — النص الحالي مؤكَّد الخلوّ من استثناء مسمًّى، لكن مقارنته بالنص السابق قبل التعديل غير مؤكَّدة لعدم توفر النسخة القديمة عبر الأدوات المتاحة).
4. **Strict Scope Completeness 50%:** يعكس فجوات استرجاع عامة واسعة في النظام، لا خللًا في آلية P2.1 نفسها (التي تستهدف بُعدين محدَّدين فقط من أصل 136). لم تُوسَّع قواعد A3 لمعالجة هذا — بأمر المالك الصريح بعدم توسعة القواعد بعد النتائج.
5. **عدم اكتمال قياس التكلفة الزمني الدقيق حتى وقت كتابة هذا القسم** (§5) — يُستكمَل عند توفر بيانات `cost_measurement_runner.py`.

---

## 8) Decision Matrix

| البُعد | التقييم |
|---|---|
| Deterministic Backbone | **PASS** — 40/40 حالة، بصمة واحدة فريدة لكل حالة عبر 5 تكرارات مستقلة |
| Discovery Rescue | **PASS** — m30 مثبَّتة تجريبيًا (السلسلة السببية الكاملة + غياب تام عن كل قنوات البحث الحقيقية بما فيها بحث حر مستقل) |
| Evidence Admission | **PASS** — m166/m167 مُحجَزتان بصرف النظر عن درجة الاسترجاع، 8/8 مشاهدات بلا استثناء |
| Anchor Precision | **PASS** — 10/10 = 100% صحة وجود، مطابقة نصية تامة عبر MCP |
| Legal Scope Coverage | **UNKNOWN (جزئي)** — 82.35% ميكرو ريكول عام يعكس النظام الأوسع لا آلية P2.1 تحديدًا؛ مقياس أثر الآلية نفسها إيجابي (PASS) لكنه ضيّق النطاق (بُعدان من 136) |
| No-Regression | **PASS** — صفر فقد من أي نوع (previously_stable وغير ذلك)، صفر `newly_failed_by_mechanism` في كلا التشغيلين |
| Retrieval Stability | **PASS (جزئي، بحد معرفي معلن)** — previously_stable=73.8% إجمالًا، والفجوة المتبقية (m167 التذبذب، gs-0038) موثَّقة لا مُصلَحة |
| Temporal Safety | **UNKNOWN** — لم يُختبَر مباشرة في نطاق قياس الإغلاق هذا (خارج القواعد المُقنَّنتين الحاليتين) |
| Search Exhaustion Safety | **PASS** — `broad_channel_search` أثبت أن غياب m30 حقيقي لا ناتج عن قصور بحث غير مُستنفَد |
| Runtime Cost | **UNKNOWN** — بيانات القياس الزمني الدقيق غير مكتملة بعد (§5) |
| Production Isolation | **PASS** — `ISOLATION_TEST_PASS` + `BENCHMARK_ISOLATION_PASS` معًا، مؤكَّدان باختبارات سلبية متعمَّدة |

### التوصية النهائية

**B — More measurement required.**

**التبرير:** النتائج الجوهرية (Deterministic Backbone، Discovery Rescue، Evidence Admission، Anchor Precision، No-Regression، Production Isolation) كلها PASS نظيف وقوي بأدلة مباشرة متكررة. لكن ثلاثة أبعاد تبقى UNKNOWN أو غير مكتملة القياس (Legal Scope Coverage الواسع، Temporal Safety، Runtime Cost)، وفجوة `gs-0038` غير المُفسَّرة تستحق تشخيصًا مستقلًا قبل أي حكم نهائي. **لا يُنفَّذ الخيار A حتى لو بدا مُرجَّحًا — القرار بالكامل يبقى للمالك.**
