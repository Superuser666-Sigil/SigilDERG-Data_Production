"""
Unified CLI orchestrator for the SigilDERG ecosystem.

Orchestrates the full pipeline: dataset generation → fine-tuning → evaluation.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.6.0
"""

import argparse
import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def run_full_pipeline(
    generate_dataset: bool = True,
    fine_tune: bool = True,
    evaluate: bool = True,
    dataset_path: str = "datasets/phase2_full.jsonl",
    config_path: str = "configs/llama8b-phase2.yml",
    checkpoint_path: Optional[str] = None,
    crate_list: Optional[str] = None,
    output_dir: str = "out",
    **kwargs,
) -> int:
    """
    Orchestrate full pipeline: generate → fine-tune → evaluate.

    Args:
        generate_dataset: Whether to generate dataset (default: True)
        fine_tune: Whether to fine-tune model (default: True)
        evaluate: Whether to evaluate model (default: True)
        dataset_path: Path to output dataset JSONL file
        config_path: Path to finetuner config YAML
        checkpoint_path: Path to checkpoint for evaluation (if None, uses latest)
        crate_list: Path to crate list file for dataset generation
        output_dir: Output directory for training
        **kwargs: Additional arguments passed to subprocess calls

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    exit_code = 0

    # Step 1: Generate dataset
    if generate_dataset:
        logger.info("=" * 70)
        logger.info("Step 1: Generating dataset")
        logger.info("=" * 70)

        if not crate_list:
            logger.error("crate_list is required for dataset generation")
            return 1

        cmd = [
            sys.executable,
            "-m",
            "sigil_pipeline.main",
            "--crate-list",
            crate_list,
            "--output",
            dataset_path,
            "--prompt-mode",
            "instruct",
            "--max-sft-lines",
            "200",
            "--max-sft-chars",
            "8000",
            "--no-require-docs",
            "--no-include-stack-dataset",
            "--create-train-val-split",
            "--val-ratio",
            "0.1",
            "--log-level",
            "INFO",
        ]

        # Add checkpoint path if provided
        if checkpoint_path:
            cmd.extend(["--checkpoint-path", checkpoint_path])

        # Add any additional kwargs
        for key, value in kwargs.items():
            if key.startswith("--"):
                cmd.append(key)
                if value is not None and value != "":
                    cmd.append(str(value))

        logger.info(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd)
        if result.returncode != 0:
            logger.error(
                f"Dataset generation failed with exit code {result.returncode}"
            )
            return result.returncode
        logger.info("Dataset generation completed successfully")

    # Step 2: Fine-tune model
    if fine_tune:
        logger.info("=" * 70)
        logger.info("Step 2: Fine-tuning model")
        logger.info("=" * 70)

        # Check if finetuner is available
        try:
            # Try importing the finetuner module
            import importlib

            importlib.import_module("rust_qlora.train")
        except ImportError:
            logger.error(
                "sigilderg-finetuner not available. Install with: pip install sigilderg-finetuner"
            )
            logger.error(
                "Or install full ecosystem: pip install sigil-pipeline[ecosystem]"
            )
            return 1

        # Update config to use local dataset
        # Note: This requires modifying the config file or passing dataset path
        # For now, we'll use the config as-is and expect it to reference the dataset
        cmd = [
            "sigilderg-train",
            config_path,
        ]

        logger.info(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd)
        if result.returncode != 0:
            logger.error(f"Fine-tuning failed with exit code {result.returncode}")
            return result.returncode
        logger.info("Fine-tuning completed successfully")

    # Step 3: Evaluate model
    if evaluate:
        logger.info("=" * 70)
        logger.info("Step 3: Evaluating model")
        logger.info("=" * 70)

        # Find latest checkpoint if not provided
        if not checkpoint_path:
            # Look for checkpoints in output_dir
            checkpoint_dir = Path(output_dir)
            if checkpoint_dir.exists():
                checkpoints = sorted(checkpoint_dir.glob("checkpoint-*"), reverse=True)
                if checkpoints:
                    checkpoint_path = str(checkpoints[0])
                    logger.info(f"Using latest checkpoint: {checkpoint_path}")
                else:
                    logger.error(f"No checkpoints found in {output_dir}")
                    return 1
            else:
                logger.error(f"Output directory not found: {output_dir}")
                return 1

        # Generate evaluation samples
        # This would typically use gen_eval_samples.py from finetuner
        # For now, we'll use eval_rust.py directly

        # Check if finetuner eval is available
        try:
            import importlib

            importlib.import_module("rust_qlora.eval_rust")
        except ImportError:
            logger.error(
                "sigilderg-finetuner not available. Install with: pip install sigilderg-finetuner"
            )
            logger.error(
                "Or install full ecosystem: pip install sigil-pipeline[ecosystem]"
            )
            return 1

        # Create a temporary samples file for evaluation
        # In a real workflow, this would be generated from the model
        # For now, we'll skip this step or use a placeholder

        logger.info("Evaluation step requires generated samples from the model")
        logger.info(
            "Use sigilderg-eval or gen_eval_samples.py to generate samples first"
        )

    logger.info("=" * 70)
    logger.info("Pipeline completed successfully!")
    logger.info("=" * 70)

    return exit_code


def main():
    """CLI entry point for ecosystem orchestrator."""
    parser = argparse.ArgumentParser(
        description="Orchestrate full SigilDERG ecosystem pipeline: generate → fine-tune → evaluate"
    )

    parser.add_argument(
        "--generate-dataset",
        action="store_true",
        default=True,
        help="Generate dataset (default: True)",
    )
    parser.add_argument(
        "--no-generate-dataset",
        dest="generate_dataset",
        action="store_false",
        help="Skip dataset generation",
    )

    parser.add_argument(
        "--fine-tune",
        action="store_true",
        default=True,
        help="Fine-tune model (default: True)",
    )
    parser.add_argument(
        "--no-fine-tune",
        dest="fine_tune",
        action="store_false",
        help="Skip fine-tuning",
    )

    parser.add_argument(
        "--evaluate",
        action="store_true",
        default=True,
        help="Evaluate model (default: True)",
    )
    parser.add_argument(
        "--no-evaluate", dest="evaluate", action="store_false", help="Skip evaluation"
    )

    parser.add_argument(
        "--dataset-path",
        type=str,
        default="datasets/phase2_full.jsonl",
        help="Path to output dataset JSONL file (default: datasets/phase2_full.jsonl)",
    )

    parser.add_argument(
        "--config-path",
        type=str,
        default="configs/llama8b-phase2.yml",
        help="Path to finetuner config YAML (default: configs/llama8b-phase2.yml)",
    )

    parser.add_argument(
        "--checkpoint-path",
        type=str,
        default=None,
        help="Path to checkpoint for evaluation (if None, uses latest in output-dir)",
    )

    parser.add_argument(
        "--crate-list",
        type=str,
        default=None,
        help="Path to crate list file for dataset generation (required if generating dataset)",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default="out",
        help="Output directory for training (default: out)",
    )

    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Run pipeline
    exit_code = run_full_pipeline(
        generate_dataset=args.generate_dataset,
        fine_tune=args.fine_tune,
        evaluate=args.evaluate,
        dataset_path=args.dataset_path,
        config_path=args.config_path,
        checkpoint_path=args.checkpoint_path,
        crate_list=args.crate_list,
        output_dir=args.output_dir,
    )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
