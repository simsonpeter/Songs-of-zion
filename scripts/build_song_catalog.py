#!/usr/bin/env python3
"""Build structured song JSON from extracted page-wise text.

This script can normalize legacy Tamil font encodings to Unicode Tamil
before parsing into song objects.
"""

from __future__ import annotations

import json
import re
import argparse
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

PAGE_HEADER_RE = re.compile(r"^===== PAGE (\d+) =====$", re.MULTILINE)
PAGE_HEADER_LINE_RE = re.compile(r"^===== PAGE \d+ =====$")
VERSE_START_RE = re.compile(r"^(\d{1,2})[.)]\s*(.+)$")
SECTION_MARKERS = {
    "NWQeLs",
    "சரணங்கள்",
    "சரணம்",
    "பல்லவி",
    "பல்லவிஇ",
}

try:
    from tamil import txt2unicode
except Exception:  # pragma: no cover - available in runtime when installed
    txt2unicode = None


def build_converter_map() -> Dict[str, Callable[[str], str]]:
    if txt2unicode is None:
        return {}
    return {
        "dinamani": txt2unicode.dinamani2unicode,
        "softview": txt2unicode.softview2unicode,
        "nakkeeran": txt2unicode.nakkeeran2unicode,
        "kavipriya": txt2unicode.kavipriya2unicode,
    }


def normalize_legacy_text(raw_text: str, converter_name: str) -> str:
    converter_map = build_converter_map()
    if converter_name not in converter_map:
        available = ", ".join(sorted(converter_map)) or "none"
        raise ValueError(f"Converter '{converter_name}' unavailable. Available: {available}")

    converter = converter_map[converter_name]
    out_lines: List[str] = []

    for line in raw_text.splitlines():
        if PAGE_HEADER_LINE_RE.match(line) or not line.strip():
            out_lines.append(line)
            continue
        try:
            out_lines.append(converter(line))
        except Exception:
            out_lines.append(line)

    return "\n".join(out_lines)


def cleanup_unicode_artifacts(text: str) -> str:
    """Apply targeted cleanup rules for recurring conversion artifacts."""
    replacements = [
        ("\u00a0", " "),
        ("−", "-"),
        ("–", "-"),
        ("‐", "-"),
        ("û[", "ளை"),
        ("ù[", "ளெ"),
        ("ள்[", "ள்ள"),
        ("ா[", "ாள"),
        ("ி[", "ிள"),
        ("ு[", "ுள"),
        ("[ô", "ளா"),
        ("ú[", "ளே"),
        ("[", "ள"),
    ]

    for old, new in replacements:
        text = text.replace(old, new)

    # Collapse accidental double spaces introduced by cleanup.
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text


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


def build_catalog(
    input_path: Path,
    output_path: Path,
    converter_name: str,
    unicode_text_out: Optional[Path],
) -> None:
    raw_text = input_path.read_text(encoding="utf-8")
    normalized_text = normalize_legacy_text(raw_text=raw_text, converter_name=converter_name)
    normalized_text = cleanup_unicode_artifacts(normalized_text)
    if unicode_text_out is not None:
        unicode_text_out.parent.mkdir(parents=True, exist_ok=True)
        unicode_text_out.write_text(normalized_text, encoding="utf-8")

    pages = parse_pages(normalized_text)
    songs = [parse_song_from_page(page, content) for page, content in pages]

    payload = {
        "source": str(input_path),
        "song_count": len(songs),
        "songs": songs,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Converter: {converter_name}")
    if unicode_text_out is not None:
        print(f"Wrote unicode text: {unicode_text_out}")
    print(f"Built catalog with {len(songs)} songs: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build normalized song catalog JSON.")
    parser.add_argument(
        "--input",
        default="/workspace/data/songs_of_zion_extracted.txt",
        help="Input extracted text with page markers.",
    )
    parser.add_argument(
        "--output",
        default="/workspace/data/songs_of_zion_catalog.json",
        help="Output song catalog JSON.",
    )
    parser.add_argument(
        "--converter",
        default="dinamani",
        choices=["dinamani", "softview", "nakkeeran", "kavipriya"],
        help="Legacy Tamil encoding converter.",
    )
    parser.add_argument(
        "--unicode-text-out",
        default="/workspace/data/songs_of_zion_unicode.txt",
        help="Optional unicode normalized text output path.",
    )
    args = parser.parse_args()

    build_catalog(
        input_path=Path(args.input),
        output_path=Path(args.output),
        converter_name=args.converter,
        unicode_text_out=Path(args.unicode_text_out) if args.unicode_text_out else None,
    )


if __name__ == "__main__":
    main()
