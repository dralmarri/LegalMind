#!/usr/bin/env python3
"""تجزئة كلمة مرور المدير والتحقق منها (scrypt من المكتبة القياسية)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os

SCRYPT_N = 2**15
SCRYPT_R = 8
SCRYPT_P = 1
DKLEN = 32
SALT_BYTES = 16
# الحد الافتراضي في OpenSSL (32MB) أقل من حاجة n=2**15 وr=8 (~33.5MB)، فنرفعه صراحة.
MAXMEM = 128 * 1024 * 1024


def _b64e(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _b64d(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    """يُنتج سلسلة تجزئة قابلة للتخزين: scrypt$n$r$p$salt_b64$key_b64"""
    salt = salt or os.urandom(SALT_BYTES)
    key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=DKLEN,
        maxmem=MAXMEM,
    )
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64e(salt)}${_b64e(key)}"


def verify_password(password: str, encoded: str) -> bool:
    """تحقق ثابت الزمن. يعيد False لأي تجزئة تالفة بدل رفع استثناء."""
    try:
        scheme, n, r, p, salt_b64, key_b64 = encoded.split("$")
        if scheme != "scrypt":
            return False
        expected = _b64d(key_b64)
        candidate = hashlib.scrypt(
            password.encode("utf-8"),
            salt=_b64d(salt_b64),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
            maxmem=MAXMEM,
        )
    except (ValueError, TypeError, MemoryError):
        return False
    return hmac.compare_digest(candidate, expected)
