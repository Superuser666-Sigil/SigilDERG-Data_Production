#!/usr/bin/env python3
"""
Utility script to split a dataset into train/val sets by source.

Keeps whole crates/files together to ensure validation tests true generalization.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.5.0
"""

import argparse
import logging
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Split dataset into train/val by source (keeps crates/files together)"
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Input JSONL dataset file",
    )
    parser.add_argument(
        "--train",
        type=Path,
        required=True,
        help="Output path for training set",
    )
    parser.add_argument(
        "--val",
        type=Path,
        required=True,
        help="Output path for validation set",
    )
    parser.add_argument(
        "--val-ratio",
        type=float,
        default=0.1,
        help="Ratio of sources for validation (default: 0.1 = 10 percent)",
    )
    parser.add_argument(
        "--source-key",
        type=str,
        default="_source_crate",
        help="Key to use for source grouping (default: _source_crate)",
    )

    args = parser.parse_args()

    try:
        from sigil_pipeline.dataset_splitter import split_by_source

        train_count, val_count = split_by_source(
            input_path=str(args.input),
            train_path=str(args.train),
            val_path=str(args.val),
            val_ratio=args.val_ratio,
            source_key=args.source_key,
        )

        logger.info(
            f"Split complete: {train_count} train samples, {val_count} val samples"
        )
        return 0

    except Exception as e:
        logger.error(f"Error splitting dataset: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
