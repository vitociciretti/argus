from __future__ import annotations

import pathlib
import tomllib

DEFAULT_PATH = pathlib.Path("argus.toml")


def load(path: str | pathlib.Path | None = None) -> dict:
    p = pathlib.Path(path) if path else DEFAULT_PATH
    if not p.exists():
        return {}
    return tomllib.loads(p.read_text())
