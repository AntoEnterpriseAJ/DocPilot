"""Walk a .docx and return ordered Section objects.

A Section is a heading + the paragraphs/tables that follow it until the
next heading. Headings are detected by Word style ("Heading*") OR by a
Romanian-FD numbering pattern at the start of a paragraph (e.g.
"8.1 Tematica activităților de curs").
"""
from __future__ import annotations

import hashlib
import io
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterator, Union

from docx import Document
from docx.document import Document as DocxDocument
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

_NUMBERING_RE = re.compile(r"^\s*\d+(\.\d+)*\s+\S")


@dataclass
class TextBlock:
    paragraphs: list[str]


@dataclass
class TableBlock:
    headers: list[str]
    rows: list[list[str]]


Block = Union[TextBlock, TableBlock]


@dataclass
class Section:
    id: str
    heading: str
    heading_norm: str
    level: int
    position: int
    body: list[Block] = field(default_factory=list)


def extract_sections(docx_bytes: bytes) -> list[Section]:
    doc = Document(io.BytesIO(docx_bytes))
    sections: list[Section] = []
    current: Section | None = None
    text_buffer: list[str] = []
    position = 0

    def flush_text() -> None:
        if text_buffer and current is not None:
            current.body.append(TextBlock(paragraphs=list(text_buffer)))
        text_buffer.clear()

    def ensure_section() -> Section:
        nonlocal current, position
        if current is None:
            current = _new_section("", 0, position)
            sections.append(current)
            position += 1
        return current

    for block in _iter_block_items(doc):
        if isinstance(block, Paragraph):
            heading_level = _heading_level(block)
            if heading_level is not None:
                flush_text()
                current = _new_section(block.text.strip(), heading_level, position)
                sections.append(current)
                position += 1
                continue

            ensure_section()
            text_buffer.append(block.text)
        elif isinstance(block, Table):
            ensure_section()
            flush_text()
            current.body.append(_table_to_block(block))  # type: ignore[union-attr]

    flush_text()
    return sections


def _iter_block_items(parent: DocxDocument) -> Iterator[Paragraph | Table]:
    body = parent.element.body
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, parent)
        elif child.tag == qn("w:tbl"):
            yield Table(child, parent)


def _heading_level(p: Paragraph) -> int | None:
    style = (p.style.name if p.style else "") or ""
    text = (p.text or "").strip()
    if style.startswith("Heading"):
        suffix = style.removeprefix("Heading").strip()
        try:
            return int(suffix) if suffix else 1
        except ValueError:
            return 1
    if text and _NUMBERING_RE.match(text) and len(text) <= 200:
        depth = text.split()[0].count(".") + 1
        return min(depth, 4)
    return None


def _new_section(heading: str, level: int, position: int) -> Section:
    norm = _normalise_heading(heading)
    sid = hashlib.sha1(f"{position}:{norm}".encode("utf-8")).hexdigest()[:12]
    return Section(id=sid, heading=heading, heading_norm=norm, level=level, position=position)


def _normalise_heading(heading: str) -> str:
    if not heading:
        return ""
    text = heading.strip()
    text = re.sub(r"^\s*\d+(\.\d+)*\s+", "", text)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip().lower()


def _table_to_block(table: Table) -> TableBlock:
    rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
    if not rows:
        return TableBlock(headers=[], rows=[])
    headers = rows[0]
    body_rows = rows[1:]
    return TableBlock(headers=headers, rows=body_rows)
