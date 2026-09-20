from __future__ import annotations

import pathlib
import tomllib

DEFAULT_PATH = pathlib.Path("argus.toml")
LOCAL_PATH = pathlib.Path("argus.local.toml")  # gitignored: emails, api tokens


def _read(p: pathlib.Path) -> dict:
    if not p.exists():
        return {}
    return tomllib.loads(p.read_text())


def load(path: str | pathlib.Path | None = None) -> dict:
    """argus.toml overlaid by argus.local.toml (per-section shallow merge)."""
    base = _read(pathlib.Path(path) if path else DEFAULT_PATH)
    for section, values in _read(LOCAL_PATH).items():
        if isinstance(values, dict) and isinstance(base.get(section), dict):
            base[section] = {**base[section], **values}
        else:
            base[section] = values
    return base
