"""Shared LLM utilities for the Rust Crate Pipeline.

This module contains common LLM processing utilities to eliminate
redundancy
across different LLM processors (ai_processing, azure_ai_processing, unified_llm_processor).
"""

import re
from typing import Callable, List, Optional

from .common_types import Section, get_section_priority


def estimate_tokens_simple(text: str) -> int:
    """Simple token estimation (4 characters per token)."""
    return len(text) // 4


def truncate_content_simple(content: str, max_tokens: int = 1000) -> str:
    """Simple content truncation by paragraphs."""
    paragraphs = content.split("\n\n")
    result, current_tokens = "", 0

    for para in paragraphs:
        tokens = estimate_tokens_simple(para)
        if current_tokens + tokens <= max_tokens:
            result += para + "\n\n"
            current_tokens += tokens
        else:
            break
    return result.strip()


def smart_truncate_content(content: str, max_tokens: int = 1000) -> str:
    """Intelligently truncate content to preserve important sections.

    This is the centralized implementation that was duplicated across
    ai_processing.py, azure_ai_processing.py, and unified_llm_processor.py.
    """
    if not content:
        return ""

    # If content is short enough, return it all
    if estimate_tokens_simple(content) <= max_tokens:
        return content

    # Split into sections based on markdown headers
    sections: List[Section] = []
    current_section: Section = {
        "heading": "Introduction",
        "content": "",
        "priority": 10,
    }

    for line in content.splitlines():
        if re.match(r"^#+\s+", line):  # It's a header
            # Save previous section if not empty
            if current_section["content"].strip():
                sections.append(current_section)

            # Create new section with appropriate priority
            heading = re.sub(r"^#+\s+", "", line)
            priority = get_section_priority(heading)

            current_section = {
                "heading": heading,
                "content": line + "\n",
                "priority": priority,
            }
        else:
            current_section["content"] += line + "\n"

            # Boost priority if code block is found
            if "```rust" in line or "```no_run" in line:
                current_section["priority"] = max(
                    current_section["priority"], 8)

    # Add the last section
    if current_section["content"].strip():
        sections.append(current_section)

    # Sort sections by priority (highest first)
    sections.sort(key=lambda x: x["priority"], reverse=True)

    # Build the result, respecting token limits
    result = ""
    tokens_used = 0

    for section in sections:
        section_text = f'## {section["heading"]}\n{section["content"]}\n'
        section_tokens = estimate_tokens_simple(section_text)

        if tokens_used + section_tokens <= max_tokens:
            result += section_text
            tokens_used += section_tokens
        elif tokens_used < max_tokens - 100:  # If we can fit a truncated version
            # Take what we can
            remaining_tokens = max_tokens - tokens_used
            # Simple truncation by characters
            max_chars = remaining_tokens * 4
            if len(section_text) > max_chars:
                result += section_text[:max_chars] + "..."
            else:
                result += section_text
            break

    return result


def clean_llm_output(output: str, task: str = "general") -> str:
    """Centralized output cleaning for LLM responses."""
    if not output:
        return ""

    # Remove any remaining prompt artifacts
    output = output.split("<|end|>")[0].strip()

    if task == "classification":
        # For classification tasks, extract just the category
        categories = [
            "AI",
            "Database",
            "Web Framework",
            "Networking",
            "Serialization",
            "Utilities",
            "DevTools",
            "ML",
            "Cryptography",
            "Unknown",
        ]
        for category in categories:
            if re.search(
                r"\b" +
                re.escape(category) +
                r"\b",
                output,
                    re.IGNORECASE):
                return category
        return "Unknown"

    elif task == "factual_pairs":
        # For factual pairs, ensure proper formatting
        pairs: List[str] = []
        facts = re.findall(r"✅\s*Factual:?\s*(.*?)(?=❌|\Z)", output, re.DOTALL)
        counterfacts = re.findall(
            r"❌\s*Counterfactual:?\s*(.*?)(?=✅|\Z)", output, re.DOTALL)

        # Pair them up
        for i in range(min(len(facts), len(counterfacts))):
            pairs.append(
                f"✅ Factual: {facts[i].strip()}\n"
                f"❌ Counterfactual: {counterfacts[i].strip()}"
            )

        return "\n\n".join(pairs)

    return output


def validate_classification_result(result: str) -> bool:
    """Validate classification results."""
    if not result:
        return False

    valid_categories = [
        "AI", "Database", "Web Framework", "Networking",
        "Serialization", "Utilities", "DevTools", "ML",
        "Cryptography", "Unknown"
    ]

    return any(category.lower() in result.lower()
               for category in valid_categories)


def validate_factual_pairs(result: str) -> bool:
    """Validate factual pairs format."""
    if not result:
        return False

    # Check for presence of both factual and counterfactual markers
    has_factual = "✅" in result or "Factual:" in result
    has_counterfactual = "❌" in result or "Counterfactual:" in result

    return has_factual and has_counterfactual


def simplify_prompt(prompt: str) -> str:
    """Simplify prompts by removing unnecessary complexity."""
    # Remove excessive whitespace
    prompt = re.sub(r'\s+', ' ', prompt)

    # Remove very verbose instructions
    prompt = re.sub(r'Please be extremely detailed.*?(?=\n|$)', '', prompt)
    prompt = re.sub(r'Remember to.*?(?=\n|$)', '', prompt)

    # Simplify complex sentence structures
    prompt = prompt.replace('In order to', 'To')
    prompt = prompt.replace('It is important that you', 'You should')

    return prompt.strip()


def validate_and_retry_llm_call(
    llm_call_func: Callable[..., Optional[str]],
    validation_func: Callable[[str], bool],
    max_retries: int = 3,
    *args,
    **kwargs
) -> Optional[str]:
    """Generic retry mechanism for LLM calls with validation.

    This eliminates the duplicate validate_and_retry methods across
    the different LLM processor classes.
    """
    for attempt in range(max_retries):
        try:
            result = llm_call_func(*args, **kwargs)
            if result and validation_func(result):
                return result

            # If validation fails, try with simplified prompt
            if 'prompt' in kwargs:
                kwargs['prompt'] = simplify_prompt(kwargs['prompt'])
            elif len(args) > 0:
                # Assume first arg is prompt
                args = (simplify_prompt(args[0]),) + args[1:]

        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            continue

    return None
