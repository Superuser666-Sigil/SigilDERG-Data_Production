"""
Dataset builder module for creating prompt-gen pairs from code.
Refactored to support 'Context -> JSON' format for high-quality Rust fine-tuning.
"""

import json
import logging
import re
import textwrap
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

from .analyzer import CrateAnalysisReport
from .ast_patterns import (
    extract_context_header,
)
from .format_validator import FormatValidator
from .task_generator import (
    generate_explanation_task,
    generate_error_fixing_task
)

logger = logging.getLogger(__name__)

def extract_description_from_docs(code: str) -> str | None:
    """Extract a description from doc comments in code."""
    module_doc_match = re.search(r"^//![\s]*(.+?)(?:\n\n|\n//[^!]|$)", code, re.MULTILINE | re.DOTALL)
    if module_doc_match:
        return module_doc_match.group(1).strip()[:500]

    fn_doc_match = re.search(r"^///[\s]*(.+?)(?:\n\s*///|\n\s*pub fn|\n\s*fn|$)", code, re.MULTILINE | re.DOTALL)
    if fn_doc_match:
        return fn_doc_match.group(1).strip()[:500]
    return None

def format_code_for_gen(code: str, phase1_spec: dict[str, Any] | None = None) -> str:
    """Format code to be clean strings."""
    formatted = textwrap.dedent(code).strip()
    formatted = re.sub(r"```rust\n?", "", formatted)
    formatted = re.sub(r"```\n?", "", formatted)
    return formatted.strip()

def build_dataset_entries(
    files: Iterable[dict],
    validate_format: bool = True,
    phase1_spec_path: Path | None = None,
    prompt_mode: str = "phase1_compat",
    task_type_mix: dict[str, float] | None = None,
    enable_error_injection: bool = True,
    error_injection_method: str = "both",
    error_injection_timeout: int = 120,
    max_sft_lines: int | None = None,
    max_sft_chars: int | None = None,
    prompt_seed: int | None = None,
    enable_prompt_randomization: bool = True,
) -> Iterator[dict]:
    """
    Convert code files into dataset samples with strict JSON output format.
    """
    
    for file_info in files:
        code = file_info.get("code", "")
        if not code:
            continue

        formatted_code = format_code_for_gen(code)
        
        # 1. Extract Context (Imports/Structs) using AST
        try:
            # extract_context_header returns imports/structs/enums for surrounding context
            context_header = extract_context_header(formatted_code)
        except Exception:
            context_header = ""  # Fallback if parsing fails

        doc_comment = extract_description_from_docs(formatted_code)

        # 2. Base Sample Structure (Context + JSON Output)
        sample = {
            "crate_name": file_info.get("crate_name"),
            "input_data": {
                "code": formatted_code,
                "code_context": context_header,
                # Default prompt if no specific task overrides it
                "prompt": "Write idiomatic Rust code based on the context." 
            },
            # Output MUST be JSON string to match your good dataset
            "output_data": json.dumps({
                "code": formatted_code
            }), 
            "task_category": "code_generation",
            "test": "" 
        }

        # 3. Handle Instruct/Task Generation
        if prompt_mode == "instruct":
            # Attempt to generate specific tasks
            
            # A. Documentation Task
            task_result = generate_explanation_task(formatted_code, doc_comment)
            
            # B. Error Fixing Task (Only if enabled and capable)
            if not task_result and enable_error_injection:
                # Ensure we pass a proper path or None (avoid passing None into Path())
                crate_dir_val = file_info.get("crate_dir")
                crate_path = Path(str(crate_dir_val)) if crate_dir_val else None
                task_result = generate_error_fixing_task(
                    formatted_code, 
                    error_injection_method, 
                    crate_path, 
                    error_injection_timeout
                )

            # Apply Task Overrides
            if task_result:
                sample["input_data"]["prompt"] = task_result["instruction"]
                
                # Override input code if the task modified it (e.g. broken code)
                if "input_code" in task_result:
                    sample["input_data"]["code"] = task_result["input_code"]
                
                # Serialize the structured output (The Fix / The Docs)
                sample["output_data"] = json.dumps(task_result["output_json"])
                sample["task_category"] = task_result["_task_type"]

        yield sample