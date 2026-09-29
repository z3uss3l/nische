"""Research lenses: reusable domain-specific analysis contracts."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass(frozen=True)
class ResearchLens:
    name: str
    subject_type: str
    domains: tuple[str,...]
    probe_providers: tuple[str,...]
    discovery_modes: tuple[str,...]
    dimensions: tuple[str,...]
    validation_gates: tuple[str,...]
    dashboard_panels: tuple[str,...]
    metadata: dict[str,Any]=field(default_factory=dict)


LENSES = {
    "generic": ResearchLens("Allgemeiner Markt","market",
        ("demand","supply","commerce","prices","social","events","calendar","regulation"),
        ("amazon","ebay","price_comparison","web"),
        ("keyword","problem","audience","product","substitute","adjacent_market"),
        ("demand","supply_gap","competition","price","trend","seasonality","risk"),
        ("demand","competition","economics","access","legal"),
        ("Situation","Kalender","Timeline","Trends","Heatmap","Evidenz")),
    "pod": ResearchLens("T-Shirt / POD","design",
        ("demand","social","commerce","events","calendar","legal"),
        ("amazon","ebay","etsy","price_comparison","web"),
        ("keyword","occasion","audience","motif","style","adjacent_market"),
        ("trend","velocity","competition","review_barrier","price","event_lead_time","legal"),
        ("demand","competition","economics","trademark","timing"),
        ("Situation","Kalender","Trends","Heatmap","Evidenz")),
    "ebook": ResearchLens("E-Book / Publishing","content",
        ("demand","books","social","commerce","calendar","events"),
        ("amazon_books","google_books","web","reddit"),
        ("keyword","question","problem","audience","content_gap","adjacent_language"),
        ("search_intent","book_supply","review_barrier","price","freshness","pain","format_gap"),
        ("demand","content_gap","competition","economics","legal"),
        ("Situation","Kalender","Trends","Heatmap","Evidenz")),
    "marketplace": ResearchLens("Marketplace-Warenangebot","product",
        ("commerce","demand","supply","prices","logistics","calendar"),
        ("amazon","ebay","price_comparison","web"),
        ("product","accessory","consumable","replacement","substitute","bundle"),
        ("demand","availability","seller_count","price_index","margin","turnover","substitution"),
        ("demand","supply_gap","economics","access","legal"),
        ("Situation","Kalender","Timeline","Trends","Heatmap","Evidenz")),
    "finance": ResearchLens("Finanzdienstleistungen","service",
        ("finance","macro","regulation","news","funding"),
        ("web","regulatory","search"),
        ("problem","audience","regulatory_change","service_gap"),
        ("demand","rates","regulation","competition","trust","compliance"),
        ("demand","competition","economics","compliance"),
        ("Situation","Kalender","Timeline","Trends","Heatmap","Evidenz")),
}


def get_lens(key: str) -> ResearchLens:
    return LENSES.get(key, LENSES["generic"])
