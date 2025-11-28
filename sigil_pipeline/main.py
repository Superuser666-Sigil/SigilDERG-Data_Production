"""
Main pipeline orchestration module.

Coordinates the entire pipeline: crawl → analyze → filter → build → export.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.2.0
"""

import asyncio
import logging
import time
from collections import Counter
from pathlib import Path
from typing import Any, Iterator

from . import analyzer, config, crawler, dataset_builder, exporter, filter, utils
from .environment import (
    EnvironmentFingerprint,
    capture_environment,
    log_environment_summary,
    write_environment_file,
)
from .observability import (
    configure_structured_logging,
    get_metrics,
)

logger = logging.getLogger(__name__)


def load_crate_list(crate_list_path: str | None = None) -> list[str]:
    """
    Load crate list from file or use default.

    Args:
        crate_list_path: Path to crate list file (optional)

    Returns:
        List of crate names
    """
    if crate_list_path:
        path = Path(crate_list_path)
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                crates = [line.strip() for line in f if line.strip()]
            logger.info(f"Loaded {len(crates)} crates from {crate_list_path}")
            return crates
        else:
            logger.warning(f"Crate list file not found: {crate_list_path}")

    # Try default location
    default_path = Path("data/crate_list.txt")
    if default_path.exists():
        with open(default_path, "r", encoding="utf-8") as f:
            crates = [line.strip() for line in f if line.strip()]
        logger.info(f"Loaded {len(crates)} crates from default location")
        return crates

    logger.warning("No crate list found, returning empty list")
    return []


async def process_crate(
    crate_name: str,
    config: config.PipelineConfig,
    temp_dir: Path,
    cargo_env: dict | None = None,
) -> tuple[list[dict] | None, str | None]:
    """
    Process a single crate: fetch, analyze, filter, and collect code files.

    Args:
        crate_name: Name of the crate to process
        config: Pipeline configuration
        temp_dir: Temporary directory for crate extraction
        cargo_env: Environment variables for cargo commands (CARGO_TARGET_DIR, etc.)

    Returns:
        Tuple of (file_list: list[dict] | None, rejection_reason: str | None)
        If accepted, returns (file_list, None). If rejected, returns (None, reason).
    """
    crate_start_time = time.time()
    try:
        # Fetch crate
        fetch_start = time.time()
        logger.info(f"Fetching {crate_name}...")
        crate_dir = crawler.fetch_crate(
            crate_name,
            config=config,
            temp_dir=temp_dir,
        )
        fetch_time = time.time() - fetch_start
        logger.debug(f"{crate_name}: Fetch took {fetch_time:.2f}s")

        if not crate_dir:
            logger.warning(f"Failed to fetch {crate_name}")
            return None, "fetch_failed"

        # Analyze crate
        analyze_start = time.time()
        logger.info(f"Analyzing {crate_name}...")
        report = await analyzer.analyze_crate(crate_dir, config, env=cargo_env)
        analyze_time = time.time() - analyze_start
        logger.debug(f"{crate_name}: Analysis took {analyze_time:.2f}s")

        # Check if crate meets criteria (returns tuple: (accepted, reason))
        is_acceptable, rejection_reason = filter.is_crate_acceptable(report, config)
        if not is_acceptable:
            logger.info(
                f"Skipping {crate_name}: does not meet quality criteria ({rejection_reason})"
            )
            return None, rejection_reason

        # Collect code files
        code_files = []
        src_dir = crate_dir / "src"
        if src_dir.exists():
            rs_files = list(src_dir.rglob("*.rs"))
            logger.debug(f"{crate_name}: Found {len(rs_files)} .rs files in src/")
            for rs_file in rs_files:
                try:
                    content = rs_file.read_text(encoding="utf-8", errors="ignore")
                    code_files.append(
                        {
                            "path": str(rs_file.relative_to(crate_dir)),
                            "code": content,
                            "crate_name": crate_name,
                        }
                    )
                except Exception as e:
                    logger.debug(f"Failed to read {rs_file}: {e}")
        else:
            logger.warning(
                f"{crate_name}: src/ directory does not exist in {crate_dir}"
            )

        # Filter code files (now returns generator)
        filter_start = time.time()
        filtered_files = list(filter.filter_code_files(code_files, config))
        filter_time = time.time() - filter_start
        logger.debug(f"{crate_name}: Filtering took {filter_time:.2f}s")

        # Chunk files if in Phase-2 mode
        if config.prompt_mode == "instruct":
            from . import chunker

            chunked_files = []
            for file_dict in filtered_files:
                try:
                    chunks = chunker.chunk_rust_file(
                        file_dict["code"],
                        max_lines=config.max_sft_lines,
                        max_chars=config.max_sft_chars,
                    )
                    for chunk in chunks:
                        chunked_files.append(
                            {
                                "path": file_dict["path"],
                                "code": chunk["code"],
                                "chunk_type": chunk["type"],
                                "crate_name": file_dict["crate_name"],
                                "crate_dir": str(crate_dir),  # For error injection
                            }
                        )
                except Exception as e:
                    logger.debug(f"Failed to chunk {file_dict['path']}: {e}")
                    # Fallback: use original file if chunking fails
                    chunked_files.append(file_dict)

            filtered_files = chunked_files
            logger.debug(f"{crate_name}: Chunked into {len(chunked_files)} snippets")

        total_time = time.time() - crate_start_time
        logger.info(
            f"{crate_name}: {len(filtered_files)}/{len(code_files)} files passed filters "
            f"(total: {total_time:.2f}s, fetch: {fetch_time:.2f}s, analyze: {analyze_time:.2f}s, filter: {filter_time:.2f}s)"
        )

        return filtered_files, None

    except Exception as e:
        total_time = time.time() - crate_start_time
        logger.error(
            f"Error processing {crate_name} (took {total_time:.2f}s): {e}",
            exc_info=True,
        )
        return None, "processing_error"


async def run_pipeline(cfg: config.PipelineConfig) -> None:
    """
    Run the complete pipeline.

    Args:
        cfg: Pipeline configuration
    """
    # Set up logging - prefer structured logging if enabled
    if cfg.enable_structured_logging:
        log_file_path = Path(cfg.log_file) if cfg.log_file else None
        configure_structured_logging(
            log_level=cfg.log_level,
            json_output=cfg.json_logs,
            log_file=log_file_path,
        )
    else:
        utils.setup_logging(cfg.log_level)

    logger.info("Starting Sigil Pipeline")
    logger.info(f"Configuration: {cfg.to_dict()}")

    # Capture and log environment fingerprint for reproducibility
    env_fingerprint: EnvironmentFingerprint | None = None
    if cfg.capture_environment:
        env_fingerprint = capture_environment()
        log_environment_summary(env_fingerprint)

    # Initialize metrics collector
    metrics_collector = get_metrics()
    metrics_collector.reset()  # Start fresh for this run

    # Load crate list
    if cfg.crates:
        crates = cfg.crates
    else:
        crates = load_crate_list(cfg.crate_list_path)

    if not crates:
        logger.error("No crates to process")
        return

    # Apply limit
    if cfg.limit:
        crates = crates[: cfg.limit]
        logger.info(f"Limited to {len(crates)} crates")

    # Create output directory
    output_dir = Path(cfg.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize checkpoint manager
    checkpoint_manager: utils.CheckpointManager | None = None
    if cfg.enable_checkpointing:
        checkpoint_path = cfg.checkpoint_path or (output_dir / "checkpoint.json")
        checkpoint_manager = utils.CheckpointManager(checkpoint_path)

        # Try to load existing checkpoint
        if checkpoint_manager.load():
            logger.info("Checkpoint loaded, resuming from previous run")
            # Verify config compatibility
            current_config_hash = utils.compute_config_hash(cfg)
            if checkpoint_manager.config_hash != current_config_hash:
                logger.warning(
                    "Config hash mismatch! Checkpoint may be from different config. "
                    "Proceeding anyway, but results may be inconsistent."
                )
            # Filter out already-processed crates (both accepted and rejected)
            # Note: Resuming skips already-processed crates to avoid duplicates.
            # To include samples from previous run, manually merge the datasets.
            crates = checkpoint_manager.filter_unprocessed(crates)
        else:
            logger.info("No checkpoint found, starting fresh run")

    # Initialize metrics tracking (Priority 5.1)
    processed_count = 0
    skipped_count = 0
    reason_counts: Counter[str] = Counter()

    # Set up metrics collector gauges
    metrics_collector.gauge(
        "pipeline_crates_total",
        float(len(crates)),
        help_text="Total number of crates to process",
    )

    # Track processed crates for checkpointing
    processed_crates: dict[str, dict[str, Any]] = {}
    if checkpoint_manager:
        processed_crates = checkpoint_manager.processed_crates.copy()

    # Performance metrics
    start_time = time.time()

    temp_cleanup_prefixes = ["sigil_", "sigil_crate_", "sigil_crates_"]
    try:
        # Determine temp directory (resume from checkpoint or create new)
        resume_temp_dir = None
        if checkpoint_manager:
            resume_temp_dir = checkpoint_manager.get_temp_dir_path()

        # Use temporary directory for crate extraction
        cleanup_temp = resume_temp_dir is None  # Don't cleanup if resuming
        with utils.TempDir(
            prefix="sigil_crates_", cleanup=cleanup_temp, resume_path=resume_temp_dir
        ) as temp_dir:
            # Setup shared cargo target directory if enabled (Priority 3.1)
            cargo_env = {}
            if cfg.reuse_cargo_target:
                if cfg.cargo_target_dir:
                    target_dir = Path(cfg.cargo_target_dir)
                else:
                    # Keep shared target alongside outputs so it stays warm across runs
                    target_dir = Path(cfg.output_dir) / "cargo_target_cache"
                target_dir.mkdir(parents=True, exist_ok=True)
                cargo_env["CARGO_TARGET_DIR"] = str(target_dir.resolve())
                logger.info(f"Using shared cargo target directory: {target_dir}")
            # Process crates with concurrency control
            semaphore = asyncio.Semaphore(cfg.max_threads)

            async def process_with_semaphore(crate_name: str):
                async with semaphore:
                    return await process_crate(crate_name, cfg, temp_dir, cargo_env)

            # Create tasks with crate name mapping
            task_to_crate = {}
            tasks = []
            for crate in crates:
                task = asyncio.create_task(process_with_semaphore(crate))
                task_to_crate[task] = crate
                tasks.append(task)

            # Process crates and collect results with reason tracking (Priority 2.1 - Streaming Architecture)
            # Use asyncio.as_completed to process as crates complete
            crate_file_generator_parts = []
            # as_completed yields futures/tasks as they complete, we need to track which is which
            pending = {task: crate for task, crate in zip(tasks, crates)}
            for completed_task in asyncio.as_completed(tasks):
                try:
                    result = await completed_task
                    # Find crate name from pending dict
                    crate_name = pending.pop(completed_task, "unknown")
                    if isinstance(result, Exception):
                        logger.error(f"Task failed with exception: {result}")
                        skipped_count += 1
                        reason_counts["processing_error"] += 1
                        metrics_collector.increment(
                            "crates_rejected_total",
                            labels={"reason": "processing_error"},
                            help_text="Total crates rejected by reason",
                        )
                        # Mark as processed (rejected due to error)
                        if checkpoint_manager:
                            checkpoint_manager.mark_processed(
                                crate_name, "rejected", "processing_error"
                            )
                            processed_crates[crate_name] = {
                                "status": "rejected",
                                "reason": "processing_error",
                                "file_count": 0,
                            }
                    elif result[0] is None:
                        # Crate was filtered out
                        skipped_count += 1
                        reason = result[1] or "unknown"
                        # Normalize reason for metrics (Priority 5.1)
                        if "edition" in reason:
                            reason_counts["edition"] += 1
                            normalized_reason = "edition"
                        elif "clippy" in reason:
                            reason_counts["clippy"] += 1
                            normalized_reason = "clippy"
                        elif (
                            "documentation" in reason
                            or "docs" in reason
                            or "no documentation" in reason
                        ):
                            reason_counts["docs"] += 1
                            normalized_reason = "docs"
                        elif "license" in reason:
                            reason_counts["license"] += 1
                            normalized_reason = "license"
                        elif "unsafe" in reason:
                            reason_counts["unsafe"] += 1
                            normalized_reason = "unsafe"
                        elif "outdated" in reason:
                            reason_counts["outdated"] += 1
                            normalized_reason = "outdated"
                        elif "deny" in reason or "advisory" in reason:
                            reason_counts["deny"] += 1
                            normalized_reason = "deny"
                        elif "platform" in reason:
                            reason_counts["platform"] += 1
                            normalized_reason = "platform"
                        elif "fetch_failed" in reason:
                            reason_counts["fetch_failed"] += 1
                            normalized_reason = "fetch_failed"
                        else:
                            reason_counts["other"] += 1
                            normalized_reason = "other"

                        metrics_collector.increment(
                            "crates_rejected_total",
                            labels={"reason": normalized_reason},
                            help_text="Total crates rejected by reason",
                        )
                        # Mark as processed (rejected)
                        if checkpoint_manager:
                            checkpoint_manager.mark_processed(
                                crate_name, "rejected", reason
                            )
                            processed_crates[crate_name] = {
                                "status": "rejected",
                                "reason": reason,
                                "file_count": 0,
                            }
                    else:
                        # Crate accepted
                        file_list, _ = result
                        processed_count += 1
                        crate_file_generator_parts.append(file_list)
                        metrics_collector.increment(
                            "crates_accepted_total",
                            help_text="Total crates accepted",
                        )
                        if file_list:
                            metrics_collector.histogram(
                                "crate_file_count",
                                float(len(file_list)),
                                help_text="Number of files per accepted crate",
                            )
                        # Mark as processed (accepted)
                        if checkpoint_manager:
                            checkpoint_manager.mark_processed(
                                crate_name, "accepted", None, file_list
                            )
                            processed_crates[crate_name] = {
                                "status": "accepted",
                                "reason": None,
                                "file_count": len(file_list) if file_list else 0,
                            }

                    # Save checkpoint periodically
                    if (
                        checkpoint_manager
                        and (processed_count + skipped_count) % cfg.checkpoint_interval
                        == 0
                    ):
                        config_hash = utils.compute_config_hash(cfg)
                        checkpoint_manager.save(processed_crates, temp_dir, config_hash)
                        logger.debug(
                            f"Checkpoint saved ({processed_count + skipped_count} crates processed)"
                        )

                except Exception as e:
                    logger.error(f"Error processing {crate_name}: {e}", exc_info=True)
                    skipped_count += 1
                    reason_counts["processing_error"] += 1
                    # Mark as processed (rejected due to error)
                    if checkpoint_manager:
                        checkpoint_manager.mark_processed(
                            crate_name, "rejected", "processing_error"
                        )
                        processed_crates[crate_name] = {
                            "status": "rejected",
                            "reason": "processing_error",
                            "file_count": 0,
                        }

            logger.info(
                f"Processed {processed_count} crates, skipped {skipped_count}, "
                f"collected {sum(len(files) for files in crate_file_generator_parts)} code files"
            )

            # Create unified generator for all files (Priority 2.1 - Streaming Architecture)
            def iter_all_code_files() -> Iterator[dict]:
                """Unified generator for all code files (crates + Stack)."""
                # Yield from processed crates
                for file_list in crate_file_generator_parts:
                    for file_dict in file_list:
                        yield file_dict

                # Yield from Stack dataset if enabled (streaming, not materialized)
                if cfg.include_stack_dataset:
                    logger.info("Processing Stack dataset files...")
                    stack_count = 0
                    stack_filtered = 0
                    for file_dict in crawler.iter_stack_files(
                        cfg.stack_dataset_path,
                        use_streaming=cfg.stack_dataset_use_streaming,
                        hf_dataset_name=cfg.stack_dataset_hf_name,
                    ):
                        stack_count += 1
                        # Filter using generator-based filter
                        filtered_iter = filter.filter_code_files([file_dict], cfg)
                        filtered_list = list(filtered_iter)
                        if filtered_list:
                            yield filtered_list[0]
                        else:
                            stack_filtered += 1
                    logger.info(
                        f"Stack dataset: {stack_count - stack_filtered}/{stack_count} files passed filters"
                    )

            # Build dataset entries with format validation (streaming)
            logger.info("Building dataset entries...")
            phase1_spec_path = getattr(cfg, "phase1_spec_path", None)
            if phase1_spec_path:
                phase1_spec_path = Path(phase1_spec_path)
            else:
                # Try default location
                default_spec = Path("docs/phase1_format_spec.json")
                phase1_spec_path = default_spec if default_spec.exists() else None

            # Chain generators: files -> filtered -> dataset entries -> JSONL (Priority 2.1)
            filtered_files = filter.filter_code_files(iter_all_code_files(), cfg)
            samples = dataset_builder.build_dataset_entries(
                filtered_files,
                validate_format=cfg.validate_format,
                phase1_spec_path=phase1_spec_path,
                prompt_mode=cfg.prompt_mode,
                task_type_mix=(
                    cfg.task_type_mix if cfg.prompt_mode == "instruct" else None
                ),
                enable_error_injection=(
                    cfg.enable_error_injection
                    if cfg.prompt_mode == "instruct"
                    else False
                ),
                error_injection_method=(
                    cfg.error_injection_method
                    if cfg.prompt_mode == "instruct"
                    else "simulate"
                ),
                error_injection_timeout=cfg.error_injection_timeout,
                max_sft_lines=(
                    cfg.max_sft_lines if cfg.prompt_mode == "instruct" else None
                ),
                max_sft_chars=(
                    cfg.max_sft_chars if cfg.prompt_mode == "instruct" else None
                ),
            )

            # Export JSONL directly from generator (streaming write)
            # If train/val split is enabled, keep metadata for splitting
            remove_metadata = not cfg.create_train_val_split
            logger.info(f"Writing dataset to {cfg.output_path}...")
            sample_count = exporter.write_jsonl(
                samples, cfg.output_path, remove_metadata=remove_metadata
            )

            # Optionally append extra Phase-2 shards (e.g., experimental upscales)
            extra_phase2_metrics: dict[str, Any] = {
                "enabled": bool(cfg.extra_phase2_shards)
            }
            if cfg.extra_phase2_shards:
                logger.info("Appending extra Phase-2 shards...")
                added_samples, per_file_counts = exporter.merge_phase2_shards(
                    primary_path=cfg.output_path,
                    extra_paths=cfg.extra_phase2_shards,
                )
                sample_count += added_samples
                extra_phase2_metrics.update(
                    {
                        "added_samples": added_samples,
                        "per_file_counts": per_file_counts,
                        "shards": cfg.extra_phase2_shards,
                    }
                )
            else:
                extra_phase2_metrics["added_samples"] = 0
                extra_phase2_metrics["per_file_counts"] = {}

            # Initialize metrics
            metrics: dict[str, Any] = {"extra_phase2_shards": extra_phase2_metrics}

            # Optionally merge with Phase 1 data if specified
            final_dataset_path = cfg.output_path
            if cfg.merge_with_phase1 and cfg.phase1_dataset_path:
                logger.info(f"Merging with Phase 1 dataset: {cfg.phase1_dataset_path}")
                merged_path = str(
                    Path(cfg.output_path).parent / "merged_phase1_phase2.jsonl"
                )
                merged_count = exporter.merge_phase1_phase2(
                    phase1_path=cfg.phase1_dataset_path,
                    phase2_path=cfg.output_path,
                    output_path=merged_path,
                    shuffle=cfg.shuffle_merged,
                    phase2_weight=cfg.phase2_weight,
                    phase1_phase2_ratio=cfg.phase1_phase2_ratio,
                    auto_upsample_phase2=cfg.auto_upsample_phase2,
                )
                logger.info(f"Merged {merged_count} total samples to {merged_path}")
                final_dataset_path = merged_path
                metrics["merged_with_phase1"] = {
                    "enabled": True,
                    "phase1_path": cfg.phase1_dataset_path,
                    "phase2_samples": sample_count,
                    "total_samples": merged_count,
                    "merged_path": merged_path,
                    "shuffled": cfg.shuffle_merged,
                    "phase2_weight": cfg.phase2_weight,
                    "phase1_phase2_ratio": cfg.phase1_phase2_ratio,
                    "auto_upsample_phase2": cfg.auto_upsample_phase2,
                }
            else:
                metrics["merged_with_phase1"] = {"enabled": False}

            # Create train/val split if requested
            if cfg.create_train_val_split:
                from . import dataset_splitter

                logger.info("Creating train/val split by source...")
                output_dir = Path(cfg.output_dir)
                train_path = str(output_dir / "train.jsonl")
                val_path = str(output_dir / "val.jsonl")

                train_count, val_count = dataset_splitter.split_by_source(
                    input_path=final_dataset_path,
                    train_path=train_path,
                    val_path=val_path,
                    val_ratio=cfg.val_ratio,
                )

                logger.info(
                    f"Train/val split complete: {train_count} train, {val_count} val"
                )
                metrics["train_val_split"] = {
                    "enabled": True,
                    "train_samples": train_count,
                    "val_samples": val_count,
                    "val_ratio": cfg.val_ratio,
                    "train_path": train_path,
                    "val_path": val_path,
                }
            else:
                metrics["train_val_split"] = {"enabled": False}

            # Add performance metrics
            total_time = time.time() - start_time
            metrics["performance"] = {
                "total_time_seconds": total_time,
                "total_time_formatted": f"{total_time / 60:.1f} minutes",
                "crates_processed": processed_count,
                "crates_skipped": skipped_count,
                "avg_time_per_crate": total_time
                / max(processed_count + skipped_count, 1),
                "samples_generated": sample_count,
            }

            # Record final gauge values
            metrics_collector.gauge(
                "pipeline_samples_total",
                float(sample_count),
                help_text="Total samples generated",
            )
            metrics_collector.gauge(
                "pipeline_crates_accepted",
                float(processed_count),
                help_text="Total crates accepted",
            )
            metrics_collector.gauge(
                "pipeline_crates_skipped",
                float(skipped_count),
                help_text="Total crates skipped",
            )

            # Write metrics with granular filter breakdown (Priority 5.1)
            metrics.update(
                {
                    "total_samples": sample_count,
                    "crates_processed": processed_count,
                    "crates_skipped": skipped_count,
                    "total_crates": len(crates),
                    "filter_breakdown": dict(reason_counts),  # Granular filter reasons
                    "stack_dataset": {
                        "enabled": cfg.include_stack_dataset,
                    },
                    "config": cfg.to_dict(),
                }
            )

            # Include environment fingerprint if captured
            if env_fingerprint:
                metrics["environment"] = env_fingerprint.to_dict()
                # Also write standalone environment file
                env_path = output_dir / "environment.json"
                write_environment_file(env_fingerprint, env_path)
                logger.info(f"Environment fingerprint: {env_path}")

            metrics_path = output_dir / "metrics.json"
            exporter.write_metrics(metrics, str(metrics_path))

            # Export Prometheus format if enabled
            if cfg.enable_prometheus_output:
                prom_path = (
                    Path(cfg.prometheus_output_path)
                    if cfg.prometheus_output_path
                    else output_dir / "metrics.prom"
                )
                prom_path.parent.mkdir(parents=True, exist_ok=True)
                with open(prom_path, "w", encoding="utf-8") as f:
                    f.write(metrics_collector.export_prometheus())
                logger.info(f"Prometheus metrics: {prom_path}")

            logger.info("Pipeline completed successfully")
            logger.info(f"Output: {cfg.output_path}")
            logger.info(f"Metrics: {metrics_path}")

            # Save final checkpoint
            if checkpoint_manager:
                config_hash = utils.compute_config_hash(cfg)
                checkpoint_manager.save(processed_crates, temp_dir, config_hash)
                logger.info(
                    f"Final checkpoint saved: {len(processed_crates)} crates processed"
                )

    finally:
        cleaned = utils.cleanup_temp_artifacts(prefixes=temp_cleanup_prefixes)
        if cleaned:
            logger.info(
                f"Cleaned up {cleaned} leftover Sigil temp director{'ies' if cleaned != 1 else 'y'}"
            )
        else:
            logger.info("No leftover Sigil temp directories found to clean up")


def main():
    """Main entry point for the pipeline."""
    import argparse

    parser = argparse.ArgumentParser(description="Sigil Pipeline - Rust crate analysis")
    parser.add_argument("--crates", nargs="+", help="Crate names to process")
    parser.add_argument("--crate-list", help="Path to crate list file")
    parser.add_argument(
        "--output",
        default="output/sigil_phase2_dataset.jsonl",
        help="Output JSONL path",
    )
    parser.add_argument(
        "--max-threads", type=int, default=4, help="Max parallel threads"
    )
    parser.add_argument("--limit", type=int, help="Limit number of crates")
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    parser.add_argument("--config", help="Path to config JSON/YAML file")
    parser.add_argument(
        "--checkpoint-path",
        help="Path to checkpoint file for resuming (default: output_dir/checkpoint.json)",
    )
    parser.add_argument(
        "--no-checkpointing",
        dest="enable_checkpointing",
        action="store_false",
        help="Disable checkpointing",
    )
    parser.add_argument(
        "--checkpoint-interval",
        type=int,
        default=10,
        help="Save checkpoint every N crates processed (default: 10)",
    )
    parser.add_argument(
        "--stack-dataset-path",
        help="Path to local Stack dataset directory (default: datasets/the-stack-rust-clean)",
    )
    parser.add_argument(
        "--stack-dataset-streaming",
        action="store_true",
        help="Enable streaming from HuggingFace if local dataset not found",
    )
    parser.add_argument(
        "--stack-dataset-hf-name",
        help="HuggingFace dataset name for streaming (default: ammarnasr/the-stack-rust-clean)",
    )
    parser.add_argument(
        "--merge-with-phase1",
        action="store_true",
        help="Merge Phase 2 output with Phase 1 dataset",
    )
    parser.add_argument(
        "--phase1-dataset-path",
        help="Path to Phase 1 dataset JSONL file or HuggingFace dataset name",
    )
    parser.add_argument(
        "--phase1-spec-path",
        help="Path to Phase 1 format specification JSON file (for validation)",
    )
    parser.add_argument(
        "--include-stack-dataset",
        dest="include_stack_dataset",
        action="store_true",
        help="Include Stack dataset files (default: disabled)",
    )
    parser.add_argument(
        "--no-include-stack-dataset",
        dest="include_stack_dataset",
        action="store_false",
        help="Exclude Stack dataset files",
    )
    parser.set_defaults(include_stack_dataset=None)
    parser.add_argument(
        "--require-docs",
        action="store_true",
        default=None,
        help="Require documentation comments in code (default: True)",
    )
    parser.add_argument(
        "--no-require-docs",
        dest="require_docs",
        action="store_false",
        help="Do not require documentation comments in code",
    )
    parser.add_argument(
        "--prompt-mode",
        choices=["phase1_compat", "instruct"],
        default="phase1_compat",
        help="Prompt generation mode: 'phase1_compat' (backwards compatible) or 'instruct' (Phase-2)",
    )
    parser.add_argument(
        "--max-sft-lines",
        type=int,
        default=200,
        help="Maximum lines per snippet for Phase-2 dataset (default: 200)",
    )
    parser.add_argument(
        "--max-sft-chars",
        type=int,
        default=8000,
        help="Maximum characters per snippet for Phase-2 dataset (default: 8000)",
    )
    parser.add_argument(
        "--task-mix",
        type=str,
        help='Task type distribution as JSON (e.g., \'{"code_generation": 0.7, "transformations": 0.15, "error_fixing": 0.1, "explanations": 0.05}\')',
    )
    parser.add_argument(
        "--phase1-phase2-ratio",
        type=float,
        help="Target ratio of Phase-1:Phase-2 samples (e.g., 10.0 = 10:1 ratio). Overrides phase2_weight.",
    )
    parser.add_argument(
        "--no-auto-upsample-phase2",
        dest="auto_upsample_phase2",
        action="store_false",
        help="Disable automatic up-sampling of Phase-2 when small relative to Phase-1",
    )
    parser.add_argument(
        "--create-train-val-split",
        action="store_true",
        help="Create train/val split by source (keeps whole crates/files together)",
    )
    parser.add_argument(
        "--val-ratio",
        type=float,
        default=0.1,
        help="Ratio of sources for validation set (default: 0.1 = 10%)",
    )
    parser.add_argument(
        "--extra-phase2-shard",
        dest="extra_phase2_shards",
        action="append",
        help="Additional Phase-2 JSONL file to append after generation (can repeat)",
    )
    parser.add_argument(
        "--error-injection-timeout",
        type=int,
        default=None,
        help="Timeout in seconds for cargo-based error injection (default: 120)",
    )

    args = parser.parse_args()

    # Load config
    if args.config:
        cfg_path = Path(args.config)
        if cfg_path.suffix == ".yaml" or cfg_path.suffix == ".yml":
            cfg = config.PipelineConfig.from_yaml(cfg_path)
        else:
            cfg = config.PipelineConfig.from_json(cfg_path)
    else:
        cfg = config.PipelineConfig()

    # Override with command-line args
    if args.crates:
        cfg.crates = args.crates
    if args.crate_list:
        cfg.crate_list_path = args.crate_list
    if args.output:
        cfg.output_path = args.output
    if args.max_threads:
        cfg.max_threads = args.max_threads
    if args.limit:
        cfg.limit = args.limit
    if args.log_level:
        cfg.log_level = args.log_level
    if args.stack_dataset_path:
        cfg.stack_dataset_path = args.stack_dataset_path
    if args.stack_dataset_streaming:
        cfg.stack_dataset_use_streaming = True
    if args.stack_dataset_hf_name:
        cfg.stack_dataset_hf_name = args.stack_dataset_hf_name
    if args.merge_with_phase1:
        cfg.merge_with_phase1 = True
    if args.phase1_dataset_path:
        cfg.phase1_dataset_path = args.phase1_dataset_path
    if args.phase1_spec_path:
        cfg.phase1_spec_path = args.phase1_spec_path
    if getattr(args, "include_stack_dataset", None) is not None:
        cfg.include_stack_dataset = args.include_stack_dataset
    if hasattr(args, "require_docs") and args.require_docs is not None:
        cfg.require_docs = args.require_docs
    if hasattr(args, "prompt_mode"):
        cfg.prompt_mode = args.prompt_mode
    if hasattr(args, "max_sft_lines"):
        cfg.max_sft_lines = args.max_sft_lines
    if hasattr(args, "max_sft_chars"):
        cfg.max_sft_chars = args.max_sft_chars
    if hasattr(args, "task_mix") and args.task_mix:
        import json

        try:
            cfg.task_type_mix = json.loads(args.task_mix)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON for --task-mix: {e}")
            raise
    if getattr(args, "error_injection_timeout", None) is not None:
        cfg.error_injection_timeout = args.error_injection_timeout
    if hasattr(args, "phase1_phase2_ratio") and args.phase1_phase2_ratio:
        cfg.phase1_phase2_ratio = args.phase1_phase2_ratio
    if hasattr(args, "auto_upsample_phase2"):
        cfg.auto_upsample_phase2 = args.auto_upsample_phase2
    if hasattr(args, "create_train_val_split"):
        cfg.create_train_val_split = args.create_train_val_split
    if hasattr(args, "val_ratio"):
        cfg.val_ratio = args.val_ratio
    if hasattr(args, "extra_phase2_shards") and args.extra_phase2_shards:
        cfg.extra_phase2_shards = args.extra_phase2_shards
    if hasattr(args, "checkpoint_path") and args.checkpoint_path:
        cfg.checkpoint_path = args.checkpoint_path
    if hasattr(args, "enable_checkpointing"):
        cfg.enable_checkpointing = args.enable_checkpointing
    if hasattr(args, "checkpoint_interval"):
        cfg.checkpoint_interval = args.checkpoint_interval

    # Run pipeline
    asyncio.run(run_pipeline(cfg))


if __name__ == "__main__":
    main()
