#!/usr/bin/env python3
"""Minimal Songbook API server."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from flask import Flask, jsonify, request, send_from_directory

DATA_PATH = Path("/workspace/data/songs_of_zion_catalog.json")

app = Flask(__name__)


def load_catalog() -> Dict[str, object]:
    if not DATA_PATH.exists():
        return {"song_count": 0, "songs": []}
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def song_summary(song: Dict[str, object]) -> Dict[str, object]:
    return {
        "id": song["id"],
        "number": song["number"],
        "title": song["title"],
        "category": song["category"],
        "page": song["page"],
    }


@app.get("/api/health")
def health() -> object:
    return jsonify({"ok": True})


@app.get("/api/categories")
def categories() -> object:
    catalog = load_catalog()
    cats = sorted({song.get("category", "Uncategorized") for song in catalog.get("songs", [])})
    return jsonify({"categories": cats})


@app.get("/api/songs")
def songs() -> object:
    catalog = load_catalog()
    items: List[Dict[str, object]] = list(catalog.get("songs", []))

    q = request.args.get("q", "").strip().lower()
    category = request.args.get("category", "").strip()

    if q:
        items = [song for song in items if q in str(song.get("searchable_text", "")).lower()]
    if category:
        items = [song for song in items if song.get("category") == category]

    return jsonify(
        {
            "total": len(items),
            "songs": [song_summary(song) for song in items],
        }
    )


@app.get("/api/songs/<song_id>")
def song_detail(song_id: str) -> object:
    catalog = load_catalog()
    for song in catalog.get("songs", []):
        if song.get("id") == song_id:
            return jsonify(song)
    return jsonify({"error": "Song not found"}), 404


@app.get("/")
def index() -> object:
    return send_from_directory("/workspace", "index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
