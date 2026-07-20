"""Attribution lookup from data/manifest.yaml (docs/06).

Best-effort: matches an uploaded document to a manifest entry by filename and
returns title/authors/DOI/license for the output footer. If the manifest is
absent or the file isn't listed, returns a minimal attribution from the filename
so rendering never fails.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.core.settings import get_settings

log = get_logger("outputs.manifest")


@lru_cache
def _load_manifest(path: str) -> dict[str, dict[str, Any]]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        log.info("manifest.missing", path=path)
        return {}
    import yaml

    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return {doc["file"]: doc for doc in data.get("documents", []) if "file" in doc}


def attribution_for(filename: str) -> dict[str, Any]:
    entry = _load_manifest(get_settings().manifest_path).get(filename)
    if entry is None:
        return {"title": filename, "authors": [], "doi": None, "license": None}
    return {
        "title": entry.get("title", filename),
        "authors": entry.get("authors", []),
        "doi": entry.get("doi"),
        "license": entry.get("license"),
        "venue": entry.get("venue"),
    }
