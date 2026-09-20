from __future__ import annotations

from .connectors.attention import HnMentions, WikiPageviews
from .connectors.cftc_cot import CftcCot
from .connectors.clinicaltrials import ClinicalTrials
from .connectors.courtlistener import CourtListener
from .connectors.crtsh import CrtSh
from .connectors.defillama import DefiLlama
from .connectors.edgar_ownership import EdgarOwnership
from .connectors.epu import Epu
from .connectors.fca_shorts import FcaShorts
from .connectors.federal_register import FederalRegister
from .connectors.gdelt import Gdelt
from .connectors.gpr import Gpr
from .connectors.kalshi import Kalshi
from .connectors.liquidity import NyFedRrp, TreasuryTga
from .connectors.ofac_sdn import OfacSdn
from .connectors.openfda_recalls import OpenFdaRecalls
from .connectors.polymarket import Polymarket
from .connectors.portwatch import PortWatch
from .connectors.regsho_threshold import RegShoThreshold
from .connectors.usaspending import UsaSpending
from .connectors.usgs_quakes import UsgsQuakes
from .connectors.warn_tx import WarnTx
from .core.base import Connector

CONNECTORS: dict[str, type[Connector]] = {
    c.name: c
    for c in (
        OfacSdn,
        CourtListener,
        FederalRegister,
        EdgarOwnership,
        RegShoThreshold,
        FcaShorts,
        CftcCot,
        WarnTx,
        ClinicalTrials,
        OpenFdaRecalls,
        UsaSpending,
        NyFedRrp,
        TreasuryTga,
        Gpr,
        Epu,
        PortWatch,
        UsgsQuakes,
        DefiLlama,
        CrtSh,
        HnMentions,
        WikiPageviews,
        Polymarket,
        Kalshi,
        Gdelt,
    )
}


def make(name: str, config: dict) -> Connector:
    if name not in CONNECTORS:
        raise KeyError(f"unknown connector {name!r}; available: {', '.join(sorted(CONNECTORS))}")
    cfg = dict(config.get(name, {}))
    # the shared watchlist rides along so connectors can shape their queries
    cfg.setdefault("watchlist", config.get("watchlist", {}))
    return CONNECTORS[name](cfg)
