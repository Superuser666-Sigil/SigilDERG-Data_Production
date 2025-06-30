"""Common types and data structures for the Rust Crate Pipeline.

This module contains shared types and data structures used across multiple
components to eliminate redundancy and ensure consistency.
"""

from dataclasses import dataclass
from typing import Optional, TypedDict


class Section(TypedDict, total=True):
    """Represents a structured section of content with priority."""
    heading: str
    content: str
    priority: int


@dataclass
class LLMRequest:
    """Standard request structure for LLM operations."""
    prompt: str
    temperature: float = 0.2
    max_tokens: int = 256
    system_message: Optional[str] = None
    task_type: str = "general"


@dataclass
class LLMResponse:
    """Standard response structure for LLM operations."""
    content: str
    success: bool
    error_message: Optional[str] = None
    tokens_used: Optional[int] = None
    model_used: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of validation operations."""
    is_valid: bool
    error_message: Optional[str] = None
    confidence_score: Optional[float] = None


# Common priority mappings for content sections
SECTION_PRIORITIES = {
    'usage': 10,
    'example': 10,
    'getting_started': 10,
    'features': 9,
    'overview': 9,
    'about': 9,
    'installation': 8,
    'setup': 8,
    'configuration': 8,
    'api': 7,
    'interface': 7,
    'default': 5
}


def get_section_priority(heading: str) -> int:
    """Get priority for a section based on its heading."""
    heading_lower = heading.lower()

    for keyword, priority in SECTION_PRIORITIES.items():
        if keyword in heading_lower:
            return priority

    return SECTION_PRIORITIES['default']
