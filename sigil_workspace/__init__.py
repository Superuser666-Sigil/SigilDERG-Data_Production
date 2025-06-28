"""
Sigil Data Workspace - Rule Zero Compliant Data Processing

A comprehensive workspace for data processing with Sacred Chain traceability,
AI integration, and complete audit capabilities.
"""

__version__ = "1.3.0"
__author__ = "Rule Zero Compliant Developer"

from .core.pipeline import DataPipeline
from .core.config import WorkspaceConfig, SacredChainConfig
from .core.sacred_chain import SacredChain, ChainLink
from .processors.base import BaseProcessor
from .processors.ai_processor import AIProcessor
from .processors.validator import DataValidator

__all__ = [
    "DataPipeline",
    "WorkspaceConfig",
    "SacredChainConfig",
    "SacredChain",
    "ChainLink",
    "BaseProcessor",
    "AIProcessor",
    "DataValidator",
]
