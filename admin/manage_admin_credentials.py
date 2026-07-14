#!/usr/bin/env python3
"""أداة إدارية لتغيير اسم مستخدم/كلمة مرور مدير LegalMind.

كلمة المرور تُقرأ تفاعليًا عبر getpass ولا تُمرَّر أبدًا كوسيط سطر أوامر،
ولا تُكتب إلى القرص، ولا تُطبع. الملف المخزَّن يحمل التجزئة فقط.

    sudo admin/.venv/bin/python -m admin.manage_admin_credentials --username <name>
"""
from __future__ import annotations

import argparse
import base64
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from getpass import getpass
from pathlib import Path

from admin.security import hash_password, verify_password

ENV_FILE = Path(__file__).resolve().parent.parent / "deploy" / "admin.env"
SERVICE = "legalmind-admin.service"
BASE_URL = os.getenv("LEGALMIND_ADMIN_URL", "http://127.0.0.1:8088")
USER_KEY = "LEGALMIND_ADMIN_USER"
HASH_KEY = "LEGALMIND_ADMIN_PASSWORD_HASH"
LEGACY_PLAINTEXT_KEY = "LEGALMIND_ADMIN_PASSWORD"
MIN_LENGTH = 12


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def write_env(path: Path, values: dict[str, str]) -> None:
    """كتابة ذرّية بصلاحيات 600 حتى لا يوجد ملف وسيط مقروء للجميع."""
    body = "".join(f"{k}={v}\n" for k, v in values.items())
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".admin.env.")
    tmp = Path(tmp_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        tmp.replace(path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    os.chmod(path, 0o600)


def probe(username: str, password: str, path: str = "/api/stats") -> int:
    """يعيد رمز حالة HTTP لمحاولة دخول Basic. 0 إذا تعذّر الاتصال."""
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    request = urllib.request.Request(f"{BASE_URL}{path}")
    request.add_header("Authorization", f"Basic {token}")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except OSError:
        return 0


def prompt_password() -> str:
    while True:
        first = getpass("كلمة مرور المدير الجديدة (لن تظهر): ")
        if len(first) < MIN_LENGTH:
            print(f"  ✗ الحد الأدنى {MIN_LENGTH} محرفًا. حاول مجددًا.", file=sys.stderr)
            continue
        if first != getpass("أعد إدخال كلمة المرور للتأكيد: "):
            print("  ✗ الإدخالان غير متطابقين. حاول مجددًا.", file=sys.stderr)
            continue
        return first


def main() -> int:
    parser = argparse.ArgumentParser(description="تغيير بيانات حساب مدير LegalMind")
    parser.add_argument("--username", required=True, help="اسم المستخدم الجديد للمدير")
    parser.add_argument("--no-restart", action="store_true", help="لا تُعد تشغيل الخدمة")
    args = parser.parse_args()

    if not ENV_FILE.exists():
        print(f"✗ ملف البيئة غير موجود: {ENV_FILE}", file=sys.stderr)
        return 1

    env = read_env(ENV_FILE)
    old_username = env.get(USER_KEY, "")
    # نحتفظ بالسر القديم في الذاكرة فقط لإثبات أنه صار مرفوضًا بعد التغيير.
    old_secret = env.get(LEGACY_PLAINTEXT_KEY, "")
    old_hash = env.get(HASH_KEY, "")

    new_password = prompt_password()
    if verify_password(new_password, old_hash) if old_hash else (new_password == old_secret and old_secret):
        print("✗ كلمة المرور الجديدة مطابقة للقديمة.", file=sys.stderr)
        return 1

    env[USER_KEY] = args.username
    env[HASH_KEY] = hash_password(new_password)
    env.pop(LEGACY_PLAINTEXT_KEY, None)  # إزالة النص الصريح نهائيًا
    write_env(ENV_FILE, env)
    print(f"✓ حُدِّث {ENV_FILE.name} (تجزئة فقط، لا نص صريح، صلاحيات 600)")

    if args.no_restart:
        print("… تخطّي إعادة التشغيل بناءً على الطلب.")
        return 0

    # إعادة التشغيل تُلغي كل بيانات الاعتماد القديمة فورًا (Basic بلا حالة على الخادم).
    subprocess.run(["systemctl", "restart", SERVICE], check=True)
    subprocess.run(["systemctl", "is-active", "--quiet", SERVICE], check=True)
    print(f"✓ أُعيد تشغيل {SERVICE}")

    checks = [
        ("الدخول باسم المستخدم الجديد + كلمة المرور الجديدة", probe(args.username, new_password), 200),
        ("صلاحيات المدير (‎/api/stats)", probe(args.username, new_password, "/api/stats"), 200),
        ("رفض اسم المستخدم القديم", probe(old_username, new_password), 401),
    ]
    if old_secret:
        checks.append(("رفض كلمة المرور القديمة", probe(args.username, old_secret), 401))
    checks.append(("رفض كلمة مرور عشوائية خاطئة", probe(args.username, "wrong-" + os.urandom(4).hex()), 401))

    print("\nنتائج الاختبار:")
    failed = 0
    for label, actual, expected in checks:
        ok = actual == expected
        failed += not ok
        print(f"  {'✓' if ok else '✗'} {label}: HTTP {actual} (المتوقع {expected})")

    if failed:
        print(f"\n✗ فشل {failed} اختبار. راجع: journalctl -u {SERVICE} -n 50", file=sys.stderr)
        return 1
    print("\n✓ نجحت كل الاختبارات. بيانات الاعتماد القديمة لم تعد صالحة.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
