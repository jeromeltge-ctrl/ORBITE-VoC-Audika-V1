"""Compatibilite temporaire ORBITE Questions additionnelles.

Le moteur actif est orb_q_analysis_v2.py. Ce module conserve l'ancien
nom d'import sans dupliquer les calculs. Ne pas supprimer la V2.
"""
from orb_q_analysis_v2 import (  # noqa: F401
    normalize_campaign,
    historical_catalog,
    filter_options,
    analyze_occurrence,
    dashboard_export,
)

__all__ = [
    'normalize_campaign',
    'historical_catalog',
    'filter_options',
    'analyze_occurrence',
    'dashboard_export',
]
