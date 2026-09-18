# -*- coding: utf-8 -*-
"""قنوات توليد المرشحين — كلها تعمل على **الطبقات الثلاث** لا على التشريع وحده.

كل قناة تستقبل اعتمادياتها دوالَّ محقونة (`search_fn` / `db_rows` / `embed_fn`)
فتُختبر بمزيّفات بلا قاعدة بيانات، وتُوصَل بدوال الإنتاج على الخادم.

القاعدة المشتركة: **كل قناة تولّد مرشحين ولا تقرر قبولًا.** القرار لاحقٌ
(دمج ← تقييم علاقة/زمن ← ترتيب ← قبول). فوسعُ القناة هنا فضيلةٌ لا خطر، ما دام
ما بعدها يصفّي؛ وهذا عكس الخط القائم الذي كان يقصّ داخل القناة نفسها قبل أي
تقييم."""
import re
from . import model as T

try:
    import kb_types as _kb
except Exception:                                   # نسخة احتياطية للاختبار
    class _kb:                                      # pragma: no cover
        LEGISLATION_TYPES = ("legislation_article", "legislation",
                             "legislation_issuing_article",
                             "legislation_preamble", "legislation_archived")
        PRINCIPLE_TYPES = ("judicial_principle", "judicial_principles_collection")
        JUDGMENT_TYPES = ("full_judgment",)
        TEMPLATE_TYPES = ("judicial_template",)

LAYER_OF_TYPES = [
    (tuple(_kb.LEGISLATION_TYPES), T.LAYER_LEGISLATION),
    (tuple(_kb.PRINCIPLE_TYPES),   T.LAYER_PRINCIPLE),
    (tuple(_kb.JUDGMENT_TYPES),    T.LAYER_JUDGMENT),
    (tuple(_kb.TEMPLATE_TYPES),    T.LAYER_TEMPLATE),
]


def layer_of_type(ot):
    for tys, lay in LAYER_OF_TYPES:
        if ot in tys:
            return lay
    return ""


# ---------------------------------------------------------------- dense
def dense(pool, search_fn, vectors, depth, layers=None):
    """بحث متجهي متعدد المحاور على **كل طبقة** بعمق واحد.

    الفرق البنيوي عن الإنتاج: هناك كانت الأحكام الكاملة تُطلب مرتين فقط على
    الاستعلام الكامل ولا تُطلب على أي محور فرعي إطلاقًا، والنماذج كذلك — فكانت
    طبقة الأحكام محرومة هيكليًا من التمثيل (قياس P2.7-O: صفر حكم كامل عبر خمس
    مراسٍ). هنا كل محور يسأل الطبقات الأربع بالعمق نفسه."""
    plans = layers or [
        (list(_kb.LEGISLATION_TYPES), T.LAYER_LEGISLATION),
        (list(_kb.PRINCIPLE_TYPES),   T.LAYER_PRINCIPLE),
        (list(_kb.JUDGMENT_TYPES),    T.LAYER_JUDGMENT),
        (list(_kb.TEMPLATE_TYPES),    T.LAYER_TEMPLATE),
    ]
    for vec in vectors:
        for tys, lay in plans:
            try:
                hits = search_fn(vec, tys, depth) or []
            except Exception:
                continue
            for i, h in enumerate(hits, 1):
                p = h.get("payload") or {}
                oid = p.get("object_id")
                if oid:
                    pool.add(oid, T.CH_DENSE, i, float(h.get("score") or 0.0), lay)
    return pool


# -------------------------------------------------------------- lexical
_WORD = re.compile(r"[ء-ي]{4,}")


def lexical(pool, db_rows, phrases, per_phrase=12, types=None):
    """بحث معجمي على الطبقات الثلاث — لا على التشريع وحده.

    `kb_types.LEXICAL_TYPES` كان مساويًا لـLEGISLATION_TYPES، أي أن القناة
    المعجمية **لم تكن تعيد مبدأً ولا حكمًا قط**. وهذا أحد وجهي تهميش القضاء
    البنيوي الموثَّق في §26 (P2.7-J)."""
    tys = list(types or (tuple(_kb.LEGISLATION_TYPES) + tuple(_kb.PRINCIPLE_TYPES)
                         + tuple(_kb.JUDGMENT_TYPES)))
    for ph in phrases:
        words = _WORD.findall(ph or "")[:6]
        if not words:
            continue
        like = " AND ".join(["normalized_text LIKE %s"] * len(words))
        sql = ("SELECT id, object_type FROM knowledge_objects WHERE object_type = ANY(%s) "
               "AND " + like + " ORDER BY id LIMIT %s")
        try:
            rows = db_rows(sql, tuple([tys] + ["%" + w + "%" for w in words]
                                      + [per_phrase]))
        except Exception:
            continue
        for i, r in enumerate(rows or [], 1):
            pool.add(r.get("id"), T.CH_LEXICAL, i, 0.0,
                     layer_of_type(r.get("object_type")))
    return pool


# ------------------------------------------------------------- citation
_LAWREF = re.compile(r"(?:رقم\s*)?\(?\s*(\d{1,3})\s*\)?\s*(?:لسنة|/)\s*(\d{4})")
# اللفظ الكامل يُقبل ولو سبقته واو أو فاء («والمادة 144»)؛ والنفي الخلفي مقصور
# على الحرف المفرد «م» وحده — وإلا التقط «رقم 5947» مادةً 594 (عيب موثَّق).
_ARTNUM = re.compile(
    r"(?:المواد|المادتين|المادتان|المادة|الماده|مادة|ماده"
    r"|(?<![ء-ي])م)\s*\(?\s*(\d{1,4})")
# قائمة أرقام بعد «المواد 57، 61، 63 و196» — الأرقام التالية بلا بادئة فتضيع
_ARTSEQ = re.compile(r"(?:المواد|المادتين|المادتان)\s*\(?\s*"
                     r"((?:\d{1,4}\s*(?:[،,]|و)?\s*){2,})")
# مدى «من 56 إلى 61» — الإحالات التشريعية تُكتب بالمدى فيسقط ما بين طرفيه
_ARTRNG = re.compile(r"من\s*\(?\s*(\d{1,4})\s*\)?\s*(?:إلى|الى|حتى)\s*\(?\s*(\d{1,4})")


def article_numbers(text, range_cap=12):
    """كل أرقام المواد في نصٍّ: المفردة والقوائم والمديات معًا."""
    t = text or ""
    out = [m.group(1) for m in _ARTNUM.finditer(t)]
    for m in _ARTSEQ.finditer(t):
        out += re.findall(r"\d{1,4}", m.group(1))
    for a, b in _ARTRNG.findall(t):
        a, b = int(a), int(b)
        if 0 < b - a <= range_cap:
            out += [str(x) for x in range(a, b + 1)]
    seen, uniq = set(), []
    for x in out:
        if x not in seen:
            seen.add(x); uniq.append(x)
    return uniq
_APPEAL = re.compile(r"الطعن(?:ان|ين)?\s*(?:رقم\s*)?\(?\s*(\d{1,5})\s*\)?\s*"
                     r"(?:لسنة|/)\s*(\d{4})")


def citation(pool, db_rows, text, resolve_law_prefix=None):
    """الاستشهاد الصريح: أرقام مواد **وأرقام طعون** معًا.

    الشق الجديد: رقم الطعن. الإنتاج كان يحلّ أرقام **القوانين والمواد** فقط
    (`DIRECT_CITATION_TYPES = LEGISLATION_TYPES`)، فسؤالٌ يسمّي طعنًا بالحرف لا
    يجلب مبدأه إلا مصادفةً عبر المتجه. وهي أدقّ قناة ممكنة: المستخدم سمّى
    المصدر بنفسه."""
    t = text or ""
    laws = _LAWREF.findall(t)
    arts = article_numbers(t)
    n = 0
    if laws and arts and resolve_law_prefix:
        for (num, yr) in laws[:8]:
            pref = resolve_law_prefix(num, yr)
            if not pref:
                continue
            for a in arts[:24]:
                n += 1
                pool.add(pref + "m" + a, T.CH_CITATION, n, 1.0,
                         T.LAYER_LEGISLATION, pinned=True)
    for (num, yr) in _APPEAL.findall(t)[:10]:
        sql = ("SELECT id, object_type FROM knowledge_objects "
               "WHERE object_type = ANY(%s) AND normalized_text LIKE %s LIMIT 12")
        pat = "%" + num + "%" + yr + "%"
        try:
            rows = db_rows(sql, (list(_kb.PRINCIPLE_TYPES) + list(_kb.JUDGMENT_TYPES), pat))
        except Exception:
            continue
        for i, r in enumerate(rows or [], 1):
            pool.add(r.get("id"), T.CH_CITATION, i, 1.0,
                     layer_of_type(r.get("object_type")), pinned=True)
    return pool


# ------------------------------------------------------------ adjacency
_ID_ART = re.compile(r"^(.*-)m(\d{1,4})(?:-|$)")


def law_prefix_of(object_id):
    m = _ID_ART.match(object_id or "")
    return m.group(1) if m else None


def adjacency(pool, db_rows, anchor_ids, window=4):
    """الجوار البنيوي داخل القانون نفسه — **بترتيب القاعدة لا بحسابٍ رقمي**.

    الفرق جوهري ومقصود: لا يُبنى مدى ±N على رقم المادة (يخطئ مع الثغرات ومواد
    «مكرر»)؛ تُقرأ **قائمة مواد القانون الفعلية من القاعدة مرتَّبةً**، ويُؤخذ
    الجارُ بموضعه الترتيبي. وهذه قناة **توليد مرشحين** لا آلية علاقة: وزنها
    أدنى الأوزان، وكل ما تولّده يمرّ على تقييم العلاقة والمرتِّب مثل غيره.
    (التمييز مهم: ما رُفض سابقًا هو الجوار الرقمي بوصفه **تفسيرًا لعلاقة**،
    لا بوصفه مولّدًا عالي التغطية يُصفّى بعده.)"""
    n = 0
    for aid in anchor_ids:
        pref = law_prefix_of(aid)
        if not pref:
            continue
        m = _ID_ART.match(aid)
        try:
            rows = db_rows(
                "SELECT id FROM knowledge_objects WHERE id LIKE %s "
                "AND object_type = ANY(%s) ORDER BY id",
                (pref + "m%", list(_kb.LEGISLATION_TYPES)))
        except Exception:
            continue
        ids = [r.get("id") for r in (rows or []) if r.get("id")]

        def artno(i):
            mm = _ID_ART.match(i)
            return int(mm.group(2)) if mm else 10 ** 9
        ids.sort(key=artno)
        if aid not in ids:
            continue
        pos = ids.index(aid)
        for j in range(max(0, pos - window), min(len(ids), pos + window + 1)):
            if ids[j] == aid:
                continue
            n += 1
            pool.add(ids[j], T.CH_ADJACENCY, abs(j - pos), 0.0,
                     T.LAYER_LEGISLATION)
    return pool


# --------------------------------------------------------- judgment link
def judgment_link(pool, db_rows, principle_ids, limit=24):
    """كل مبدأ مسترجَع يجرّ **حكمه الأم** عبر metadata.source_judgment_id.

    هذه القناة تعالج مباشرةً أحدّ نتائج P2.7-O: صفر حكم كامل اكتُشف عبر خمس
    مراسٍ و19 مسارًا لكل مرساة. الحكم الكامل لا يصله التشابه اللفظي غالبًا
    (لغته وقائعية طويلة) لكنه مربوط بالمبدأ برابط **بنيوي صريح في القاعدة**،
    وهذا الرابط كان غير مستعمَل في الاسترجاع إطلاقًا."""
    ids = [i for i in principle_ids if i][:200]
    if not ids:
        return pool
    try:
        rows = db_rows(
            "SELECT id, metadata->>'source_judgment_id' AS jid FROM knowledge_objects "
            "WHERE id = ANY(%s) AND metadata->>'source_judgment_id' IS NOT NULL",
            (ids,))
    except Exception:
        return pool
    seen, n = set(), 0
    for r in rows or []:
        jid = r.get("jid")
        if not jid or jid in seen or n >= limit:
            continue
        seen.add(jid)
        n += 1
        pool.add(jid, T.CH_JUDGMENT, n, 0.0, T.LAYER_JUDGMENT)
    return pool
