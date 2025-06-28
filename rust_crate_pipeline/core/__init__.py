"""
Core Sigil Protocol Components

This module contains the foundational components for the Sigil Protocol
implementation, providing shared functionality across all pipeline variants.
"""

from .sacred_chain import SacredChainBase, SacredChainTrace, TrustVerdict
from .canon_registry import CanonRegistry, CanonEntry
from .irl_engine import IRLEngine

__all__ = [
    "SacredChainBase",
    "SacredChainTrace", 
    "TrustVerdict",
    "CanonRegistry",
    "CanonEntry",
    "IRLEngine",
] 