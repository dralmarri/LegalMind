# مخطط الكائنات المعرفية

## الحقول المشتركة
```yaml
id:
type:
branch:
topic:
subtopic:
micro_issue:
title:
source_title:
source_classification:
original_text:
normalized_text:
keywords: []
positive_links: []
negative_links: []
temporal_scope:
use_case: []
not_for_use: []
verification_status:
source_reference:
created_at:
updated_at:
batch_id:
```

## التشريع
```yaml
id: LEG-<BRANCH>-<LAW>-<YEAR>-ART-<ARTICLE>
type: legislation
law_type:
law_number:
law_year:
law_name:
article_number:
official_text:
effective_from:
effective_to:
amendments: []
repealed_by:
related_principles: []
related_rules: []
related_templates: []
```

## المبدأ القضائي
```yaml
id: JUR-<BRANCH>-<TOPIC>-<SEQUENCE>
type: judicial_principle
principle_text:
appeal_number:
appeal_year:
appeal_type:
circuit:
hearing_date:
volume:
page:
explicit_articles: []
explicit_laws: []
rule_role:
historical_limit:
current_relevance:
```

## القاعدة الجامعة
```yaml
id: RULE-<BRANCH>-<TOPIC>-<SEQUENCE>
type: synthesized_rule
rule_text:
scope:
conditions: []
exceptions: []
supported_by: []
contrary_sources: []
historical_limit:
confidence:
verification_status: machine_pending_human
```

## النموذج القضائي
```yaml
id: TPL-<BRANCH>-<TOPIC>-<TYPE>-<SEQUENCE>
type: judicial_template
template_type:
court:
party_position:
required_facts: []
required_documents: []
editable_fields: []
conditional_sections: []
legal_basis: []
supporting_principles: []
available_defenses: []
alternative_requests: []
procedural_warnings: []
template_body:
```
