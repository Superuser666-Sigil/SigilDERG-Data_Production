"""Unit tests for tools.analyze_failures utilities."""

from pathlib import Path

from tools.analyze_failures import (
    categorize_clippy_warning,
    parse_log_file_for_license_rejections,
)


def test_categorize_clippy_warning_safe():
    assert categorize_clippy_warning("clippy::doc_markdown") == "safe_to_ignore"


def test_categorize_clippy_warning_bad():
    assert categorize_clippy_warning("clippy::unwrap_used") == "bad_code"


def test_categorize_clippy_warning_questionable_unknown():
    assert categorize_clippy_warning("clippy::custom_rule") == "questionable"
    assert categorize_clippy_warning("") == "unknown"


def test_parse_log_file_for_license_rejections(tmp_path: Path):
    log_contents = "\n".join(
        [
            "2025-11-24 18:04:06 - sigil_pipeline.crawler - INFO - "
            "Skipping aho: license 'GPL-3.0' not in allowed list",
            "2025-11-24 18:05:10 - sigil_pipeline.crawler - INFO - "
            "Skipping foo-bar: no license declared",
            "INFO unrelated line",
        ]
    )
    log_file = tmp_path / "phase2.log"
    log_file.write_text(log_contents, encoding="utf-8")

    rejections = parse_log_file_for_license_rejections(log_file)

    assert rejections == [
        {
            "crate": "aho",
            "license": "GPL-3.0",
            "reason": "license 'GPL-3.0' not in allowed list",
        },
        {
            "crate": "foo-bar",
            "license": None,
            "reason": "no license declared in crates.io metadata",
        },
    ]
