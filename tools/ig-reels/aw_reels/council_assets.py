from __future__ import annotations

from pathlib import Path

import yaml

from .config import ROOT

DEFAULT_MANIFEST = ROOT / "assets" / "council" / "manifest.yaml"


MAX_REFERENCE_IMAGES = 7


def load_reference_paths(manifest: Path | None = None, *, max_images: int = MAX_REFERENCE_IMAGES) -> list[Path]:
    """Ścieżki PNG w kolejności montażu (tylko wpisy z plikiem, limit xAI)."""
    path = manifest or DEFAULT_MANIFEST
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    base = path.parent
    out: list[Path] = []
    for entry in data.get("order", []):
        if entry.get("reference") is False:
            continue
        fname = entry.get("file")
        if not fname:
            continue
        p = base / fname
        if not p.is_file():
            raise FileNotFoundError(f"Brak portretu: {p}")
        out.append(p)
        if len(out) >= max_images:
            break
    return out
