#!/usr/bin/env python3
"""اختبارات طبقة التطبيع — تعمل بلا قاعدة بيانات وبلا شبكة.

الاختبار الأهم هنا: PDF الممسوح ضوئيًا يُرفض ولا يمر بنص فارغ.
مصدر قانوني يدخل النظام بنص فارغ ينتج كائنات معرفية جوفاء يُستشهد بها في محكمة.
"""
from __future__ import annotations

import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from normalizer import SUPPORTED_EXTENSIONS, UnsupportedSource, normalize, normalize_text

DOCX_XML = """<?xml version="1.0"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:body>
<w:p><w:r><w:t>المادة 1</w:t></w:r></w:p>
<w:p><w:r><w:t>تسري أحكام هذا القانون على المسلمين.</w:t></w:r></w:p>
<w:p><w:r><w:t>المادة 2</w:t></w:r></w:p>
<w:p><w:r><w:t>الخطبة طلب الزواج.</w:t></w:r></w:p>
</w:body></w:document>"""


def scanned_pdf(path: Path) -> Path:
    """PDF صحيح البنية تمامًا وبلا طبقة نصية — يحاكي المصدر الممسوح ضوئيًا."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    with path.open("wb") as handle:
        writer.write(handle)
    return path


PASSED: list[str] = []
FAILED: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASSED if condition else FAILED).append(f"{name} {detail}".strip())


def write(tmp: Path, name: str, data: bytes | str) -> Path:
    path = tmp / name
    if isinstance(data, str):
        path.write_text(data, encoding="utf-8")
    else:
        path.write_bytes(data)
    return path


def main() -> int:
    with tempfile.TemporaryDirectory() as raw_tmp:
        tmp = Path(raw_tmp)

        # --- التطبيع الموحد ---
        check("التطويل يُحذف", normalize_text("الحضـــانة") == "الحضانة")
        check("المسافات تُضغط", normalize_text("أ    ب") == "أ ب")
        check("الأسطر الزائدة تُضغط", normalize_text("أ\n\n\n\nب") == "أ\n\nب")
        check("المحارف الخفية تُزال", normalize_text("أ‏ب") == "أب")
        check("NFKC يوحّد", normalize_text("ﻻ") == "لا")

        # --- DOCX ---
        docx_path = tmp / "law.docx"
        with zipfile.ZipFile(docx_path, "w") as archive:
            archive.writestr("word/document.xml", DOCX_XML)
        docx = normalize(docx_path)
        check("DOCX: الصيغة", docx.source_format == "docx", f"→ {docx.source_format}")
        check("DOCX: المواد محفوظة", "المادة 1" in docx.body and "المادة 2" in docx.body)
        check("DOCX: بصمة المصدر", len(docx.source_sha256) == 64)

        # --- HTML ---
        html = normalize(write(tmp, "law.html", (
            "<html><head><style>p{color:red}</style></head>"
            "<body><h1>قانون</h1><p>المادة 1</p><p>نص المادة.</p>"
            "<script>alert(1)</script></body></html>"
        )))
        check("HTML: الصيغة", html.source_format == "html")
        check("HTML: النص مستخرج", "المادة 1" in html.body)
        check("HTML: script/style مستبعدان",
              "alert" not in html.body and "color:red" not in html.body)

        # --- TXT / Markdown ---
        txt = normalize(write(tmp, "law.txt", "المادة 5\nنص.\n"))
        check("TXT: الصيغة", txt.source_format == "txt")
        check("TXT: النص محفوظ", "المادة 5" in txt.body)

        md = normalize(write(tmp, "law.md", "# عنوان\n\nالمادة 7\nنص.\n"))
        check("MD: الصيغة", md.source_format == "markdown")

        # --- PDF ممسوح ضوئيًا: يجب أن يُرفض، لا أن يمر بنص فارغ ---
        try:
            normalize(scanned_pdf(tmp / "scanned.pdf"))
            check("PDF ممسوح يُرفض", False, "مرّ بنص فارغ — خطر قانوني")
        except UnsupportedSource as exc:
            check("PDF ممسوح يُرفض", "ممسوح" in str(exc))

        # --- PDF تالف: خطأ واضح، لا استثناء خام من المكتبة ---
        try:
            normalize(write(tmp, "broken.pdf", b"%PDF-1.4\ngarbage"))
            check("PDF التالف يُرفض", False)
        except UnsupportedSource as exc:
            check("PDF التالف يُرفض", "تالف" in str(exc))
        except Exception as exc:
            check("PDF التالف يُرفض", False, f"استثناء خام: {type(exc).__name__}")

        # --- صيغة غير مدعومة ---
        try:
            normalize(write(tmp, "x.rtf", "شيء"))
            check("الصيغة غير المدعومة تُرفض", False)
        except UnsupportedSource:
            check("الصيغة غير المدعومة تُرفض", True)

        # --- مصدر فارغ يُرفض ---
        try:
            normalize(write(tmp, "empty.txt", "   \n\n  "))
            check("المصدر الفارغ يُرفض", False, "مرّ بنص فارغ")
        except UnsupportedSource:
            check("المصدر الفارغ يُرفض", True)

        check("الصيغ المسجّلة",
              SUPPORTED_EXTENSIONS >= {".docx", ".pdf", ".txt", ".md", ".html"},
              f"→ {sorted(SUPPORTED_EXTENSIONS)}")

    for name in PASSED:
        print(f"  ✅ {name}")
    for name in FAILED:
        print(f"  ❌ {name}")
    print(f"\n{len(PASSED)} نجح، {len(FAILED)} فشل")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
