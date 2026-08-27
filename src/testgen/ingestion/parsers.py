"""Deterministic text extraction for each supported source-document format.

Each function takes raw file bytes and returns normalized plain text. Splitting
that text into candidate requirements is a separate step (requirement_splitter.py)
so these stay simple, pure, and easy to test in isolation from the LLM-based
Requirement Analyst agent that later refines and classifies what they produce.
"""

import io
from collections.abc import Callable

from docx import Document as DocxDocument
from lxml import etree
from markdown_it import MarkdownIt
from pypdf import PdfReader

from testgen.platform.enums import DocumentFormat

_EXTENSION_TO_FORMAT = {
    ".pdf": DocumentFormat.PDF,
    ".docx": DocumentFormat.DOCX,
    ".xml": DocumentFormat.XML,
    ".reqif": DocumentFormat.REQIF,
    ".reqifz": DocumentFormat.REQIF,
    ".md": DocumentFormat.MARKDOWN,
    ".markdown": DocumentFormat.MARKDOWN,
}


def detect_format(filename: str) -> DocumentFormat:
    lower = filename.lower()
    for ext, fmt in _EXTENSION_TO_FORMAT.items():
        if lower.endswith(ext):
            return fmt
    raise ValueError(f"Unsupported source document extension: {filename!r}")


def parse_pdf(raw_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(raw_bytes))
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    return "\n\n".join(page for page in pages if page)


def parse_docx(raw_bytes: bytes) -> str:
    document = DocxDocument(io.BytesIO(raw_bytes))
    paragraphs = [p.text.strip() for p in document.paragraphs]
    return "\n\n".join(p for p in paragraphs if p)


def parse_xml(raw_bytes: bytes) -> str:
    root = etree.fromstring(raw_bytes)
    texts: list[str] = []
    for node_text in root.itertext():
        text = node_text.decode("utf-8") if isinstance(node_text, bytes) else node_text
        if text.strip():
            texts.append(text.strip())
    return "\n\n".join(texts)


_REQIF_VALUE_TAGS = {"THE-VALUE"}


def parse_reqif(raw_bytes: bytes) -> str:
    """Extracts SPEC-OBJECT attribute text.

    Handles the common case (string-valued attributes), not the full OMG ReqIF
    spec — no attribute-definition/datatype resolution and no spec-hierarchy
    traversal. Good enough to demonstrate the format; a production ReqIF adapter
    would need considerably more of the spec.
    """
    root = etree.fromstring(raw_bytes)
    blocks: list[str] = []
    for spec_object in root.iter("{*}SPEC-OBJECT"):
        values = [
            (node.text or "").strip()
            for node in spec_object.iter()
            if etree.QName(node).localname in _REQIF_VALUE_TAGS and node.text
        ]
        block = " ".join(v for v in values if v)
        if block:
            blocks.append(block)
    return "\n\n".join(blocks)


def parse_markdown(raw_bytes: bytes) -> str:
    """An inline token's own `.content` is the raw markdown source (markup and all);
    the de-markup'd text lives in its children's `text`/`code_inline` tokens.
    """
    md = MarkdownIt()
    tokens = md.parse(raw_bytes.decode("utf-8"))
    blocks: list[str] = []
    for token in tokens:
        if token.type != "inline" or token.children is None:
            continue
        plain = "".join(
            child.content for child in token.children if child.type in ("text", "code_inline")
        ).strip()
        if plain:
            blocks.append(plain)
    return "\n\n".join(blocks)


_PARSERS: dict[DocumentFormat, Callable[[bytes], str]] = {
    DocumentFormat.PDF: parse_pdf,
    DocumentFormat.DOCX: parse_docx,
    DocumentFormat.XML: parse_xml,
    DocumentFormat.REQIF: parse_reqif,
    DocumentFormat.MARKDOWN: parse_markdown,
}


def extract_text(file_format: DocumentFormat, raw_bytes: bytes) -> str:
    return _PARSERS[file_format](raw_bytes)
