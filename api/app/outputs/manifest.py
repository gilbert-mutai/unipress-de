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


def citation_for(filename: str) -> str:
    """The source paper as one readable citation line.

    Templates used to assemble this themselves, which meant two of them could
    disagree, and one printed the raw dictionary because it interpolated the whole
    mapping. Building the string once keeps both views identical and correct.

    Reads as: Authors. Title. Venue. DOI. Licence.
    """
    a = attribution_for(filename)
    parts: list[str] = []

    authors = a.get("authors") or []
    if authors:
        listed = ", ".join(authors[:6])
        parts.append(f"{listed}, et al." if len(authors) > 6 else f"{listed}.")

    title = (a.get("title") or "").strip().rstrip(".")
    if title:
        parts.append(f"{title}.")

    for field, label in (("venue", ""), ("doi", "DOI: "), ("license", "Licence: ")):
        value = a.get(field)
        if value:
            parts.append(f"{label}{str(value).strip().rstrip('.')}.")

    return " ".join(parts)
