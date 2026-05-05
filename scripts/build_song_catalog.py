#!/usr/bin/env python3
"""Build structured song JSON from extracted page-wise text."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PAGE_HEADER_RE = re.compile(r"^===== PAGE (\d+) =====$", re.MULTILINE)
VERSE_START_RE = re.compile(r"^(\d{1,2})[.)]\s*(.+)$")
SECTION_MARKERS = {"NWQeLs"}


def parse_pages(raw_text: str) -> List[Tuple[int, str]]:
    matches = list(PAGE_HEADER_RE.finditer(raw_text))
    pages: List[Tuple[int, str]] = []
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw_text)
        page_number = int(match.group(1))
        page_content = raw_text[start:end].strip()
        pages.append((page_number, page_content))
    return pages


def to_category(song_number: Optional[int]) -> str:
    if not song_number:
        return "Uncategorized"
    bucket_start = ((song_number - 1) // 50) * 50 + 1
    bucket_end = bucket_start + 49
    return f"Songs {bucket_start}-{bucket_end}"


def clean_lines(page_content: str) -> List[str]:
    lines = [line.strip() for line in page_content.splitlines()]
    return [line for line in lines if line]


def parse_song_from_page(page_number: int, page_content: str) -> Dict[str, object]:
    lines = clean_lines(page_content)
    song_number: Optional[int] = None
    idx = 0

    if lines and re.fullmatch(r"\d{1,3}", lines[0]):
        song_number = int(lines[0])
        idx = 1

    title_lines: List[str] = []
    while idx < len(lines):
        line = lines[idx]
        if line in SECTION_MARKERS or VERSE_START_RE.match(line):
            break
        title_lines.append(line)
        idx += 1

    if not title_lines:
        while idx < len(lines):
            line = lines[idx]
            if line in SECTION_MARKERS:
                idx += 1
                continue
            if VERSE_START_RE.match(line):
                break
            title_lines = [line]
            idx += 1
            break

    chorus_lines: List[str] = []
    verses: List[Dict[str, object]] = []
    current_verse_number: Optional[int] = None
    current_verse_lines: List[str] = []

    while idx < len(lines):
        line = lines[idx]
        idx += 1

        if line in SECTION_MARKERS:
            continue

        verse_match = VERSE_START_RE.match(line)
        if verse_match:
            if current_verse_lines:
                verses.append(
                    {
                        "number": current_verse_number,
                        "text": "\n".join(current_verse_lines).strip(),
                    }
                )
            current_verse_number = int(verse_match.group(1))
            current_verse_lines = [verse_match.group(2).strip()]
            continue

        if current_verse_lines:
            current_verse_lines.append(line)
        else:
            chorus_lines.append(line)

    if current_verse_lines:
        verses.append(
            {
                "number": current_verse_number,
                "text": "\n".join(current_verse_lines).strip(),
            }
        )

    title = " ".join(title_lines).strip() if title_lines else f"Song {page_number}"
    effective_number = song_number if song_number is not None else page_number
    song_id = f"song-{effective_number:03d}-{page_number:03d}"
    chorus = "\n".join(chorus_lines).strip() if chorus_lines else None

    searchable_parts: List[str] = [title]
    if chorus:
        searchable_parts.append(chorus)
    searchable_parts.extend(verse["text"] for verse in verses)
    searchable_text = "\n".join(searchable_parts).lower()

    return {
        "id": song_id,
        "page": page_number,
        "number": effective_number,
        "title": title,
        "category": to_category(song_number),
        "chorus": chorus,
        "verses": verses,
        "searchable_text": searchable_text,
    }


def build_catalog(input_path: Path, output_path: Path) -> None:
    raw_text = input_path.read_text(encoding="utf-8")
    pages = parse_pages(raw_text)
    songs = [parse_song_from_page(page, content) for page, content in pages]

    payload = {
        "source": str(input_path),
        "song_count": len(songs),
        "songs": songs,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Built catalog with {len(songs)} songs: {output_path}")


def main() -> None:
    input_path = Path("/workspace/data/songs_of_zion_extracted.txt")
    output_path = Path("/workspace/data/songs_of_zion_catalog.json")
    build_catalog(input_path=input_path, output_path=output_path)


if __name__ == "__main__":
    main()
