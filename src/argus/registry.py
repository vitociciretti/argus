from __future__ import annotations

from .connectors.federal_register import FederalRegister
from .connectors.gdelt import Gdelt
from .connectors.ofac_sdn import OfacSdn
from .connectors.polymarket import Polymarket
from .core.base import Connector

CONNECTORS: dict[str, type[Connector]] = {
    c.name: c for c in (Polymarket, FederalRegister, OfacSdn, Gdelt)
}


def make(name: str, config: dict) -> Connector:
    if name not in CONNECTORS:
        raise KeyError(f"unknown connector {name!r}; available: {', '.join(sorted(CONNECTORS))}")
    cfg = dict(config.get(name, {}))
    # the shared watchlist rides along so connectors can shape their queries
    cfg.setdefault("watchlist", config.get("watchlist", {}))
    return CONNECTORS[name](cfg)
