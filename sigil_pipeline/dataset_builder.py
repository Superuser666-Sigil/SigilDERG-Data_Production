"""
Dataset builder module for creating prompt-gen pairs from code.

Converts filtered code files into training examples with prompts and code.
Matches Phase 1 format exactly for consistent tokenization and training.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.0.0
"""

import json
import logging
import re
import textwrap
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Iterator

from .analyzer import CrateAnalysisReport
from .format_validator import FormatValidator
from .task_generator import (
    determine_task_capabilities,
    generate_error_fixing_task,
    generate_explanation_task,
    generate_transformation_task,
    select_task_type_with_quota,
)

logger = logging.getLogger(__name__)


def extract_description_from_docs(code: str) -> str | None:
    """
    Extract a description from doc comments in code.

    Args:
        code: Code content with potential doc comments

    Returns:
        Description string or None if not found
    """
    # Look for module-level doc comment (//! or /// at start)
    module_doc_match = re.search(
        r"^//![\s]*(.+?)(?:\n\n|\n//[^!]|$)",
        code,
        re.MULTILINE | re.DOTALL,
    )
    if module_doc_match:
        desc = module_doc_match.group(1).strip()
        # Clean up markdown and extra whitespace
        desc = re.sub(r"#+\s*", "", desc)  # Remove markdown headers
        desc = re.sub(r"\s+", " ", desc)  # Normalize whitespace
        return desc[:200]  # Limit length

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
    """
    Detect patterns in code to help generate better prompts.

    Args:
        code: Code content

    Returns:
        Dictionary of detected patterns
    """
    patterns = {
        "has_main": "fn main" in code,
        "has_async": "async fn" in code or "tokio::" in code or "async-std" in code,
        "has_error_handling": "anyhow" in code
        or "Result<" in code
        or ".unwrap()" in code
        or ".expect(" in code,
        "has_serde": "serde" in code.lower()
        or "Serialize" in code
        or "Deserialize" in code,
        "has_iterators": ".iter()" in code
        or ".map(" in code
        or ".filter(" in code
        or ".collect()" in code,
        "has_collections": "Vec<" in code
        or "HashMap<" in code
        or "HashSet<" in code
        or "BTreeMap<" in code,
        "has_strings": "String::" in code or "&str" in code or ".to_string()" in code,
        "has_io": "std::io" in code or "File::" in code or "read_line" in code,
        "has_networking": "http" in code.lower()
        or "reqwest" in code.lower()
        or "hyper" in code.lower(),
        "has_concurrency": "thread::" in code
        or "Arc<" in code
        or "Mutex<" in code
        or "RwLock<" in code,
        "function_names": re.findall(r"fn\s+(\w+)", code),
    }
    return patterns


def generate_prompt_for_code(
    code: str,
    crate_name: str | None = None,
    analysis: CrateAnalysisReport | None = None,
    file_path: str | None = None,
) -> str:
    """
    Generate an instruction prompt for the given code snippet matching Phase 1 style.

    Phase 1 uses the exact format: "Write a Rust code snippet. Output only the code."
    (100% of samples use this exact prompt)

    Args:
        code: Code content
        crate_name: Name of the crate (optional, not used in Phase 1 format)
        analysis: Crate analysis report (optional, not used in Phase 1 format)
        file_path: Path to the file (optional, not used in Phase 1 format)

    Returns:
        Instruction prompt string matching Phase 1 format exactly
    """
    # Phase 1 dataset analysis shows 100% of samples use this exact format
    return "Write a Rust code snippet. Output only the code."


def create_prompt_from_code(
    code: str,
    crate_name: str | None = None,
    file_path: str | None = None,
) -> str:
    """
    Generate an instruct-style prompt from code for Phase-2 dataset.

    Creates human-readable instructions based on doc comments, code patterns,
    and function signatures. Does NOT include "Output only the code" suffix.

    Args:
        code: Code snippet content
        crate_name: Name of the crate (optional)
        file_path: Path to the file (optional)

    Returns:
        Natural language instruction prompt
    """
    # Extract doc comment
    doc_desc = extract_description_from_docs(code)

    # Detect patterns
    patterns = detect_code_patterns(code)

    # Extract function signature if available
    fn_signature_match = re.search(
        r"(?:pub\s+)?(?:async\s+)?fn\s+(\w+)\s*\(([^)]*)\)\s*(?:->\s*([^{]+))?",
        code,
        re.MULTILINE,
    )

    # Generate prompt based on detected patterns
    if doc_desc:
        # Use doc comment as basis for prompt
        # Clean up and convert to instruction format
        desc = doc_desc.strip()
        # Remove common doc comment prefixes
        desc = re.sub(r"^(///|//!)\s*", "", desc, flags=re.MULTILINE)
        desc = re.sub(r"\s+", " ", desc)

        if fn_signature_match:
            fn_name = fn_signature_match.group(1)
            params = fn_signature_match.group(2)
            return_type = fn_signature_match.group(3)

            if return_type:
                return_type = return_type.strip()
                return f"Write a Rust function {fn_name}({params}) -> {return_type}. {desc}"
            return f"Write a Rust function {fn_name}({params}). {desc}"
        return f"Write Rust code that: {desc}"

    # Pattern-based prompts
    if patterns.get("has_async"):
        if fn_signature_match:
            fn_name = fn_signature_match.group(1)
            return f"Using Tokio, write an async function {fn_name} that handles asynchronous operations."
        return (
            "Using Tokio, write an async function that handles asynchronous operations."
        )

    if patterns.get("has_serde"):
        struct_match = re.search(r"struct\s+(\w+)", code)
        if struct_match:
            struct_name = struct_match.group(1)
            # Try to extract fields
            fields_match = re.search(r"struct\s+\w+\s*\{([^}]+)\}", code, re.DOTALL)
            if fields_match:
                fields = fields_match.group(1)
                # Extract field names and types
                field_parts = []
                for field_line in fields.split("\n"):
                    field_line = field_line.strip()
                    if field_line and not field_line.startswith("//"):
                        # Match "field_name: Type" or "pub field_name: Type"
                        field_match = re.search(
                            r"(?:pub\s+)?(\w+)\s*:\s*([^,]+)", field_line
                        )
                        if field_match:
                            field_name = field_match.group(1)
                            field_type = field_match.group(2).strip()
                            field_parts.append(f"{field_name}: {field_type}")

                if field_parts:
                    fields_str = ", ".join(field_parts)
                    return f"Implement a struct {struct_name} with {fields_str}, derive Serialize and Deserialize with Serde."

            return f"Implement a struct {struct_name} with Serialize and Deserialize derives using Serde."
        return "Implement a Rust struct with Serialize and Deserialize derives using Serde."

    if patterns.get("has_error_handling"):
        if fn_signature_match:
            fn_name = fn_signature_match.group(1)
            return f"Write a Rust function {fn_name} that handles errors using Result types."
        return "Write a Rust function that handles errors using Result types."

    if patterns.get("has_iterators"):
        if fn_signature_match:
            fn_name = fn_signature_match.group(1)
            return f"Write a Rust function {fn_name} that processes a vector using iterators."
        return "Write a Rust function that processes a vector using iterators."

    if patterns.get("has_io"):
        if fn_signature_match:
            fn_name = fn_signature_match.group(1)
            return f"Write a Rust function {fn_name} that performs file I/O operations."
        return "Write a Rust function that performs file I/O operations."

    if patterns.get("has_networking"):
        if fn_signature_match:
            fn_name = fn_signature_match.group(1)
            return f"Write a Rust function {fn_name} that makes HTTP requests."
        return "Write a Rust function that makes HTTP requests."

    # Fallback: Extract function signature and create instruction
    if fn_signature_match:
        fn_name = fn_signature_match.group(1)
        params = fn_signature_match.group(2)
        return_type = fn_signature_match.group(3)

        if return_type:
            return_type = return_type.strip()
            return f"Write a Rust function {fn_name}({params}) -> {return_type}."
        else:
            return f"Write a Rust function {fn_name}({params})."

    # Final fallback
    return "Write a Rust code snippet."


def format_code_for_gen(code: str, phase1_spec: dict[str, Any] | None = None) -> str:
    """
    Format code for the 'gen' field to match Phase 1 format.

    Args:
        code: Raw code content
        phase1_spec: Phase 1 format specification (optional)

    Returns:
        Formatted code string
    """
    # Strip and dedent code
    formatted = textwrap.dedent(code).strip()

    # Check Phase 1 spec for backticks requirement
    if phase1_spec:
        code_formatting = phase1_spec.get("format_requirements", {}).get(
            "code_formatting", {}
        )
        has_backticks = code_formatting.get("has_backticks", False)

        # If Phase 1 didn't use backticks, ensure we don't have them
        if not has_backticks:
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
) -> Iterator[dict]:
    """
    Convert an iterable of code files into dataset samples (prompt-gen pairs).

    Matches Phase 1 format exactly: {"prompt": "...", "gen": "..."}
    Refactored to accept Iterable and yield (Priority 2.1 - Streaming Architecture).

    Args:
        files: Iterable of file dicts with 'path', 'code', and optionally 'crate_name'
        validate_format: Whether to validate samples against Phase 1 format
        phase1_spec_path: Path to Phase 1 format specification (optional)
        prompt_mode: Prompt generation mode ('phase1_compat' or 'instruct')
        task_type_mix: Task type distribution dictionary (for Phase-2)
        enable_error_injection: Enable error-fixing tasks (for Phase-2)
        error_injection_method: Error injection method ('real_compile', 'simulate', 'both')
        error_injection_timeout: Timeout (seconds) for cargo-based error injection

    Yields:
        Dicts with 'prompt' and 'gen' keys matching Phase 1 format
    """
    # Load format validator if needed
    validator = None
    phase1_spec = None
    if validate_format:
        validator = FormatValidator(phase1_spec_path, prompt_mode=prompt_mode)
        if validator.phase1_spec:
            phase1_spec = validator.phase1_spec

    validation_errors = []
    sample_count = 0
    task_counts: defaultdict[str, int] = defaultdict(int)

    for file_info in files:
        code = file_info.get("code", "")
        if not code:
            continue

        # Format code for gen field (match Phase 1 format)
        formatted_code = format_code_for_gen(code, phase1_spec)

        # Generate prompt and gen based on mode and task type
        crate_name = file_info.get("crate_name")
        file_path = file_info.get("path")
        crate_dir = file_info.get("crate_dir")  # Optional, for error injection

        if prompt_mode == "instruct" and task_type_mix:
            patterns = detect_code_patterns(formatted_code)
            doc_comment = extract_description_from_docs(formatted_code)

            capabilities = determine_task_capabilities(
                formatted_code,
                patterns,
                doc_comment,
                enable_error_injection=enable_error_injection,
                error_injection_method=error_injection_method,
            )

            available_tasks = set(capabilities)
            sample_dict = None
            selected_task: str | None = None

            def build_sample(task_name: str) -> dict[str, Any] | None:
                if task_name == "code_generation":
                    prompt_local = create_prompt_from_code(
                        formatted_code, crate_name, file_path
                    )
                    return {
                        "prompt": prompt_local,
                        "gen": formatted_code,
                        "_task_type": "code_generation",
                    }

                if task_name == "transformations":
                    result = generate_transformation_task(formatted_code, patterns)
                    if result:
                        result["_task_type"] = "transformations"
                    return result

                if task_name == "error_fixing" and enable_error_injection:
                    crate_path = Path(crate_dir) if crate_dir else None
                    result = generate_error_fixing_task(
                        formatted_code,
                        error_injection_method,
                        crate_path,
                        error_injection_timeout,
                    )
                    if result:
                        result["_task_type"] = "error_fixing"
                    return result

                if task_name == "explanations":
                    result = generate_explanation_task(formatted_code, doc_comment)
                    if result:
                        result["_task_type"] = "explanations"
                    return result

                return None

            while available_tasks and task_type_mix:
                selected_task = select_task_type_with_quota(
                    task_type_mix, available_tasks, task_counts
                )
                sample_dict = build_sample(selected_task)
                if sample_dict:
                    break
                available_tasks.discard(selected_task)

            if not sample_dict:
                sample_dict = build_sample("code_generation")
                selected_task = "code_generation"

            sample = sample_dict or {
                "prompt": create_prompt_from_code(
                    formatted_code, crate_name, file_path
                ),
                "gen": formatted_code,
                "_task_type": "code_generation",
            }

            sample["_source_crate"] = crate_name
            sample["_source_file"] = file_path
            sample["_source"] = "phase2"

            if sample["_task_type"]:
                task_counts[sample["_task_type"]] += 1
            else:
                task_counts["code_generation"] += 1

        else:
            # Phase 1 compatible mode
            prompt = generate_prompt_for_code(
                formatted_code, crate_name, None, file_path
            )
            sample = {
                "prompt": prompt,
                "gen": formatted_code,
                "_source_crate": crate_name,
                "_source_file": file_path,
                "_source": "phase1_compat",  # Mark as Phase-1 compatible source
            }

        # Validate format if requested
        if validator:
            is_valid, errors = validator.validate_sample(
                sample, max_lines=max_sft_lines, max_chars=max_sft_chars
            )
            if not is_valid:
                validation_errors.append(
                    {
                        "file": file_path,
                        "errors": errors,
                    }
                )
                logger.debug(f"Format validation failed for {file_path}: {errors}")
                # Continue anyway, but log the error

        sample_count += 1
        yield sample

    if task_counts:
        _log_task_mix_report(task_counts, sum(task_counts.values()))

    if validation_errors:
        logger.warning(
            f"Format validation found {len(validation_errors)} samples with issues. "
            f"Check logs for details."
        )


def _log_task_mix_report(task_counts: dict[str, int], total_samples: int) -> None:
    """Persist observed task mix for downstream monitoring."""
    if not task_counts or total_samples == 0:
        return

    ratios = {
        task: round(count / total_samples, 4)
        for task, count in task_counts.items()
        if total_samples
    }
    output_dir = Path("logs")
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
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
    logger.info("Observed task mix ratios: %s", ratios)
