#!/usr/bin/env python3
"""Extract page-wise text from a songbook PDF.

This script writes:
1) A plain-text file with explicit page markers.
2) A lightweight JSON page index for app ingestion workflows.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

from pdfminer.high_level import extract_text


def normalize_page_text(text: str) -> str:
    """Normalize whitespace while preserving line breaks."""
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def extract_pages(pdf_path: Path) -> List[str]:
    full_text = extract_text(str(pdf_path))
    raw_pages = full_text.split("\f")
    pages: List[str] = []
    for raw in raw_pages:
        cleaned = normalize_page_text(raw)
        if cleaned:
            pages.append(cleaned)
    return pages


def write_text_output(pages: List[str], output_path: Path) -> None:
    chunks: List[str] = []
    for i, page_text in enumerate(pages, start=1):
        chunks.append(f"===== PAGE {i} =====\n{page_text}\n")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(chunks), encoding="utf-8")


def write_page_index(pages: List[str], output_path: Path) -> None:
    index = []
    for i, page_text in enumerate(pages, start=1):
        lines = [line for line in page_text.splitlines() if line.strip()]
        preview = lines[:6]
        index.append(
            {
                "page": i,
                "line_count": len(lines),
                "preview": preview,
            }
        )
    payload = {
        "page_count": len(pages),
        "pages": index,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract text from PDF songbook.")
    parser.add_argument(
        "--pdf",
        default="/root/.cursor/projects/workspace/uploads/Songs_of_Zion__new__NJC.pdf",
        help="Absolute path to source PDF.",
    )
    parser.add_argument(
        "--text-out",
        default="/workspace/data/songs_of_zion_extracted.txt",
        help="Output path for full extracted text.",
    )
    parser.add_argument(
        "--index-out",
        default="/workspace/data/songs_of_zion_page_index.json",
        help="Output path for JSON page index.",
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    text_out = Path(args.text_out)
    index_out = Path(args.index_out)

    pages = extract_pages(pdf_path)
    write_text_output(pages, text_out)
    write_page_index(pages, index_out)

    print(f"Extracted pages: {len(pages)}")
    print(f"Wrote text file: {text_out}")
    print(f"Wrote page index: {index_out}")


if __name__ == "__main__":
    main()
