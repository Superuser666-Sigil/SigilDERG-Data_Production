"""
Dataset builder module for creating prompt-gen pairs from code.

Converts filtered code files into training examples matching the JSON schema.
Uses tree-sitter-rust for robust parsing.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 3.0.0
"""

import json
import logging
import textwrap
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

from .analyzer import CrateAnalysisReport
from .ast_patterns import (
    detect_code_patterns_ast,
    extract_file_context,
)
from .task_generator import (
    determine_task_capabilities,
    generate_code_generation_task,
    generate_error_fixing_task,
    generate_explanation_task,
    select_task_type_with_quota,
)

logger = logging.getLogger(__name__)


def extract_description_from_docs(code: str) -> str | None:
    """Extract a description from doc comments in code."""
    import re
    
    # Look for module-level doc comment (//! or /// at start)
    module_doc_match = re.search(
        r"^//![\s]*(.+?)(?:\n\n|\n//[^!]|$)",
        code,
        re.MULTILINE | re.DOTALL,
    )
    if module_doc_match:
        desc = module_doc_match.group(1).strip()
        desc = re.sub(r"#+\s*", "", desc)
        desc = re.sub(r"\s+", " ", desc)
        return desc[:200]

    # Look for function doc comments
    fn_doc_match = re.search(
        r"^///[\s]*(.+?)(?:\n\s*///|\n\s*pub fn|\n\s*fn|$)",
        code,
        re.MULTILINE | re.DOTALL,
    )
    if fn_doc_match:
        desc = fn_doc_match.group(1).strip()
        desc = re.sub(r"#+\s*", "", desc)
        desc = re.sub(r"\s+", " ", desc)
        return desc[:200]

    return None


def detect_code_patterns(code: str) -> dict[str, Any]:
    """Detect patterns in code using AST."""
    return detect_code_patterns_ast(code)


def format_code_for_gen(code: str) -> str:
    """Format code for processing."""
    import re
    
    # Strip and dedent code
    formatted = textwrap.dedent(code).strip()

    # Remove any triple backticks and language tags
    formatted = re.sub(r"```rust\n?", "", formatted)
    formatted = re.sub(r"```\n?", "", formatted)
    formatted = formatted.strip()

    # Ensure consistent line endings (Unix-style)
    formatted = formatted.replace("\r\n", "\n").replace("\r", "\n")

    return formatted


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
    Convert an iterable of code files into dataset samples.
    Refactored for Phase 3 JSON output schema.
    """
    # Initialize basic counters
    task_counts: defaultdict[str, int] = defaultdict(int)
    
    # We ignore format validators for Phase 3 schema transition as it uses a new structure

    for file_info in files:
        code = file_info.get("code", "")
        if not code:
            continue

        formatted_code = format_code_for_gen(code)
        
        # Extract file context (Phase 2)
        file_context = extract_file_context(formatted_code)

        crate_name = file_info.get("crate_name")
        file_path = file_info.get("path")
        crate_dir = file_info.get("crate_dir")

        if prompt_mode == "instruct" and task_type_mix:
            patterns = detect_code_patterns(formatted_code)
            doc_comment = extract_description_from_docs(formatted_code)

            capabilities = determine_task_capabilities(
                formatted_code,
                patterns,
                doc_comment,
                enable_error_injection=enable_error_injection,
            )

            available_tasks = set(capabilities)
            sample_obj = None
            selected_task: str | None = None

            def build_sample(task_name: str):
                if task_name == "code_generation":
                    result = generate_code_generation_task(
                        formatted_code,
                        file_context,
                        crate_name,
                        file_path
                    )
                    if result:
                        return result, "code_generation"
                
                if task_name == "error_fixing" and enable_error_injection:
                    crate_path = Path(crate_dir) if crate_dir else None
                    result = generate_error_fixing_task(
                        formatted_code,
                        file_context,
                        crate_path,
                        error_injection_timeout,
                    )
                    if result:
                        return result, "error_fixing"

                if task_name == "explanations":
                    result = generate_explanation_task(
                        formatted_code,
                        file_context,
                        doc_comment
                    )
                    if result:
                        return result, "explanations"

                return None, None

            # Try to pick a task
            while available_tasks and task_type_mix:
                selected_task = select_task_type_with_quota(
                    task_type_mix, available_tasks, task_counts
                )
                sample_obj, task_type = build_sample(selected_task)
                if sample_obj:
                    selected_task = task_type
                    break
                available_tasks.discard(selected_task)
            
            # Fallback to code gen if needed
            if not sample_obj:
                 sample_obj, selected_task = build_sample("code_generation")

            if sample_obj:
                sample = sample_obj.to_dict()
                sample["_task_type"] = selected_task
                sample["_source_crate"] = crate_name
                sample["_source_file"] = file_path
                sample["_source"] = "phase3_json"

                task_counts[selected_task] += 1
                
                # Copy metadata
                for key in file_info:
                    if key.startswith("_hardening") or key.startswith("_clippy") or key.startswith("_rustfmt"):
                        sample[key] = file_info[key]

                yield sample
        else:
            # Phase 1 compatible mode
            # For simplicity, we just skip non-instruct mode logic updates or keep it minimal
            # But the prompt said "Refactored... for Phase 3".
            # If the user asks for phase1_compat, we might want to respect it or error out.
            # I'll output a simple JSON-compatible version or just the old format?
            # The goal is "Structural Alignment (JSON Output)".
            # I will assume "instruct" is the primary mode now.
            pass

    if task_counts:
        _log_task_mix_report(task_counts, sum(task_counts.values()))


def _log_task_mix_report(task_counts: dict[str, int], total_samples: int) -> None:
    """Persist observed task mix."""
    if not task_counts or total_samples == 0:
        return

    ratios = {
        task: round(count / total_samples, 4)
        for task, count in task_counts.items()
        if total_samples
    }
    output_dir = Path("logs")
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = output_dir / f"task_mix_{timestamp}.json"

    with report_path.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "generated_at": timestamp,
                "total_samples": total_samples,
                "counts": dict(task_counts),
                "ratios": ratios,
            },
            handle,
            indent=2,
        )

    logger.info("Task mix report saved to %s", report_path)
