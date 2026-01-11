"""
Schema definitions for the Sigil pipeline.

Defines the structure of training samples and output formats.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.6.0
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class TrainingSample:
    """
    Represents a single training sample for the model.
    Matches the "good" dataset schema.
    """

    system: str
    """System prompt (e.g. "You are a Rust expert...")."""

    instruction: str
    """The task instruction (e.g. "Fix this code...")."""

    input_context: str
    """Context information: Imports, Structs, Enums, etc."""

    input_code: str
    """The target function signature (for code gen) or broken code (for fixing)."""

    output_json: dict[str, Any]
    """The expected JSON response containing the code and/or explanation."""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "system": self.system,
            "instruction": self.instruction,
            "input_context": self.input_context,
            "input_code": self.input_code,
            "output_json": self.output_json,
        }
