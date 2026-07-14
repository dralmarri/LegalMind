"""Canonical Markdown — الصيغة الموحدة الوحيدة التي يراها مستخرج المعرفة.

كل مصدر قانوني، أيًا كانت صيغته، يتحول هنا إلى نص واحد موحد.
ما بعد هذه الطبقة لا يعرف شيئًا عن DOCX أو PDF أو HTML.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone

NORMALIZER_VERSION = 1

TATWEEL = "ـ"
INVISIBLE_RE = re.compile(r"[​-‏‪-‮⁦-⁩﻿]")


@dataclass
class CanonicalDocument:
    """المخرج الوحيد لطبقة التطبيع."""

    body: str
    source_format: str
    source_sha256: str
    source_name: str
    normalized_at: str
    normalizer_version: int = NORMALIZER_VERSION
    warnings: list[str] = field(default_factory=list)

    def front_matter(self) -> dict:
        return {
            "source_name": self.source_name,
            "source_format": self.source_format,
            "source_sha256": self.source_sha256,
            "normalized_at": self.normalized_at,
            "normalizer_version": self.normalizer_version,
            "warnings": self.warnings,
        }

    def to_markdown(self) -> str:
        """الصيغة المؤرشفة على القرص — نص المصدر بعد التطبيع مع ترويسة تدقيق."""
        lines = ["---"]
        for key, value in self.front_matter().items():
            if isinstance(value, list):
                lines.append(f"{key}:" + ("" if value else " []"))
                lines.extend(f"  - {item}" for item in value)
            else:
                lines.append(f"{key}: {value}")
        lines.append("---")
        lines.append("")
        lines.append(self.body)
        return "\n".join(lines)


def normalize_text(text: str) -> str:
    """قواعد التطبيع الموحدة. تُطبق على كل صيغة بلا استثناء."""
    text = unicodedata.normalize("NFKC", text)
    text = INVISIBLE_RE.sub("", text)
    text = text.replace(TATWEEL, "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def build(blocks: list[str], *, source_format: str, raw: bytes, source_name: str,
          warnings: list[str] | None = None) -> CanonicalDocument:
    """يبني المستند الموحد من كتل نصية استخرجها قارئ الصيغة."""
    body = normalize_text("\n".join(block for block in blocks if block.strip()))
    return CanonicalDocument(
        body=body,
        source_format=source_format,
        source_sha256=hashlib.sha256(raw).hexdigest(),
        source_name=source_name,
        normalized_at=datetime.now(timezone.utc).isoformat(),
        warnings=list(warnings or []),
    )
