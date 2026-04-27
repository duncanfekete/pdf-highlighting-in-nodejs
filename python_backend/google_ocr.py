"""Google Document AI Enterprise Document OCR -> hierarchical BBox tree."""

from __future__ import annotations

import datetime
import json
import os
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Tuple

import fitz
from google.api_core.client_options import ClientOptions
from google.cloud import documentai_v1


# ---------------------------------------------------------------------------
# BBox schema
# ---------------------------------------------------------------------------

# position = (page, x0, y0, x1, y1):
#   - page: 1-based page number
#   - x0, y0, x1, y1: normalized 0..1 coords relative to page size
#     (origin top-left; x increases right, y increases down - matches Doc AI)
Pos = Tuple[int, float, float, float, float]


@dataclass
class BBox:
    id: str
    text: str
    position: Pos
    segmentation: str
    children: List["BBox"] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_timestamp() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _anchor_text(full_text: str, text_anchor) -> str:
    """Resolve a TextAnchor into its substring of document.text."""
    if not text_anchor or not text_anchor.text_segments:
        return (text_anchor.content or "").strip() if text_anchor else ""
    parts: list[str] = []
    for seg in text_anchor.text_segments:
        start = int(seg.start_index) if seg.start_index else 0
        end = int(seg.end_index) if seg.end_index else 0
        if end > start:
            parts.append(full_text[start:end])
    return "".join(parts).strip()


def _xyxy(bounding_poly, page_dim) -> tuple[float, float, float, float]:
    """Return normalized (x0, y0, x1, y1) from a Doc AI BoundingPoly."""
    if not bounding_poly:
        return (0.0, 0.0, 0.0, 0.0)
    norm = list(bounding_poly.normalized_vertices)
    if norm:
        xs = [v.x for v in norm]
        ys = [v.y for v in norm]
        return (min(xs), min(ys), max(xs), max(ys))
    abs_v = list(bounding_poly.vertices)
    if abs_v and page_dim and page_dim.width and page_dim.height:
        w, h = float(page_dim.width), float(page_dim.height)
        xs = [v.x / w for v in abs_v]
        ys = [v.y / h for v in abs_v]
        return (min(xs), min(ys), max(xs), max(ys))
    return (0.0, 0.0, 0.0, 0.0)


def _rect_center(r):
    return ((r[0] + r[2]) / 2.0, (r[1] + r[3]) / 2.0)


def _rect_contains_point(outer, pt, tol=0.005):
    return (
        outer[0] - tol <= pt[0] <= outer[2] + tol
        and outer[1] - tol <= pt[1] <= outer[3] + tol
    )


# ---------------------------------------------------------------------------
# OCR response -> BBox tree
# ---------------------------------------------------------------------------

def page_to_bboxes(page, full_text: str) -> Tuple[List[BBox], List[str]]:
    """Convert a single OCR page into a list of top-level BBox nodes.

    Layout hierarchy emitted:
      - `table` -> `table_header_row` / `table_row` -> `table_cell` (text leaf)
      - `block` -> `paragraph` -> `line`  (text flows outside tables)

    Returns the list of top-level BBox nodes and a flat list of all IDs.
    """
    ids: List[str] = []
    page_num = int(page.page_number) if page.page_number else 1
    dim = page.dimension

    # --- Tables -----------------------------------------------------------
    table_nodes: List[BBox] = []
    table_rects: List[Tuple[float, float, float, float]] = []
    for table in page.tables:
        t_rect = _xyxy(table.layout.bounding_poly, dim)
        table_rects.append(t_rect)

        row_children: List[BBox] = []

        def _emit_row(row, row_seg: str) -> None:
            cell_children: List[BBox] = []
            row_xs: List[float] = []
            row_ys: List[float] = []
            for cell in row.cells:
                c_rect = _xyxy(cell.layout.bounding_poly, dim)
                cell_text = _anchor_text(full_text, cell.layout.text_anchor)
                cell_id = f"table_cell-{page_num}-{len(cell_children)}-{_get_timestamp()}"
                ids.append(cell_id)
                cell_children.append(
                    BBox(
                        id=cell_id,
                        text=cell_text,
                        position=(page_num, *c_rect),
                        segmentation="table_cell",
                        children=[],
                    )
                )
                row_xs += [c_rect[0], c_rect[2]]
                row_ys += [c_rect[1], c_rect[3]]
            r_rect = (
                (min(row_xs), min(row_ys), max(row_xs), max(row_ys))
                if row_xs and row_ys
                else t_rect
            )
            row_id = f"{row_seg}-{page_num}-{len(row_children)}-{_get_timestamp()}"
            ids.append(row_id)
            row_children.append(
                BBox(
                    id=row_id,
                    text="",
                    position=(page_num, *r_rect),
                    segmentation=row_seg,
                    children=cell_children,
                )
            )

        for row in table.header_rows:
            _emit_row(row, "table_header_row")
        for row in table.body_rows:
            _emit_row(row, "table_row")

        table_id = f"table-{page_num}-{len(table_nodes)}-{_get_timestamp()}"
        ids.append(table_id)
        table_nodes.append(
            BBox(
                id=table_id,
                text="",
                position=(page_num, *t_rect),
                segmentation="table",
                children=row_children,
            )
        )

    # --- Blocks/paragraphs/lines (outside tables) -------------------------
    paragraph_rects: List[Tuple[float, float, float, float]] = []
    paragraph_texts: List[str] = []
    for para in page.paragraphs:
        paragraph_rects.append(_xyxy(para.layout.bounding_poly, dim))
        paragraph_texts.append(_anchor_text(full_text, para.layout.text_anchor))

    line_rects: List[Tuple[float, float, float, float]] = []
    line_texts: List[str] = []
    for line in page.lines:
        line_rects.append(_xyxy(line.layout.bounding_poly, dim))
        line_texts.append(_anchor_text(full_text, line.layout.text_anchor))

    # Assign each line to the paragraph whose rect contains its center.
    para_lines: List[List[int]] = [[] for _ in page.paragraphs]
    for li, l_rect in enumerate(line_rects):
        pt = _rect_center(l_rect)
        for pi, p_rect in enumerate(paragraph_rects):
            if _rect_contains_point(p_rect, pt):
                para_lines[pi].append(li)
                break

    # Assign each paragraph to the block whose rect contains its center.
    block_paragraphs: List[List[int]] = []
    block_rects: List[Tuple[float, float, float, float]] = []
    block_texts: List[str] = []
    for block in page.blocks:
        b_rect = _xyxy(block.layout.bounding_poly, dim)
        block_rects.append(b_rect)
        block_texts.append(_anchor_text(full_text, block.layout.text_anchor))
        block_paragraphs.append([])
    for pi, p_rect in enumerate(paragraph_rects):
        pt = _rect_center(p_rect)
        for bi, b_rect in enumerate(block_rects):
            if _rect_contains_point(b_rect, pt):
                block_paragraphs[bi].append(pi)
                break

    def _in_any_table(rect):
        pt = _rect_center(rect)
        return any(_rect_contains_point(tr, pt) for tr in table_rects)

    block_nodes: List[BBox] = []
    for bi, b_rect in enumerate(block_rects):
        if _in_any_table(b_rect):
            continue
        para_nodes: List[BBox] = []
        for pi in block_paragraphs[bi]:
            p_rect = paragraph_rects[pi]
            if _in_any_table(p_rect):
                continue
            line_nodes: List[BBox] = []
            for li in para_lines[pi]:
                line_id = f"line-{page_num}-{li}-{_get_timestamp()}"
                ids.append(line_id)
                line_nodes.append(
                    BBox(
                        id=line_id,
                        text=line_texts[li],
                        position=(page_num, *line_rects[li]),
                        segmentation="line",
                        children=[],
                    )
                )
            para_id = f"paragraph-{page_num}-{pi}-{_get_timestamp()}"
            ids.append(para_id)
            para_nodes.append(
                BBox(
                    id=para_id,
                    text=paragraph_texts[pi],
                    position=(page_num, *p_rect),
                    segmentation="paragraph",
                    children=line_nodes,
                )
            )
        block_id = f"block-{page_num}-{bi}-{_get_timestamp()}"
        ids.append(block_id)
        block_nodes.append(
            BBox(
                id=block_id,
                text=block_texts[bi],
                position=(page_num, *b_rect),
                segmentation="block",
                children=para_nodes,
            )
        )

    return (block_nodes + table_nodes), ids


def document_to_bboxes(document: documentai_v1.Document) -> Tuple[List[BBox], List[str]]:
    """Convert an OCR Document response into a BBox tree.

    Returns a flat list of top-level BBoxes spanning all pages and a flat list
    of all BBox IDs.
    """
    out: List[BBox] = []
    ids: List[str] = []
    for page in document.pages:
        page_bboxes, page_ids = page_to_bboxes(page, document.text or "")
        out.extend(page_bboxes)
        ids.extend(page_ids)
    return out, ids


def bboxes_to_json(bboxes: List[BBox], **dumps_kwargs) -> str:
    return json.dumps([asdict(b) for b in bboxes], **dumps_kwargs)


# ---------------------------------------------------------------------------
# Document AI call
# ---------------------------------------------------------------------------

def process_ocr(
    client: documentai_v1.DocumentProcessorServiceClient,
    project_id: str,
    location: str,
    processor_id: str,
    file_path: str,
) -> documentai_v1.ProcessResponse:
    """Run the Enterprise Document OCR processor on a PDF."""
    name = client.processor_path(project_id, location, processor_id)
    with open(file_path, "rb") as fp:
        raw_document = documentai_v1.RawDocument(
            content=fp.read(), mime_type="application/pdf"
        )
    request = documentai_v1.ProcessRequest(name=name, raw_document=raw_document)
    return client.process_document(request=request)


# ---------------------------------------------------------------------------
# Example usage: render a BBox tree onto a PDF
# ---------------------------------------------------------------------------

_SEGMENTATION_COLORS: Dict[str, Tuple[float, float, float]] = {
    "block": (0, 0, 1),
    "paragraph": (0, 0.5, 0.9),
    "line": (0.4, 0.7, 1),
    "table": (0, 0.6, 0),
    "table_header_row": (0, 0.45, 0.15),
    "table_row": (0, 0.5, 0.3),
    "table_cell": (0.2, 0.7, 0.2),
}


def _walk(bboxes: List[BBox]):
    for b in bboxes:
        yield b
        if b.children:
            yield from _walk(b.children)


def draw_bboxes_on_pdf(pdf_path: str, bboxes: List[BBox], output_path: str) -> None:
    """Render every BBox (recursively) onto the PDF."""
    pdf = fitz.open(pdf_path)
    drew = 0
    skipped = 0
    for b in _walk(bboxes):
        page_num, x0, y0, x1, y1 = b.position
        page_idx = page_num - 1
        if page_idx < 0 or page_idx >= len(pdf):
            skipped += 1
            continue
        if (x1 - x0) <= 0 or (y1 - y0) <= 0:
            skipped += 1
            continue
        page = pdf[page_idx]
        w, h = page.rect.width, page.rect.height
        rect = fitz.Rect(x0 * w, y0 * h, x1 * w, y1 * h)
        if rect.is_empty:
            skipped += 1
            continue
        color = _SEGMENTATION_COLORS.get(b.segmentation, (0.5, 0.5, 0.5))
        page.draw_rect(rect, color=color, width=1.0)
        page.insert_text(
            fitz.Point(rect.x0 + 2, max(rect.y0 - 2, 8)),
            b.segmentation,
            fontsize=6,
            color=color,
        )
        drew += 1
    pdf.save(output_path)
    pdf.close()
    print(f"  drew {drew} boxes on {output_path} (skipped {skipped})")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    project_id = "replace-with-your-project-id"
    processor_id = "replace-with-your-processor-id"
    location = "replace-with-your-region"
    file_directory = os.path.join(os.path.dirname(__file__), "..", "PDFs")
    output_directory = os.path.join(os.path.dirname(__file__), "..", "google_processed_PDFs")

    opts = ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")
    client = documentai_v1.DocumentProcessorServiceClient(client_options=opts)

    for file_path in os.listdir(file_directory):
        if not file_path.lower().endswith(".pdf"):
            continue

        full_path = os.path.join(file_directory, file_path)
        stem = os.path.splitext(file_path)[0]
        print(f"Processing {file_path}...")

        result = process_ocr(client, project_id, location, processor_id, full_path)
        document = result.document
        num_blocks = sum(len(p.blocks) for p in document.pages)
        num_tables = sum(len(p.tables) for p in document.pages)
        print(
            f"  pages: {len(document.pages)}, blocks: {num_blocks}, "
            f"tables: {num_tables}"
        )

        bboxes, ids = document_to_bboxes(document)

        annotated_path = os.path.join(output_directory, f"{stem}_annotated.pdf")
        draw_bboxes_on_pdf(full_path, bboxes, annotated_path)
