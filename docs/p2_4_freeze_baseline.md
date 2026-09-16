# P2.4 — تجميد الأساس المرجعي (Freeze) قبل أي تصميم/تجربة

**التاريخ:** 2026-09-17. **الحالة: توثيق تجميد بحت — صفر عمل تجريبي في هذا الملف.**

جميع القيم أدناه مؤكَّدة من `git log` على الفرع `claude/kuwaiti-legal-docs-qq0cx3` مباشرة قبل
بدء أي عمل خاص بـP2.4، وتبقى **ثابتة** طوال هذه الجولة كاملةً. أي مقارنة "قبل/بعد" في أي ذراع
تُقاس دومًا مقابل هذا الأساس بالذات.

## 1) التزامات P2.1 (الأساس المعماري الأصلي)

| الالتزام | الوصف |
|---|---|
| `601107b303a3a400f57c27f2e0b9c41d62614de3` | P2.1A — طبقة S + إزالة حقن العزل (نقطة التجميد المرجعية الأصلية) |
| `fa39c83` | Shadow B runner — فصل `retrieved` عن `direct_fetched` |

## 2) Gold Set المجمَّد (الحقيقة الأرضية المستقلة)

```
SHA-256: 0ef4ddb91fa51695f130ab7da07af2656c5e001d0ba0819186ec3d291e98588d
40 حالة، 142 بُعدًا (133 verified / 7 partially_verified / 2 unresolved)
مؤلَّفة بمنهج أعمى (بلا اطلاع على أي مُخرَج Backbone/Shadow) + تحقُّق MCP مباشر لكل سند.
```

**ملزم لكل هذه الجولة (P2.4):** هذا الملف **لا يُعدَّل بعد رؤية أي نتيجة تجريبية** — أي تصحيح
حقيقي مكتشَف أثناء P2.4 (مثال: خطأ في `required_dimensions`) يُسجَّل في هذا التقرير كملاحظة
منفصلة، ولا يُطبَّق على الملف الحي إلا في جولة مستقلة لاحقة بعد انتهاء كل قياسات P2.4.

## 3) تقارير P2.2 وP2.3 (المرجع التشخيصي الكامل لكل ذراع)

| الملف | الالتزام | الموضوع |
|---|---|---|
| `docs/p2_2_coverage_gap_analysis_report.md` | `0ce06a0` (+تصحيح صياغي `73dffd5`) | 24 بُعدًا مفقودًا، تصنيف فشل أول، القمع الخماسي |
| `docs/p2_3_stable_failure_attribution_report.md` | `d9acfd9` | تصنيف فشل مستقر 5x، Frozen Axes سببي، حقن Oracle، القمع المقابل للواقع |

**الإخفاقات الحرجة التسعة (P2.2 §7 + P2.3 §3) — المرجع الثابت لكل قياس Arm A/B لاحق:**

| Authority | التصنيف النهائي (P2.3) |
|---|---|
| `legis-38-1980-m166` | STABLE_DISCOVERY_FAILURE |
| `legis-38-1980-m167` | STABLE_DISCOVERY_FAILURE |
| `regl-1-2016-m65` | INTERMITTENT_PRE_RERANK_CAP_FAILURE |
| `legis-51-1984-m299` | AXIS_DEPENDENT_DISCOVERY_FAILURE (مؤكَّد سببيًا) |
| `legis-51-1984-m300` | MIXED_FAILURE (axis-dependent + cap) |
| `legis-51-1984-m337` | STABLE_SCOPE_FAILURE |
| `legis-51-1984-m338` | STABLE_RANKING_FAILURE |
| `legis-20-2015-m49` | INTERMITTENT_PRE_RERANK_CAP_FAILURE |
| `legis-38-1980-m103` | MIXED_FAILURE (axis-dependent, ثنائي القناة) |

## 4) أدوات التشخيص القائمة (P2.2/P2.3) — تُستعمَل بلا تعديل كمراجع/أنماط في P2.4

`tools/coverage_gap_diagnostic.py`، `tools/frozen_axes_experiment.py`،
`tools/p23_stable_failure_matrix.py`، `tools/p23_oracle_injection.py`،
`tools/p23_frozen_axes_causal.py`. كلها أدوات تشخيص مستقلة عن مسار الإنتاج (لا تُستورَد من
`admin/app.py`)، ونمط التصحيح المؤقت (monkey-patch try/finally) المُثبَت فيها هو الأساس الذي
تُبنى عليه البنية التحتية المشتركة لـP2.4 (`tools/p24_offline_pipeline.py`).

## 5) بنية `_draft_build_context` الحقيقية المؤكَّدة حيًّا (مرجع حرفي لـP2.4-Infra)

المصدر الكامل (280 سطرًا) استُخرِج حيًّا في P2.3 (`dump_source.py`، 2026-09-16) ومحفوظ في
سياق الجلسة؛ يتضمن التسلسل الدقيق: `best` (دِنس عبر `_draft_search`) → دمج تكرار المبادئ
(P0-4) → **السقف الثابت `caps_n`** (نقطة تدخل Arm A الوحيدة) → قنوات bundle/direct/chapter/
lexical/xref/sibling/prin_xref → `_draft_rerank` → دمج الدرجات → ترتيب `ordered` → حلقة
الميزانية `LBL_BUDGET`. أي إعادة بناء offline لهذا التسلسل في P2.4 يجب أن تطابقه حرفيًا فيما
عدا نقطة السقف وحدها (Arm A) — أي انحراف آخر يُفسد صحة المقارنة.

## 6) قيود التجميد الملزمة لكل P2.4 (بأمر المالك، حرفيًا)

- لا تعديل على Gold Set بعد رؤية أي نتيجة تجريبية.
- لا قواعد خاصة بحالة بعينها (`case_id`-specific rules).
- لا قواعد مشتقة من معرِّف سلطة فاشلة بعينها (`authority-ID rules` من الإخفاقات).
- لا BM25/Hybrid في هذه الجولة.
- لا رفع للميزانية (`LBL_BUDGET`).
- لا تغيير في سلوك الإنتاج (`admin/app.py` يبقى بلا مساس تمامًا طوال P2.4 كاملة).

**تأكيد:** `admin/app.py` لم يُلمَس بأي تعديل منذ بداية P2.1 وحتى هذه اللحظة — كل عمل P2.1/
P2.2/P2.3/P2.4 جرى حصرًا في وحدات `tools/*.py` تشخيصية مستقلة تستهلك دوال الإنتاج الحقيقية
عبر `import` وتصحيح مؤقت (monkey-patch)، بلا أي `git diff` على `admin/`.
