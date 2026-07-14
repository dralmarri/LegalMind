"""طبقة التطبيع — المدخل الوحيد لأي مصدر قانوني.

    أي مصدر (DOCX | PDF | TXT | Markdown | HTML)
        ↓  normalize()
    Canonical Markdown
        ↓  استخراج المعرفة
    Knowledge Objects → PostgreSQL → Qdrant

قاعدة حاكمة: لا يقرأ أي كود بعد هذه الطبقة الملف الأصلي.
الاستخراج يرى الصيغة الموحدة فقط، فلا يعرف — ولا يجوز أن يعرف — صيغة المصدر.
"""
from __future__ import annotations

from pathlib import Path

from .canonical import NORMALIZER_VERSION, CanonicalDocument, build, normalize_text
from .readers import READERS, SUPPORTED_EXTENSIONS, UnsupportedSource

__all__ = [
    "CanonicalDocument",
    "NORMALIZER_VERSION",
    "SUPPORTED_EXTENSIONS",
    "UnsupportedSource",
    "normalize",
    "normalize_text",
]


def normalize(path: Path) -> CanonicalDocument:
    """يحول أي مصدر مدعوم إلى Canonical Markdown."""
    suffix = path.suffix.lower()
    entry = READERS.get(suffix)
    if entry is None:
        supported = "، ".join(sorted(SUPPORTED_EXTENSIONS))
        raise UnsupportedSource(f"الصيغة {suffix} غير مدعومة. المدعوم: {supported}")

    source_format, reader = entry
    blocks, warnings = reader(path)
    document = build(
        blocks,
        source_format=source_format,
        raw=path.read_bytes(),
        source_name=path.name,
        warnings=warnings,
    )

    if not document.body.strip():
        raise UnsupportedSource(
            f"المصدر {path.name} أنتج نصًا فارغًا بعد التطبيع. لا يُقبل مصدر بلا نص."
        )
    return document
