from __future__ import annotations

from .connectors.clinicaltrials import ClinicalTrials
from .connectors.courtlistener import CourtListener
from .connectors.epu import Epu
from .connectors.federal_register import FederalRegister
from .connectors.gdelt import Gdelt
from .connectors.gpr import Gpr
from .connectors.kalshi import Kalshi
from .connectors.ofac_sdn import OfacSdn
from .connectors.polymarket import Polymarket
from .connectors.portwatch import PortWatch
from .connectors.usaspending import UsaSpending
from .connectors.warn_tx import WarnTx
from .core.base import Connector

CONNECTORS: dict[str, type[Connector]] = {
    c.name: c
    for c in (
        Polymarket,
        Kalshi,
        FederalRegister,
        OfacSdn,
        Gdelt,
        Gpr,
        Epu,
        WarnTx,
        UsaSpending,
        PortWatch,
        ClinicalTrials,
        CourtListener,
    )
}


def make(name: str, config: dict) -> Connector:
    if name not in CONNECTORS:
        raise KeyError(f"unknown connector {name!r}; available: {', '.join(sorted(CONNECTORS))}")
    cfg = dict(config.get(name, {}))
    # the shared watchlist rides along so connectors can shape their queries
    cfg.setdefault("watchlist", config.get("watchlist", {}))
    return CONNECTORS[name](cfg)
