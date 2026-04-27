"""
inject_bboxes_to_frontend.py
----------------------------
Run OCR on a PDF and write the results into the Next.js public directory so the
frontend can serve them as static files.

Usage:
    python inject_bboxes_to_frontend.py <path/to/document.pdf>

Outputs:
    front_end_test/public/document.pdf   — copy of the source PDF
    front_end_test/public/bboxes.json    — BBox tree as JSON
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

from google.api_core.client_options import ClientOptions
from google.cloud import documentai_v1

from python_backend.google_ocr import (
    bboxes_to_json,
    document_to_bboxes,
    process_ocr,
)

# ---------------------------------------------------------------------------
# Config — mirror the values in google_ocr.py __main__
# ---------------------------------------------------------------------------
PROJECT_ID = "replace-with-your-project-id"
PROCESSOR_ID = "replace-with-your-processor-id"
LOCATION = "replace-with-your-region"

# Relative to this script's directory
FRONTEND_PUBLIC_DIR = os.path.join(
    os.path.dirname(__file__), "..", "public"
)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def inject(pdf_path: str) -> None:
    if not os.path.isfile(pdf_path):
        print(f"Error: file not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(FRONTEND_PUBLIC_DIR, exist_ok=True)

    # --- Run OCR -----------------------------------------------------------
    print(f"Running OCR on {pdf_path} ...")
    opts = ClientOptions(api_endpoint=f"{LOCATION}-documentai.googleapis.com")
    client = documentai_v1.DocumentProcessorServiceClient(client_options=opts)

    result = process_ocr(client, PROJECT_ID, LOCATION, PROCESSOR_ID, pdf_path)
    document = result.document

    num_pages = len(document.pages)
    num_blocks = sum(len(p.blocks) for p in document.pages)
    num_tables = sum(len(p.tables) for p in document.pages)
    print(f"  pages: {num_pages}, blocks: {num_blocks}, tables: {num_tables}")

    # --- Build BBox tree ---------------------------------------------------
    bboxes, ids = document_to_bboxes(document)
    print(f"  total BBoxes: {len(ids)}")

    # --- Write outputs to public/ ------------------------------------------
    dest_pdf = os.path.join(FRONTEND_PUBLIC_DIR, "document.pdf")
    shutil.copy2(pdf_path, dest_pdf)
    print(f"  PDF  → {dest_pdf}")

    dest_json = os.path.join(FRONTEND_PUBLIC_DIR, "bboxes.json")
    with open(dest_json, "w", encoding="utf-8") as f:
        f.write(bboxes_to_json(bboxes, indent=2))
    print(f"  JSON → {dest_json}")

    print("Done. Refresh the frontend to see updated results.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="OCR a PDF and inject results into the Next.js frontend."
    )
    parser.add_argument("pdf", help="Path to the PDF file to process.")
    args = parser.parse_args()
    inject(args.pdf)
