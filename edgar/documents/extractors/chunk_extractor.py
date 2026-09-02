"""Structural chunking for search and retrieval.

Two consumers, one walk of the node tree.

``StructuralChunker`` is the search-shaped chunker: it cuts the document at
heading boundaries and emits each table as its own chunk, which is the shape
``Filing.sections()`` has always produced and the shape ``Filing.search()``
displays — one panel per chunk, tables rendered as tables. It replaces
``edgar.files.htmltools.html_sections``, whose ``HtmlDocument`` backend 6.0
deletes (bead edgartools-07lk.3).

``ChunkExtractor`` is the token-budgeted chunker ``Document.chunks()`` has
imported from this module since the parser rewrite. The module was never
written, so that public method — a retrieval API, and RAG is a large part of
what this library is used for — raised ``ModuleNotFoundError`` for every caller
that ever tried it (bead edgartools-vwtb). It packs and splits the structural
chunks rather than re-walking the tree, so a retrieval chunk never straddles a
heading it did not have to.

WHY STRUCTURE RATHER THAN A FIXED WINDOW for the search path. BM25 scores whole
chunks, so chunk boundaries decide what a hit means. Cutting every N tokens puts
the answer to "what did they say about supply concentration" in the middle of a
window that begins mid-sentence in an unrelated risk factor, and the panel the
user reads starts there too. Heading-anchored chunks make a hit a passage.
"""
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterator, List, Optional

from edgar.documents.types import NodeType

if TYPE_CHECKING:  # pragma: no cover - typing only
    from edgar.documents.document import Document, DocumentChunk
    from edgar.documents.nodes import Node

#: Node types that carry content and are emitted WITHOUT descending into them.
#: A paragraph's text is its TEXT children's text, so descending would emit
#: everything twice; stopping here is what keeps the stream linear.
_CONTENT_TYPES = frozenset({
    NodeType.HEADING,
    NodeType.PARAGRAPH,
    NodeType.LIST,
    NodeType.TABLE,
    NodeType.TEXT,
})

#: Structure. These are walked THROUGH, never emitted.
_CONTAINER_TYPES = frozenset({
    NodeType.DOCUMENT,
    NodeType.SECTION,
    NodeType.CONTAINER,
})

#: Item and Part headers, matched against a LINE of bare text.
#:
#: Pre-2009 filings are the reason this exists. Their markup carries no
#: paragraph or heading structure at all — the whole body arrives as a handful
#: of bare TEXT nodes between tables (measured: a 2001 10-K parses to 23 TEXT
#: nodes and 22 tables, with zero HEADING and zero PARAGRAPH) — so there are no
#: heading boundaries to cut on and the document would otherwise become two or
#: three chunks tens of thousands of characters long. The legacy chunker read
#: the same two patterns off block text for the same reason.
_ITEM_LINE = re.compile(
    r"^\s{0,8}(?:ITEM|Item)\s+(?:[0-9]{1,2}[A-Z]?\.?|[0-9]{1,2}\.[0-9]{2})\b"
)
_PART_LINE = re.compile(r"^\s{0,8}\b(PART\s+[IVXLC]+)\b", re.IGNORECASE)

def _has_heading_descendant(node) -> bool:
    """Is there a HEADING anywhere under this node?

    Load-bearing, and the reason it is not enough to stop at a paragraph. The
    parser routinely nests headings INSIDE paragraphs — on a 1999 10-K all 71
    HEADING nodes are children of a ParagraphNode — so a walk that emits a
    paragraph without descending never sees a single one of them, and the
    chunker silently degrades to cutting on nothing but its size cap. That is
    what the first version did: it still produced plausible chunk counts, which
    is exactly why the failure needed a heading-count assertion to catch rather
    than a shape one.
    """
    for child in node.children:
        if child.type is NodeType.HEADING or _has_heading_descendant(child):
            return True
    return False


#: A heading this short with no letters ("3.", "(a)") is numbering, not a
#: section boundary; cutting on it produced one-line chunks out of numbered
#: lists on older filings.
_NUMBERING_ONLY = re.compile(r'^[\W\d]{0,8}$')


@dataclass
class Chunk:
    """One structural chunk of a document."""

    text: str
    kind: str = 'text'          # 'text' | 'table'
    heading: Optional[str] = None
    section: Optional[str] = None

    def __len__(self) -> int:
        return len(self.text)


def _render_table(table) -> str:
    """Render a table as pipe-delimited rows.

    The leading ``|`` is load-bearing beyond looks: ``SearchResults.__rich__``
    decides whether to draw a result as a table by testing
    ``doc.startswith("|  |")``, so a table chunk that does not start that way
    silently renders as a wall of text. That heuristic is the display contract
    the legacy renderer established and this keeps it.
    """
    lines: List[str] = []

    for header_row in table.headers or []:
        cells = [c.text().strip() for c in header_row]
        if any(cells):
            lines.append('|  | ' + ' | '.join(cells) + ' |')

    for row in list(table.rows or []) + list(table.footer or []):
        cells = [c.text().strip() for c in row.cells]
        if any(cells):
            lines.append('|  | ' + ' | '.join(cells) + ' |')

    if not lines:
        return ''
    caption = (table.caption or '').strip()
    return (f'{caption}\n' if caption else '') + '\n'.join(lines)


class StructuralChunker:
    """Cut a parsed document into heading-anchored chunks."""

    def __init__(self, min_chars: int = 1, max_chars: int = 3000):
        #: Chunks shorter than this are dropped. The default drops only the
        #: genuinely empty. The legacy chunker emitted them freely — on
        #: pre-2009 filings roughly half of its chunks were empty strings,
        #: which BM25 indexes as documents with no terms and which render as
        #: blank panels.
        self.min_chars = min_chars
        #: Soft cap. A chunk is closed at the next paragraph boundary once it
        #: passes this, so no chunk swallows a whole Item.
        #:
        #: This is not tidiness. BM25 scores a chunk as a bag of words and
        #: normalises by length, so an uncapped chunk both dilutes the query
        #: terms it does contain and hides every distinct passage inside it
        #: behind a single result. Measured over 15 filings and 375 phrase
        #: queries: uncapped recall@1 is 89.5% against the legacy chunker's
        #: 92.2%, and capping at 3,000 recovers it to 91.8% with recall@5 level
        #: at 99.2% either way. See the module docstring of
        #: tests/test_document_chunking.py for the harness.
        self.max_chars = max_chars

    def chunks(self, document: 'Document') -> List[Chunk]:
        root = getattr(document, 'root', None)
        if root is None:
            return []

        walk = _StructuralWalk(self.min_chars, self.max_chars)
        walk.visit(root)
        walk.flush()
        return walk.out


class _StructuralWalk:
    """
    One pass over a document tree, accumulating chunks.

    This is a class rather than a nest of closures only so each step stays
    small enough to read on its own; the state it carries is exactly what the
    walk needs to decide where one passage ends and the next begins.
    """

    def __init__(self, min_chars: int, max_chars: int):
        self.min_chars = min_chars
        self.max_chars = max_chars
        self.out: List[Chunk] = []
        self.buffer: List[str] = []
        self.heading: Optional[str] = None
        #: Has body text landed in the buffer since the last heading? Runs of
        #: consecutive headings are one passage, not one chunk each.
        #:
        #: Without this the chunker cuts on every heading, and filings that mark
        #: each line of their cover page as a heading — common pre-2003 — come
        #: out as a chunk per LINE ("UNITED STATES", "SECURITIES AND EXCHANGE
        #: COMMISSION", ...). The legacy chunker carried the same rule under the
        #: names `header_detected` / `accumulating_regular_text`.
        self.body_since_heading = False

    def flush(self) -> None:
        """Close the current passage, dropping it if it is too short."""
        self.body_since_heading = False
        if not self.buffer:
            return
        text = '\n'.join(part for part in self.buffer if part).strip()
        self.buffer.clear()
        if len(text) >= self.min_chars:
            self.out.append(Chunk(text=text, kind='text', heading=self.heading))

    def emit_heading(self, text: str) -> None:
        """Start a new passage under `text`, unless we are mid-run of headings."""
        if self.body_since_heading:
            self.flush()
        self.heading = text
        self.body_since_heading = False
        self.buffer.append(text)

    def _append_body(self, text: str) -> None:
        """Add body text, closing the passage if it has grown past the cap."""
        self.buffer.append(text)
        self.body_since_heading = True
        if self.max_chars and sum(len(b) for b in self.buffer) >= self.max_chars:
            self.flush()

    def visit(self, node: 'Node') -> None:
        if node.type is NodeType.TABLE:
            self._visit_table(node)
        elif node.type in _CONTENT_TYPES:
            self._visit_content(node)
        elif node.type in _CONTAINER_TYPES:
            for child in node.children:
                self.visit(child)

    def _visit_table(self, node: 'Node') -> None:
        self.flush()
        rendered = _render_table(node)
        if len(rendered) >= self.min_chars:
            self.out.append(Chunk(text=rendered, kind='table', heading=self.heading))

    def _visit_content(self, node: 'Node') -> None:
        text = (node.text() or '').strip()
        if not text:
            return

        # A paragraph wrapping headings is structure, not a passage.
        if (node.type in (NodeType.PARAGRAPH, NodeType.LIST)
                and _has_heading_descendant(node)):
            for child in node.children:
                self.visit(child)
            return

        if node.type is NodeType.HEADING and not _NUMBERING_ONLY.match(text):
            self.emit_heading(text)
            return

        if node.type is NodeType.TEXT:
            self._visit_bare_text(text)
            return

        self._append_body(text)

    def _visit_bare_text(self, text: str) -> None:
        """
        Cut bare text on Item/Part lines.

        A document built entirely of these has no other boundary available.
        """
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if _PART_LINE.match(line) or _ITEM_LINE.match(line):
                self.emit_heading(stripped)
            else:
                self._append_body(stripped)


class ChunkExtractor:
    """Token-budgeted chunks over the structural ones, with overlap.

    ``chunk_size`` and ``overlap`` are in tokens, as ``Document.chunks()``
    documents them; tokens are counted as whitespace-delimited words, which is
    within a small constant of any BPE tokenizer and needs no dependency.
    """

    def __init__(self, chunk_size: int = 512, overlap: int = 128):
        from edgar.exceptions import ValidationError

        if chunk_size <= 0:
            raise ValidationError(
                "chunk_size must be a positive number of tokens.",
                parameter='chunk_size', invalid_value=chunk_size,
                suggestions=["Pass a positive integer, e.g. chunk_size=512."])
        if not 0 <= overlap < chunk_size:
            # Equal or larger would make the window advance by zero and loop
            # forever on any document with a chunk over the budget.
            raise ValidationError(
                f"overlap must be non-negative and smaller than chunk_size "
                f"({chunk_size}); an overlap that large never advances the window.",
                parameter='overlap', invalid_value=overlap,
                suggestions=[f"Try overlap={max(chunk_size // 4, 0)}."])
        self.chunk_size = chunk_size
        self.overlap = overlap

    def extract(self, document: 'Document') -> Iterator['DocumentChunk']:
        from edgar.documents.document import DocumentChunk

        root = getattr(document, 'root', None)
        for chunk in StructuralChunker().chunks(document):
            for piece, count in self._split(chunk.text):
                yield DocumentChunk(
                    content=piece,
                    start_node=root,
                    end_node=root,
                    section=chunk.heading,
                    token_count=count,
                )

    def _split(self, text: str):
        words = text.split()
        if not words:
            return
        if len(words) <= self.chunk_size:
            yield text, len(words)
            return
        step = self.chunk_size - self.overlap
        for start in range(0, len(words), step):
            window = words[start:start + self.chunk_size]
            if not window:
                break
            yield ' '.join(window), len(window)
            if start + self.chunk_size >= len(words):
                break


def chunk_html(html: str, form: Optional[str] = None, **kwargs) -> List[str]:
    """Parse HTML and return its structural chunks as plain strings.

    The entry point ``Filing.sections()`` uses, and the replacement for
    ``edgar.files.htmltools.html_sections``. A parse failure returns the empty
    list rather than raising: ``sections()`` feeds a search index, and a filing
    whose markup defeats the parser should search as empty, not make
    ``filing.search(...)`` raise.
    """
    from edgar.documents import HTMLParser, ParserConfig

    if not html:
        return []
    try:
        document = HTMLParser(ParserConfig(form=form)).parse(html)
    except Exception:
        return []
    return [chunk.text for chunk in StructuralChunker(**kwargs).chunks(document)]
