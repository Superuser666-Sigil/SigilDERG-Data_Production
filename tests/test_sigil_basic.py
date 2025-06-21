"""
Simple test to verify pytest works with sigil_compliant_analyzer
"""

from sigil_compliant_analyzer import TrustVerdict, SacredChainTrace, CanonEntry
import sys
from pathlib import Path

# Add the project root to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_basic_import():
    """Test that basic imports work"""
    assert TrustVerdict.ALLOW.value == "ALLOW"


def test_sacred_chain_trace_basic():
    """Test basic SacredChainTrace creation"""
    trace = SacredChainTrace(
        input_data="test",
        context_sources=["test"],
        reasoning_steps=["test"],
        suggestion="test",
        verdict=TrustVerdict.ALLOW,
        audit_info={},
        irl_score=8.0,
        execution_id="test",
        timestamp="2024-01-01T00:00:00Z",
        canon_version="1.0"
    )
    assert trace.input_data == "test"


def test_canon_entry_basic():
    """Test basic CanonEntry creation"""
    entry = CanonEntry(
        source="test",
        version="1.0",
        authority_level=5,
        content_hash="hash",
        last_validated="2024-01-01T00:00:00Z"
    )
    assert entry.source == "test"
    assert entry.is_valid() is True
