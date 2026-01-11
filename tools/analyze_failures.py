#!/usr/bin/env python3
"""
Analyze pipeline failures: identify license rejections and analyze clippy warnings.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.6.0
"""

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

# Import the canonical categorize_clippy_warning function from analyzer
# This avoids code duplication and ensures consistent categorization
try:
    from sigil_pipeline.analyzer import categorize_clippy_warning
except ImportError:
    # Fallback for standalone usage without package installation
    def categorize_clippy_warning(code: str) -> str:
        """Fallback categorization when sigil_pipeline is not installed."""
        if not code or "clippy::" not in code:
            return "unknown"
        warning_name = code.split("::")[-1].lower()
        # Simplified fallback - prefer installing the package for accurate categorization
        bad_keywords = [
            "unwrap",
            "panic",
            "transmute",
            "unsafe",
            "unused",
            "todo",
            "unimplemented",
        ]
        for keyword in bad_keywords:
            if keyword in warning_name:
                return "bad_code"
        return "questionable"


def analyze_clippy_log(clippy_log_path: Path) -> dict[str, Any]:
    """Analyze clippy.log to extract warning types."""
    if not clippy_log_path.exists():
        return {}

    warning_types = defaultdict(int)
    categorized = defaultdict(int)

    try:
        with open(clippy_log_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    if msg.get("reason") == "compiler-message":
                        message = msg.get("message", {})
                        if message.get("level") == "warning":
                            code_obj = message.get("code", {})
                            if code_obj:
                                code_str = code_obj.get("code", "")
                                if code_str:
                                    warning_types[code_str] += 1
                                    category = categorize_clippy_warning(code_str)
                                    categorized[category] += 1
                except (json.JSONDecodeError, KeyError):
                    continue
    except Exception as e:
        print(f"Warning: Failed to analyze {clippy_log_path}: {e}")

    return {"warning_types": dict(warning_types), "categorized": dict(categorized)}


def parse_log_file_for_license_rejections(log_file_path: Path) -> list[dict[str, str]]:
    """Parse the main log file for license rejections during fetch phase."""
    license_rejections = []

    if not log_file_path.exists():
        return license_rejections

    # Pattern: "Skipping {crate}: license '{license}' not in allowed list"
    # Example: "2025-11-24 18:04:06 - sigil_pipeline.crawler - INFO - Skipping argh: license 'BSD-3-Clause' not in allowed list"
    pattern = re.compile(
        r"Skipping (\w+(?:-\w+)*): license '([^']+)' not in allowed list"
    )
    no_license_pattern = re.compile(r"Skipping (\w+(?:-\w+)*): no license declared")

    try:
        with open(log_file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                # Check for license rejection
                if "license" in line.lower() and "not in allowed" in line.lower():
                    match = pattern.search(line)
                    if match:
                        crate_name = match.group(1)
                        license_str = match.group(2)
                        license_rejections.append(
                            {
                                "crate": crate_name,
                                "license": license_str,
                                "reason": f"license '{license_str}' not in allowed list",
                            }
                        )
                # Check for no license declared
                elif "no license declared" in line.lower():
                    match = no_license_pattern.search(line)
                    if match:
                        crate_name = match.group(1)
                        license_rejections.append(
                            {
                                "crate": crate_name,
                                "license": None,
                                "reason": "no license declared in crates.io metadata",
                            }
                        )
    except Exception as e:
        print(f"Warning: Failed to parse log file {log_file_path}: {e}")

    return license_rejections


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Analyze pipeline failures: identify license rejections and analyze clippy warnings"
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        default=None,
        help="Path to analysis log directory (e.g., logs/analysis_20251124_180335). If not provided, will search for most recent analysis directory.",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default="logs/phase2_full_run.log",
        help="Path to main pipeline log file (default: logs/phase2_full_run.log)",
    )
    parser.add_argument(
        "--crate-list",
        type=str,
        default="data/crate_list.txt",
        help="Path to crate list file (default: data/crate_list.txt)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Optional: Write results to file (in addition to console output)",
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Don't automatically remove license rejections from crate_list.txt",
    )

    args = parser.parse_args()

    # Find log directory if not provided
    log_dir = None
    if args.log_dir:
        log_dir = Path(args.log_dir)
    else:
        # Find most recent analysis directory
        logs_base = Path("logs")
        if logs_base.exists():
            analysis_dirs = sorted(
                [
                    d
                    for d in logs_base.iterdir()
                    if d.is_dir() and d.name.startswith("analysis_")
                ],
                key=lambda x: x.stat().st_mtime,
                reverse=True,
            )
            if analysis_dirs:
                log_dir = analysis_dirs[0]
                print(f"Using most recent analysis directory: {log_dir}")

    log_file = Path(args.log_file)
    crate_list_path = Path(args.crate_list)

    if not log_dir or not log_dir.exists():
        print(f"Error: Log directory not found: {log_dir}")
        print("  Use --log-dir to specify the analysis log directory")
        return

    # Load all rejection summaries (analysis-phase rejections)
    print("Loading rejection summaries...")
    rejections = {}
    for crate_dir in log_dir.iterdir():
        if not crate_dir.is_dir():
            continue
        rejection_file = crate_dir / "rejection_summary.json"
        if rejection_file.exists():
            try:
                with open(rejection_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    rejections[data["crate"]] = data
            except Exception as e:
                print(f"Warning: Failed to read {rejection_file}: {e}")

    print(f"Found {len(rejections)} rejected crates from analysis phase\n")

    # Parse log file for license rejections (fetch-phase rejections)
    print("Parsing log file for license rejections...")
    license_rejections_from_log = parse_log_file_for_license_rejections(log_file)
    print(
        f"Found {len(license_rejections_from_log)} license rejections from fetch phase\n"
    )

    # Categorize by reason
    reason_counts = defaultdict(int)
    license_rejections = []
    clippy_rejections = []

    for crate_name, data in rejections.items():
        reason = data.get("reason", "unknown")
        reason_counts[reason] += 1

        if "license" in reason.lower():
            license_info = data.get("license", {})
            license_rejections.append(
                {
                    "crate": crate_name,
                    "license": license_info.get("crate_license")
                    or license_info.get("all_licenses"),
                    "reason": reason,
                }
            )
        elif "clippy" in reason.lower():
            clippy_rejections.append(
                {
                    "crate": crate_name,
                    "warnings": data.get("clippy_warning_count", 0),
                    "errors": data.get("clippy_error_count", 0),
                    "reason": reason,
                }
            )

    # Print summary
    print("=" * 70)
    print("REJECTION REASON SUMMARY")
    print("=" * 70)
    for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
        print(f"  {reason}: {count}")

    # Combine license rejections from both sources
    all_license_rejections = license_rejections + license_rejections_from_log
    # Deduplicate by crate name
    seen_crates = set()
    unique_license_rejections = []
    for item in all_license_rejections:
        if item["crate"] not in seen_crates:
            seen_crates.add(item["crate"])
            unique_license_rejections.append(item)

    # License rejections
    print(f"\n{'=' * 70}")
    print(f"LICENSE REJECTIONS: {len(unique_license_rejections)}")
    print("=" * 70)
    if unique_license_rejections:
        for item in unique_license_rejections:
            license_str = item.get("license") or "none declared"
            print(f"  {item['crate']}: {license_str}")

        # Remove from crate_list.txt (unless --no-cleanup flag)
        if not args.no_cleanup:
            print(
                f"\nRemoving {len(unique_license_rejections)} license rejections from crate_list.txt..."
            )
            if crate_list_path.exists():
                with open(crate_list_path, "r", encoding="utf-8") as f:
                    crates = [line.strip() for line in f if line.strip()]

                original_count = len(crates)
                license_crate_names = {
                    item["crate"] for item in unique_license_rejections
                }
                crates = [c for c in crates if c not in license_crate_names]
                removed = original_count - len(crates)

                with open(crate_list_path, "w", encoding="utf-8") as f:
                    for crate in crates:
                        f.write(f"{crate}\n")

                print(f"  Removed {removed} crates (kept {len(crates)})")
            else:
                print(f"  Error: crate_list.txt not found at {crate_list_path}")
        else:
            print("\nSkipping cleanup (--no-cleanup flag set)")
    else:
        print("  No license rejections found")

    # Clippy rejections analysis
    print(f"\n{'=' * 70}")
    print(f"CLIPPY REJECTIONS: {len(clippy_rejections)}")
    print("=" * 70)
    if clippy_rejections:
        sorted_clippy = sorted(
            clippy_rejections, key=lambda x: x["warnings"], reverse=True
        )
        print("Top 20 by warning count:")
        for item in sorted_clippy[:20]:
            print(
                f"  {item['crate']}: {item['warnings']} warnings, {item['errors']} errors"
            )

        # Analyze aho crate specifically
        print(f"\n{'=' * 70}")
        print("ANALYZING 'aho' CRATE CLIPPY WARNINGS")
        print("=" * 70)
        aho_clippy_log = log_dir / "aho" / "clippy.log"
        if aho_clippy_log.exists():
            analysis = analyze_clippy_log(aho_clippy_log)

            print(
                f"\nTotal warnings: {sum(analysis.get('warning_types', {}).values())}"
            )
            print("\nCategorized:")
            for category, count in analysis.get("categorized", {}).items():
                print(f"  {category.replace('_', ' ').title()}: {count}")

            print("\nWarning types (top 20):")
            warning_types = analysis.get("warning_types", {})
            for wtype, count in sorted(warning_types.items(), key=lambda x: -x[1])[:20]:
                category = categorize_clippy_warning(wtype)
                print(f"  {wtype}: {count} ({category})")
        else:
            print(f"  Clippy log not found: {aho_clippy_log}")

    # Recommendations
    print("\n" + "=" * 70)
    print("RECOMMENDATIONS")
    print("=" * 70)
    print("\n1. License rejections have been removed from crate_list.txt")
    print("\n2. For clippy warnings, consider allowing:")
    print("   - Documentation style warnings (doc_lazy_continuation, doc_markdown)")
    print("   - Complexity warnings (too_many_lines, cognitive_complexity)")
    print("   - Style warnings (naming, formatting, manual_* lints)")
    print("   - Dead code in trait definitions (often false positives)")
    print("\n3. Should still reject:")
    print("   - Unsafe code warnings (unwrap_used, expect_used, panic)")
    print("   - Memory safety warnings (transmute, invalid_*)")
    print("   - Actual dead code (unused_variables, unused_imports)")
    print("\n4. Suggested max_bad_code_warnings threshold: 0")
    print("   (Only rejects actual code quality problems, ignores style warnings)")

    # Write to file if requested
    if args.output:
        output_lines = [
            "=" * 70,
            "COMPREHENSIVE FAILURE ANALYSIS",
            "=" * 70,
            "",
            f"License Rejections: {len(unique_license_rejections)}",
            f"Clippy Rejections: {len(clippy_rejections)}",
            "",
            "License Rejections:",
        ]
        for item in unique_license_rejections:
            license_str = item.get("license") or "none declared"
            output_lines.append(f"  {item['crate']}: {license_str}")
        output_lines.append("")
        output_lines.append("Clippy Rejections:")
        for item in sorted_clippy:
            output_lines.append(
                f"  {item['crate']}: {item['warnings']} warnings, {item['errors']} errors"
            )

        output_file = Path(args.output)
        output_file.write_text("\n".join(output_lines), encoding="utf-8")
        print(f"\nResults also written to: {output_file}")


if __name__ == "__main__":
    main()
