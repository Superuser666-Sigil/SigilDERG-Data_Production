#!/usr/bin/env python3
"""
Split a large JSONL file into smaller chunks.

Each chunk is approximately 10-12MB in size, and no JSON object is split
across files (each line is a complete JSON object).

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.2.0
"""

import argparse
import logging
from pathlib import Path

# All types use modern Python 3.12 syntax

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Target chunk size: 10-12MB (use 11MB as target)
TARGET_CHUNK_SIZE = 11 * 1024 * 1024  # 11MB in bytes


def split_jsonl_file(
    input_path: Path,
    output_dir: Path,
    chunk_size: int = TARGET_CHUNK_SIZE,
    prefix: str = "phase1",
) -> None:
    """
    Split a JSONL file into smaller chunks.

    Args:
        input_path: Path to input JSONL file
        output_dir: Directory to write output chunks
        chunk_size: Target size for each chunk in bytes (default: 11MB)
        prefix: Prefix for output filenames (default: "phase1")
    """
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Splitting {input_path} into ~{chunk_size / (1024*1024):.1f}MB chunks")
    logger.info(f"Output directory: {output_dir}")

    chunk_num = 1
    current_size = 0
    current_file = None
    total_lines = 0
    total_size = 0

    try:
        with open(input_path, "r", encoding="utf-8") as infile:
            for line_num, line in enumerate(infile, 1):
                line_size = len(line.encode("utf-8"))
                total_size += line_size

                # Start a new chunk if current one would exceed target size
                if current_file is None or (
                    current_size + line_size > chunk_size and current_size > 0
                ):
                    if current_file is not None:
                        current_file.close()
                        logger.info(
                            f"Completed chunk {chunk_num - 1}: "
                            f"{current_size / (1024*1024):.2f}MB, "
                            f"{total_lines} total lines processed"
                        )

                    # Open new chunk file
                    output_path = output_dir / f"{prefix}_{chunk_num}.jsonl"
                    current_file = open(output_path, "w", encoding="utf-8")
                    current_size = 0
                    chunk_num += 1

                    if chunk_num == 2:  # Log first chunk start
                        logger.info("Starting chunk 1...")

                # Write line to current chunk
                current_file.write(line)
                current_size += line_size
                total_lines += 1

                # Progress logging every 100k lines
                if line_num % 100000 == 0:
                    logger.info(
                        f"Processed {line_num:,} lines "
                        f"({total_size / (1024*1024):.1f}MB total, "
                        f"{chunk_num - 1} chunks so far)"
                    )

        # Close the last chunk
        if current_file is not None:
            current_file.close()
            logger.info(
                f"Completed chunk {chunk_num - 1}: "
                f"{current_size / (1024*1024):.2f}MB"
            )

    except Exception:
        if current_file is not None:
            current_file.close()
        raise

    logger.info("=" * 70)
    logger.info("Split complete!")
    logger.info(f"Total lines: {total_lines:,}")
    logger.info(f"Total size: {total_size / (1024*1024):.2f}MB")
    logger.info(f"Number of chunks: {chunk_num - 1}")
    logger.info(
        f"Average chunk size: {(total_size / (chunk_num - 1)) / (1024*1024):.2f}MB"
    )
    logger.info(f"Output directory: {output_dir}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Split a large JSONL file into smaller chunks"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("datasets/phase1_full.jsonl"),
        help="Input JSONL file path (default: datasets/phase1_full.jsonl)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("datasets"),
        help="Output directory for chunks (default: datasets)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=TARGET_CHUNK_SIZE,
        help=f"Target chunk size in bytes (default: {TARGET_CHUNK_SIZE} = 11MB)",
    )
    parser.add_argument(
        "--prefix",
        type=str,
        default="phase1",
        help="Prefix for output filenames (default: phase1)",
    )

    args = parser.parse_args()

    try:
        split_jsonl_file(
            input_path=args.input,
            output_dir=args.output_dir,
            chunk_size=args.chunk_size,
            prefix=args.prefix,
        )
    except Exception as e:
        logger.error(f"Error splitting file: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
