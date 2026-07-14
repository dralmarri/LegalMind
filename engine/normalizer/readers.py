"""قارئات الصيغ — كل قارئ يحول صيغة واحدة إلى كتل نصية خام.

القارئ لا يطبّع ولا يصنّف ولا يستخرج. يقرأ فقط.
إضافة صيغة جديدة = دالة جديدة + سطر في READERS. لا يتغير شيء بعدها.
"""
from __future__ import annotations

import zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

DOCX_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
HTML_SKIP = {"script", "style", "head", "meta", "link", "noscript"}
HTML_BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6",
              "section", "article", "td", "th", "blockquote"}


class UnsupportedSource(Exception):
    """صيغة غير مدعومة، أو مصدر لا يمكن استخراج نص منه."""


def read_docx(path: Path) -> tuple[list[str], list[str]]:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml")
    root = ET.fromstring(xml)
    blocks = []
    for paragraph in root.findall(".//w:p", DOCX_NS):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", DOCX_NS)).strip()
        if text:
            blocks.append(text)
    return blocks, []


def read_pdf(path: Path) -> tuple[list[str], list[str]]:
    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
    except ImportError as exc:  # pragma: no cover
        raise UnsupportedSource(
            "قراءة PDF تتطلب حزمة pypdf. ثبّتها: pip install pypdf"
        ) from exc

    try:
        reader = PdfReader(str(path))
        pages = list(reader.pages)
    except (PdfReadError, OSError, ValueError) as exc:
        raise UnsupportedSource(f"PDF تالف أو غير قابل للقراءة: {exc}") from exc

    blocks: list[str] = []
    empty_pages = 0
    for page in pages:
        try:
            text = (page.extract_text() or "").strip()
        except Exception as exc:  # صفحة معطوبة لا تُسقط المصدر كله بصمت
            empty_pages += 1
            continue
        if text:
            blocks.append(text)
        else:
            empty_pages += 1

    if not blocks:
        raise UnsupportedSource(
            f"PDF بلا طبقة نصية ({len(pages)} صفحة) — الأرجح أنه ممسوح ضوئيًا. "
            "يحتاج OCR وهو غير مدعوم بعد. لا يُقبل المصدر بنص فارغ."
        )

    warnings = []
    if empty_pages:
        warnings.append(f"{empty_pages} صفحة بلا نص مستخرج — راجع اكتمال المصدر")
    return blocks, warnings


class _HTMLText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self._buffer: list[str] = []
        self._skip = 0

    def _flush(self) -> None:
        text = "".join(self._buffer).strip()
        if text:
            self.blocks.append(text)
        self._buffer = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in HTML_SKIP:
            self._skip += 1
        elif tag in HTML_BLOCK:
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        if tag in HTML_SKIP:
            self._skip = max(0, self._skip - 1)
        elif tag in HTML_BLOCK:
            self._flush()

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._buffer.append(data)

    def close(self) -> None:
        super().close()
        self._flush()


def read_html(path: Path) -> tuple[list[str], list[str]]:
    parser = _HTMLText()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    parser.close()
    if not parser.blocks:
        raise UnsupportedSource("HTML بلا نص قابل للاستخراج")
    return parser.blocks, []


def read_plain(path: Path) -> tuple[list[str], list[str]]:
    return path.read_text(encoding="utf-8", errors="replace").split("\n"), []


READERS = {
    ".docx": ("docx", read_docx),
    ".pdf": ("pdf", read_pdf),
    ".html": ("html", read_html),
    ".htm": ("html", read_html),
    ".txt": ("txt", read_plain),
    ".md": ("markdown", read_plain),
}

SUPPORTED_EXTENSIONS = frozenset(READERS)
