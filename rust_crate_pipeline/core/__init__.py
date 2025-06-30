"""
Core Sigil Protocol Components

This module contains the foundational components for the Sigil Protocol
implementation, providing shared functionality across all pipeline variants.
"""

from .canon_registry import CanonEntry, CanonRegistry
from .irl_engine import IRLEngine
from .sacred_chain import SacredChainBase, SacredChainTrace, TrustVerdict

__all__ = [
    "SacredChainBase",
    "SacredChainTrace",
    "TrustVerdict",
    "CanonRegistry",
    "CanonEntry",
    "IRLEngine",
]
