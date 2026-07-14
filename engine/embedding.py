#!/usr/bin/env python3
"""مكوّن التضمين الموحد — النقطة المركزية الوحيدة لإعدادات النموذج.

قرار معماري (2026-07-14): `hash_embedding` **محظور**. لم يكن نموذج تضمين،
بل hashing trick على SHA-256، فكانت «الحضانة» و«رعاية المحضون» متجهين
شبه متعامدين — أي أن المرادفات القانونية العربية لا تُسترجع أبدًا.

اسم النموذج وحجم المتجه واسم الـcollection تُقرأ **من هنا فقط**.
لا تُكرَّر في أي ملف آخر (بند «أولًا»).

صيغة E5 إلزامية: النص المفهرس `passage: ...` والاستعلام `query: ...`.
تضمين نص بلا بادئة يفسد فضاء المتجهات.
"""
from __future__ import annotations

import hashlib
import os
import threading
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

# ── الإعدادات المركزية ──────────────────────────────────────────────
PROVIDER = "huggingface_local"
MODEL_ID = os.getenv("LEGALMIND_EMBEDDING_MODEL", "intfloat/multilingual-e5-base")
VECTOR_SIZE = int(os.getenv("LEGALMIND_EMBEDDING_DIM", "768"))
DISTANCE = "Cosine"
EMBEDDING_MODE = "dense"
EMBEDDING_VERSION = 1
COLLECTION = os.getenv("LEGALMIND_COLLECTION", "legalmind_multilingual_e5_base_v1")

# الـcollection القديمة — للقراءة/المقارنة فقط. الكتابة فيها محظورة.
LEGACY_COLLECTION = "legalmind_objects_v1"

QUERY_PREFIX = "query: "
PASSAGE_PREFIX = "passage: "

_model = None
_lock = threading.Lock()


@dataclass(frozen=True)
class EmbeddingMeta:
    """تُحفظ مع كل نقطة مفهرسة (بند «أولًا»)."""

    embedding_model: str
    embedding_dimension: int
    embedding_version: int
    embedded_at: str
    source_object_id: str
    content_sha256: str

    def as_payload(self) -> dict:
        return asdict(self)


def config() -> dict:
    return {
        "provider": PROVIDER,
        "model_id": MODEL_ID,
        "vector_size": VECTOR_SIZE,
        "distance": DISTANCE,
        "embedding_mode": EMBEDDING_MODE,
        "embedding_version": EMBEDDING_VERSION,
        "collection": COLLECTION,
    }


def load_model():
    global _model
    with _lock:
        if _model is None:
            os.environ.setdefault("HF_HOME", "/opt/legalmind-data/hf")
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(MODEL_ID, device="cpu")
            dim = model.get_sentence_embedding_dimension()
            if dim != VECTOR_SIZE:
                raise RuntimeError(
                    f"عدم تطابق الأبعاد: النموذج {MODEL_ID} يعطي {dim} والمُعلن {VECTOR_SIZE}"
                )
            _model = model
    return _model


def content_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _encode(texts: list[str]) -> list[list[float]]:
    model = load_model()
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return [vector.tolist() for vector in vectors]


def embed_passages(texts: list[str]) -> list[list[float]]:
    """يضمّن نصوصًا مفهرسة. البادئة `passage:` تُضاف هنا ولا تُضاف مرتين."""
    for text in texts:
        if text.startswith(QUERY_PREFIX):
            raise ValueError("نص مفهرس ببادئة query: — خطأ في صيغة E5")
    prefixed = [t if t.startswith(PASSAGE_PREFIX) else PASSAGE_PREFIX + t for t in texts]
    return _encode(prefixed)


def embed_query(text: str) -> list[float]:
    """يضمّن استعلامًا. البادئة `query:` إلزامية."""
    if text.startswith(PASSAGE_PREFIX):
        raise ValueError("استعلام ببادئة passage: — خطأ في صيغة E5")
    prefixed = text if text.startswith(QUERY_PREFIX) else QUERY_PREFIX + text
    return _encode([prefixed])[0]


def meta_for(object_id: str, embedded_text: str) -> EmbeddingMeta:
    return EmbeddingMeta(
        embedding_model=MODEL_ID,
        embedding_dimension=VECTOR_SIZE,
        embedding_version=EMBEDDING_VERSION,
        embedded_at=datetime.now(timezone.utc).isoformat(),
        source_object_id=object_id,
        content_sha256=content_sha256(embedded_text),
    )


def point_id(object_id: str) -> int:
    """حتمي وقابل لإعادة الإنتاج — لا يتغيّر أبدًا (يفصل المتجه عن كائنه)."""
    return int.from_bytes(hashlib.sha256(object_id.encode()).digest()[:8], "big") & ((1 << 63) - 1)


if __name__ == "__main__":
    import json

    print(json.dumps(config(), ensure_ascii=False, indent=2))
