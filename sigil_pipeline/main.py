"""
Main pipeline orchestration module.

Coordinates the entire pipeline: crawl → analyze → filter → build → export.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.6.0
"""

import asyncio
import logging
import random
import time
from collections import Counter
from pathlib import Path
from typing import Any, Iterator

from . import (
    analyzer,
    config,
    crawler,
    dataset_builder,
    exporter,
    filter,
    github_miner,
    prompt_templates,
    utils,
)
from .analyzer import get_crate_source_paths
from .environment import (
    EnvironmentFingerprint,
    capture_environment,
    log_environment_summary,
    validate_hardening_toolchain_or_exit,
    write_environment_file,
)
from .observability import configure_structured_logging, get_metrics

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
    Process a single crate: fetch, analyze, and collect raw code files.

    NOTE:
      - Filtering and chunking are handled later in the streaming stage.
      - This function only returns raw file dicts + metadata.

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

        # Collect raw code files from actual source directories
        code_files: list[dict] = []
        source_dirs = get_crate_source_paths(crate_dir)
        seen_files: set[Path] = set()
        total_rs_files = 0

        # Build hardening metadata from analysis report (if hardening enabled)
        hardening_meta: dict[str, Any] = {}
        if config.dataset_hardening:
            hardening_meta["_hardening_enabled"] = True
            hardening_meta["_hardening_edition"] = report.edition or "unknown"
            if report.strict_clippy:
                hardening_meta["_clippy_strict_passed"] = report.strict_clippy.passed
            if report.rustfmt:
                hardening_meta["_rustfmt_passed"] = report.rustfmt.passed

        for src_dir in source_dirs:
            if not src_dir.exists():
                continue
            rs_files = list(src_dir.rglob("*.rs"))
            for rs_file in rs_files:
                if rs_file in seen_files:
                    continue
                seen_files.add(rs_file)
                total_rs_files += 1
                try:
                    content = rs_file.read_text(encoding="utf-8", errors="ignore")
                    file_dict: dict[str, Any] = {
                        "path": str(rs_file.relative_to(crate_dir)),
                        "code": content,
                        "crate_name": crate_name,
                        "crate_dir": str(crate_dir),  # used later for error injection
                    }
                    # Add hardening metadata if enabled
                    if hardening_meta:
                        file_dict.update(hardening_meta)
                    code_files.append(file_dict)
                except Exception as e:
                    logger.debug(f"Failed to read {rs_file}: {e}")

        if source_dirs:
            logger.debug(
                f"{crate_name}: Found {total_rs_files} .rs files in "
                f"{[str(d.relative_to(crate_dir)) for d in source_dirs]}"
            )
        else:
            logger.warning(f"{crate_name}: No source directories found in {crate_dir}")

        total_time = time.time() - crate_start_time
        logger.info(
            f"{crate_name}: collected {len(code_files)} raw code files "
            f"(total: {total_time:.2f}s, fetch: {fetch_time:.2f}s, analyze: {analyze_time:.2f}s)"
        )

        # No filtering or chunking here; that is handled in the streaming stage
        return code_files, None

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

    # Initialize multi-GPU inference if configured
    from . import task_generator_llm

    if cfg.multi_gpu_enabled is not None:
        # Explicit setting in config
        task_generator_llm.initialize_multi_gpu(
            model_path=cfg.multi_gpu_model_path,
            gpu_count=cfg.multi_gpu_count,
            force_enabled=cfg.multi_gpu_enabled,
        )
    else:
        # Prompt user at runtime
        task_generator_llm.initialize_multi_gpu(
            model_path=cfg.multi_gpu_model_path,
            gpu_count=cfg.multi_gpu_count,
            force_enabled=None,  # Will prompt
        )

    prompt_seed: int | None = None
    if cfg.enable_prompt_randomization:
        prompt_templates.set_prompt_randomization(True)
        prompt_seed = prompt_templates.initialize_prompt_rng(cfg.prompt_seed)
        logger.info(f"Prompt randomization enabled (seed={prompt_seed})")
    else:
        prompt_templates.set_prompt_randomization(False)
        if cfg.prompt_seed is not None:
            prompt_seed = prompt_templates.initialize_prompt_rng(cfg.prompt_seed)
        logger.info("Prompt randomization disabled")

    # Validate hardening toolchain if hardening mode is enabled
    if cfg.dataset_hardening:
        logger.info("Dataset hardening mode enabled - validating toolchain...")
        validate_hardening_toolchain_or_exit(
            cfg.hardening_min_edition, cfg.rustfmt_style_edition
        )
        logger.info(
            f"Hardening settings: strict_clippy={cfg.hardening_strict_clippy}, "
            f"deny_antipatterns={cfg.hardening_deny_antipatterns}, "
            f"require_rustfmt={cfg.hardening_require_rustfmt}, "
            f"reject_unsafe={cfg.hardening_reject_unsafe}"
        )

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
    if cfg.enable_rejection_log and not cfg.rejection_log_path:
        cfg.rejection_log_path = str(output_dir / "rejected_samples.jsonl")

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
            crates = checkpoint_manager.filter_unprocessed(crates)
        else:
            logger.info("No checkpoint found, starting fresh run")

    # Initialize metrics tracking
    processed_count = 0
    skipped_count = 0
    reason_counts: Counter[str] = Counter()
    rejection_tracker: dataset_builder.RejectionTracker | None = None

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
            # Setup shared cargo target directory if enabled
            cargo_env: dict[str, str] = {}
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

            tasks: list[asyncio.Task[Any]] = []
            task_to_crate: dict[int, str] = {}
            for crate in crates:
                task = asyncio.create_task(process_with_semaphore(crate))
                task_id = id(task)
                task_to_crate[task_id] = crate
                tasks.append(task)

            crate_file_generator_parts: list[list[dict]] = []
            accepted_crates_for_mining: list[github_miner.CrateInfo] = []

            for completed_task in asyncio.as_completed(tasks):
                crate_name = task_to_crate.get(id(completed_task), "unknown")
                try:
                    file_list, reason = await completed_task
                except Exception as e:
                    # Hard failure in the task itself
                    logger.error(f"Error processing {crate_name}: {e}", exc_info=True)
                    skipped_count += 1
                    reason_counts["processing_error"] += 1
                    metrics_collector.increment(
                        "crates_rejected_total",
                        labels={"reason": "processing_error"},
                        help_text="Total crates rejected by reason",
                    )
                    if checkpoint_manager:
                        checkpoint_manager.mark_processed(
                            crate_name, "rejected", "processing_error"
                        )
                        processed_crates[crate_name] = {
                            "status": "rejected",
                            "reason": "processing_error",
                            "file_count": 0,
                        }
                    continue

                if file_list is None:
                    # Crate was rejected by quality filters / fetch errors
                    skipped_count += 1
                    reason = reason or "unknown"

                    # Normalize reason for metrics
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
                            help_text="Number of files per accepted crate (pre-filter)",
                        )
                        crate_dir_value = file_list[0].get("crate_dir")
                        if crate_dir_value:
                            accepted_crates_for_mining.append(
                                github_miner.CrateInfo(
                                    name=crate_name, crate_dir=Path(crate_dir_value)
                                )
                            )

                    if checkpoint_manager:
                        checkpoint_manager.mark_processed(
                            crate_name, "accepted", None, file_list
                        )
                        processed_crates[crate_name] = {
                            "status": "accepted",
                            "reason": None,
                            "file_count": len(file_list),
                        }

                # Save checkpoint periodically
                if (
                    checkpoint_manager
                    and (processed_count + skipped_count) % cfg.checkpoint_interval == 0
                ):
                    config_hash = utils.compute_config_hash(cfg)
                    checkpoint_manager.save(processed_crates, temp_dir, config_hash)
                    logger.debug(
                        f"Checkpoint saved ({processed_count + skipped_count} crates processed)"
                    )

            logger.info(
                f"Processed {processed_count} crates, skipped {skipped_count}, "
                f"collected {sum(len(files) for files in crate_file_generator_parts)} raw code files"
            )

            # Unified generator: raw code files from crates + optional Stack
            def iter_all_code_files() -> Iterator[dict]:
                """Unified generator for raw code files (no filtering/chunking)."""
                # From accepted crates
                for file_list in crate_file_generator_parts:
                    for file_dict in file_list:
                        yield file_dict

            # Streaming stage: filter + chunking
            def iter_filtered_and_chunked_files() -> Iterator[dict]:
                """
                files -> filter.filter_code_files -> chunker -> file dicts

                Phase-2 instruct mode with semantic chunking.

                Prioritizes function chunks to enable better task diversity (code_gen,
                FIM, error_fixing, transformations) since non-function chunks can only
                do explanations.
                """
                from . import chunker
                from .ast_patterns import extract_context_header

                base_iter = filter.filter_code_files(iter_all_code_files(), cfg)

                # Collect chunks into two categories for prioritization
                function_chunks: list[dict] = []
                other_chunks: list[dict] = []

                for file_dict in base_iter:
                    context_header = ""
                    try:
                        context_header = extract_context_header(file_dict["code"])
                        chunks = chunker.chunk_rust_file(
                            file_dict["code"],
                            max_lines=cfg.max_sft_lines,
                            max_chars=cfg.max_sft_chars,
                        )
                        for chunk in chunks:
                            chunk_dict: dict[str, Any] = {
                                "path": file_dict["path"],
                                "code": chunk["code"],
                                "chunk_type": chunk["type"],
                                "crate_name": file_dict.get("crate_name"),
                                "crate_dir": file_dict.get("crate_dir"),
                                "start_line": chunk.get("start_line"),
                                "end_line": chunk.get("end_line"),
                            }
                            if context_header:
                                chunk_dict["file_context"] = context_header
                            # Preserve hardening / analysis metadata
                            for key, value in file_dict.items():
                                if (
                                    key.startswith("_hardening")
                                    or key.startswith("_clippy")
                                    or key.startswith("_rustfmt")
                                ):
                                    chunk_dict[key] = value
                            # Categorize by chunk type
                            if chunk["type"] == "function":
                                function_chunks.append(chunk_dict)
                            else:
                                other_chunks.append(chunk_dict)
                    except Exception as e:
                        logger.debug(
                            f"Failed to chunk {file_dict.get('path', '<unknown>')}: {e}"
                        )
                        # Fallback: emit original file if chunking fails
                        if context_header:
                            file_dict["file_context"] = context_header
                        other_chunks.append(file_dict)

                # Shuffle within categories for variety
                random.shuffle(function_chunks)
                random.shuffle(other_chunks)

                # Yield function chunks first (enables code_gen, FIM, refactor, error_fix)
                yield from function_chunks
                yield from other_chunks

            # Build dataset entries with format validation (streaming)
            logger.info("Building dataset entries...")
            rejection_tracker = dataset_builder.RejectionTracker(
                dump_path=(
                    Path(cfg.rejection_log_path) if cfg.rejection_log_path else None
                )
            )

            samples = dataset_builder.iter_dataset_entries_async(
                iter_filtered_and_chunked_files(),
                validate_format=cfg.validate_format,
                validate_outputs=cfg.validate_outputs,
                validation_timeout=cfg.output_validation_timeout,
                cargo_env=cargo_env,
                require_rustfmt=cfg.dataset_hardening and cfg.hardening_require_rustfmt,
                allow_explanations=cfg.enable_explanations,
                sandbox_mode=cfg.sandbox_mode,
                task_type_mix=cfg.task_type_mix,
                enable_error_injection=cfg.enable_error_injection,
                error_injection_method=cfg.error_injection_method,
                allow_simulated_error_fixing=cfg.allow_simulated_error_fixing,
                error_injection_timeout=cfg.error_injection_timeout,
                max_sft_lines=cfg.max_sft_lines,
                max_sft_chars=cfg.max_sft_chars,
                prompt_seed=prompt_seed if cfg.enable_prompt_randomization else None,
                rejection_tracker=rejection_tracker,
            )

            if cfg.enable_github_mining and accepted_crates_for_mining:
                base_samples = samples

                async def iter_all_samples():
                    async for sample in base_samples:
                        yield sample
                    async for sample in github_miner.iter_bugfix_samples_async(
                        accepted_crates_for_mining,
                        allowed_labels=cfg.github_mining_labels,
                        max_prs_per_crate=cfg.github_mining_max_prs_per_crate,
                        max_samples_per_pr=cfg.github_mining_max_samples_per_pr,
                        timeout=cfg.github_mining_timeout,
                        require_tests=cfg.github_mining_require_tests,
                        max_lines=cfg.max_sft_lines,
                        max_chars=cfg.max_sft_chars,
                        cargo_env=cargo_env,
                        sandbox_mode=cfg.sandbox_mode,
                    ):
                        yield sample

                samples = iter_all_samples()

            seen_prompts: set[str] | None = None
            if cfg.deduplicate_prompts:
                seen_prompts = set()
            if cfg.strict_validation or cfg.deduplicate_prompts:
                samples = dataset_builder.enforce_sample_gates_async(
                    samples,
                    validate_format=cfg.validate_format,
                    max_lines=cfg.max_sft_lines,
                    max_chars=cfg.max_sft_chars,
                    strict_validation=cfg.strict_validation,
                    deduplicate_prompts=cfg.deduplicate_prompts,
                    seen_prompts=seen_prompts,
                    rejection_tracker=rejection_tracker,
                )

            # Export JSONL directly from generator (streaming write)
            remove_metadata = not cfg.create_train_val_split
            logger.info(f"Writing dataset to {cfg.output_path}...")
            sample_count = await exporter.write_jsonl_async(
                samples, cfg.output_path, remove_metadata=remove_metadata
            )

            # Optionally append extra Phase-2 shards (e.g., experimental upscales)
            extra_phase2_metrics: dict[str, Any] = {
                "enabled": bool(cfg.extra_phase2_shards)
            }
            if cfg.extra_phase2_shards:
                logger.info("Appending extra Phase-2 shards...")
                extra_validator = (
                    dataset_builder.FormatValidator() if cfg.validate_format else None
                )

                def _validate_extra(sample: dict[str, Any]) -> tuple[bool, list[str]]:
                    errors = dataset_builder.strict_sample_errors(
                        sample,
                        validator=extra_validator,
                        max_lines=cfg.max_sft_lines,
                        max_chars=cfg.max_sft_chars,
                    )
                    return (len(errors) == 0, errors)

                added_samples, per_file_counts = exporter.merge_phase2_shards(
                    primary_path=cfg.output_path,
                    extra_paths=cfg.extra_phase2_shards,
                    validate_sample=_validate_extra,
                    strict=cfg.strict_validation,
                    deduplicate_prompts=cfg.deduplicate_prompts,
                    seen_prompts=seen_prompts,
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
            metrics["prompt_seed"] = (
                prompt_seed if cfg.enable_prompt_randomization else None
            )
            metrics["enable_prompt_randomization"] = cfg.enable_prompt_randomization

            # Final dataset path is the output path
            final_dataset_path = cfg.output_path

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

            # Write metrics with granular filter breakdown
            metrics.update(
                {
                    "total_samples": sample_count,
                    "crates_processed": processed_count,
                    "crates_skipped": skipped_count,
                    "total_crates": len(crates),
                    "filter_breakdown": dict(reason_counts),
                    "config": cfg.to_dict(),
                }
            )

            rejection_summary = rejection_tracker.summary()
            if rejection_summary.get("counts"):
                metrics["sample_rejections"] = rejection_summary
                top_rejections = sorted(
                    rejection_summary["counts"].items(),
                    key=lambda item: item[1],
                    reverse=True,
                )
                logger.info(
                    "Sample rejection summary (top 10): "
                    + ", ".join(
                        f"{reason}={count}" for reason, count in top_rejections[:10]
                    )
                )

            # Track JSON parse failure rates for structured outputs (if used)
            parse_total = metrics_collector.get_counter("llm_json_parse_total")
            parse_success = metrics_collector.get_counter("llm_json_parse_success")
            parse_fail = metrics_collector.get_counter("llm_json_parse_failure")
            parse_fallback = metrics_collector.get_counter("llm_json_parse_fallback")
            parse_failure_rate = parse_fail / parse_total if parse_total > 0 else 0.0
            metrics["json_parse"] = {
                "total": int(parse_total),
                "success": int(parse_success),
                "failure": int(parse_fail),
                "fallback": int(parse_fallback),
                "failure_rate": parse_failure_rate,
            }
            json_parse_rate_exceeded = False
            if (
                cfg.max_json_parse_failure_rate is not None
                and parse_total > 0
                and parse_failure_rate > cfg.max_json_parse_failure_rate
            ):
                json_parse_rate_exceeded = True
                logger.error(
                    "JSON parse failure rate %.2f%% exceeds threshold %.2f%%",
                    parse_failure_rate * 100,
                    cfg.max_json_parse_failure_rate * 100,
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

            if json_parse_rate_exceeded:
                raise SystemExit(1)

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
        if rejection_tracker:
            rejection_tracker.close()
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
        "--rejection-log",
        dest="rejection_log_path",
        help="Path to write rejected LLM outputs (JSONL). Defaults to output_dir/rejected_samples.jsonl.",
    )
    parser.add_argument(
        "--no-rejection-log",
        dest="enable_rejection_log",
        action="store_false",
        default=None,
        help="Disable rejected LLM output logging",
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
        "--strict-validation",
        dest="strict_validation",
        action="store_true",
        default=None,
        help="Fail pipeline on any sample validation error or duplicate prompt",
    )
    parser.add_argument(
        "--no-strict-validation",
        dest="strict_validation",
        action="store_false",
        default=None,
        help="Disable strict sample validation",
    )
    parser.add_argument(
        "--dedup-prompts",
        dest="deduplicate_prompts",
        action="store_true",
        default=None,
        help="Deduplicate samples by prompt text before writing",
    )
    parser.add_argument(
        "--no-dedup-prompts",
        dest="deduplicate_prompts",
        action="store_false",
        default=None,
        help="Disable prompt-level deduplication",
    )
    parser.add_argument(
        "--validate-outputs",
        dest="validate_outputs",
        action="store_true",
        default=None,
        help="Enable compile-check validation of LLM outputs (default: False)",
    )
    parser.add_argument(
        "--no-validate-outputs",
        dest="validate_outputs",
        action="store_false",
        default=None,
        help="Disable compile-check validation of LLM outputs",
    )
    parser.add_argument(
        "--output-validation-timeout",
        type=int,
        default=None,
        help="Timeout in seconds for output validation cargo checks/tests (default: 160)",
    )
    parser.add_argument(
        "--no-explanations",
        dest="enable_explanations",
        action="store_false",
        default=None,
        help="Disable explanation task generation",
    )
    parser.add_argument(
        "--sandbox-mode",
        choices=["auto", "firejail", "none"],
        default=None,
        help="Sandbox mode for running untrusted code (auto, firejail, none)",
    )
    parser.add_argument(
        "--task-mix",
        type=str,
        help=(
            "Task type distribution as JSON, e.g. "
            '\'{"code_generation": 0.7, "transformations": 0.15, '
            '"error_fixing": 0.1, "explanations": 0.05}\''
        ),
    )
    parser.add_argument(
        "--create-train-val-split",
        action="store_true",
        default=None,
        help="Enable train/val split by source (keeps whole crates/files together)",
    )
    parser.add_argument(
        "--no-create-train-val-split",
        dest="create_train_val_split",
        action="store_false",
        default=None,
        help="Disable train/val split creation (enabled by default)",
    )
    parser.add_argument(
        "--val-ratio",
        type=float,
        default=0.1,
        help="Ratio of sources for validation set (default: 0.1 = 10%%)",
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
    parser.add_argument(
        "--allow-simulated-error-fixing",
        dest="allow_simulated_error_fixing",
        action="store_true",
        default=None,
        help="Allow regex-based simulated error injection for error-fixing tasks",
    )
    parser.add_argument(
        "--no-allow-simulated-error-fixing",
        dest="allow_simulated_error_fixing",
        action="store_false",
        default=None,
        help="Disallow simulated error injection for error-fixing tasks (default)",
    )
    parser.add_argument(
        "--enable-github-mining",
        dest="enable_github_mining",
        action="store_true",
        default=None,
        help="Enable GitHub bug-fix mining for error-fixing samples",
    )
    parser.add_argument(
        "--no-github-mining",
        dest="enable_github_mining",
        action="store_false",
        default=None,
        help="Disable GitHub bug-fix mining",
    )
    parser.add_argument(
        "--github-mining-label",
        dest="github_mining_labels",
        action="append",
        help="Label to use when mining bug-fix PRs (can repeat)",
    )
    parser.add_argument(
        "--github-mining-max-prs",
        type=int,
        default=None,
        help="Maximum PRs to scan per crate when mining (default: 5)",
    )
    parser.add_argument(
        "--github-mining-max-samples",
        type=int,
        default=None,
        help="Maximum samples to emit per PR when mining (default: 5)",
    )
    parser.add_argument(
        "--github-mining-timeout",
        type=int,
        default=None,
        help="Timeout in seconds for mining validations (default: 160)",
    )
    parser.add_argument(
        "--no-github-mining-require-tests",
        dest="github_mining_require_tests",
        action="store_false",
        default=None,
        help="Allow mined samples without requiring cargo test when tests exist",
    )

    # Dataset Hardening Mode (Rust 2024 Benchmark Quality)
    parser.add_argument(
        "--dataset-hardening",
        action="store_true",
        help="Enable strict Rust 2024 dataset hardening mode. Applies additional quality "
        "gates: strict Clippy (pedantic/nursery), rustfmt validation, unsafe block "
        "rejection. Requires rustc 1.85+ for full edition 2024 support. "
        "See docs/runbooks/RUST_2024_TOOLCHAIN_SETUP.md for setup instructions.",
    )
    parser.add_argument(
        "--no-hardening-strict-clippy",
        dest="hardening_strict_clippy",
        action="store_false",
        help="Disable strict Clippy (pedantic/nursery) in hardening mode for faster runs",
    )
    parser.add_argument(
        "--no-hardening-rustfmt",
        dest="hardening_require_rustfmt",
        action="store_false",
        help="Disable rustfmt validation in hardening mode",
    )
    parser.add_argument(
        "--no-hardening-reject-unsafe",
        dest="hardening_reject_unsafe",
        action="store_false",
        help="Allow unsafe blocks in hardening mode (not recommended)",
    )
    parser.add_argument(
        "--no-hardening-deny-antipatterns",
        dest="hardening_deny_antipatterns",
        action="store_false",
        help="Allow unwrap/expect/panic in hardening mode (not recommended)",
    )
    parser.add_argument(
        "--hardening-min-edition",
        default="2021",
        help="Minimum Rust edition for hardening mode (default: 2021, editions below 2021 not supported)",
    )
    parser.add_argument(
        "--hardening-style-edition",
        default=None,
        help="Rustfmt style_edition to enforce in hardening mode (defaults to hardening_min_edition)",
    )
    parser.add_argument(
        "--rustfmt-style-edition",
        default=None,
        help="Rustfmt style_edition to enforce (default: 2021)",
    )
    parser.add_argument(
        "--max-json-parse-failure-rate",
        type=float,
        default=None,
        help="Abort run if JSON parse failure rate exceeds this fraction (default: 0.05)",
    )

    # Multi-GPU configuration
    parser.add_argument(
        "--multi-gpu",
        action="store_true",
        dest="multi_gpu_enabled",
        default=None,
        help="Enable multi-GPU inference (skips runtime prompt)",
    )
    parser.add_argument(
        "--no-multi-gpu",
        action="store_false",
        dest="multi_gpu_enabled",
        help="Disable multi-GPU inference (skips runtime prompt)",
    )
    parser.add_argument(
        "--gpu-count",
        type=int,
        default=None,
        dest="multi_gpu_count",
        help="Number of GPUs to use for multi-GPU inference (default: auto-detect)",
    )
    parser.add_argument(
        "--multi-gpu-model",
        type=str,
        default=None,
        dest="multi_gpu_model_path",
        help="Path to GGUF model for multi-GPU inference",
    )

    args = parser.parse_args()

    # Load config from file if specified
    if args.config:
        cfg = config.PipelineConfig.from_file(args.config)
    else:
        cfg = config.PipelineConfig()

    # Override config with command-line arguments
    if args.crates:
        cfg.crates = args.crates
    if args.crate_list:
        cfg.crate_list_path = args.crate_list
    if args.output:
        cfg.output_path = args.output
    if args.enable_rejection_log is not None:
        cfg.enable_rejection_log = args.enable_rejection_log
    if args.rejection_log_path:
        cfg.rejection_log_path = args.rejection_log_path
        cfg.enable_rejection_log = True
    if args.max_threads:
        cfg.max_threads = args.max_threads
    if args.limit:
        cfg.limit = args.limit
    if args.log_level:
        cfg.log_level = args.log_level
    if args.checkpoint_path:
        cfg.checkpoint_path = args.checkpoint_path
    if hasattr(args, "enable_checkpointing"):
        cfg.enable_checkpointing = args.enable_checkpointing
    if args.checkpoint_interval:
        cfg.checkpoint_interval = args.checkpoint_interval
    if args.require_docs is not None:
        cfg.require_docs = args.require_docs
    if args.max_sft_lines:
        cfg.max_sft_lines = args.max_sft_lines
    if args.max_sft_chars:
        cfg.max_sft_chars = args.max_sft_chars
    if args.strict_validation is not None:
        cfg.strict_validation = args.strict_validation
    if args.deduplicate_prompts is not None:
        cfg.deduplicate_prompts = args.deduplicate_prompts
    if args.validate_outputs is not None:
        cfg.validate_outputs = args.validate_outputs
    if args.output_validation_timeout is not None:
        cfg.output_validation_timeout = args.output_validation_timeout
    if args.enable_explanations is not None:
        cfg.enable_explanations = args.enable_explanations
    if args.sandbox_mode is not None:
        cfg.sandbox_mode = args.sandbox_mode
    if args.task_mix:
        import json

        cfg.task_type_mix = json.loads(args.task_mix)
    if args.create_train_val_split is not None:
        cfg.create_train_val_split = args.create_train_val_split
    if args.val_ratio:
        cfg.val_ratio = args.val_ratio
    if args.extra_phase2_shards:
        cfg.extra_phase2_shards = args.extra_phase2_shards
    if args.error_injection_timeout:
        cfg.error_injection_timeout = args.error_injection_timeout
    if args.allow_simulated_error_fixing is not None:
        cfg.allow_simulated_error_fixing = args.allow_simulated_error_fixing
    if args.enable_github_mining is not None:
        cfg.enable_github_mining = args.enable_github_mining
    if args.github_mining_labels:
        cfg.github_mining_labels = args.github_mining_labels
    if args.github_mining_max_prs is not None:
        cfg.github_mining_max_prs_per_crate = args.github_mining_max_prs
    if args.github_mining_max_samples is not None:
        cfg.github_mining_max_samples_per_pr = args.github_mining_max_samples
    if args.github_mining_timeout is not None:
        cfg.github_mining_timeout = args.github_mining_timeout
    if args.github_mining_require_tests is not None:
        cfg.github_mining_require_tests = args.github_mining_require_tests
    if args.dataset_hardening:
        cfg.dataset_hardening = args.dataset_hardening
    if hasattr(args, "hardening_strict_clippy"):
        cfg.hardening_strict_clippy = args.hardening_strict_clippy
    if hasattr(args, "hardening_require_rustfmt"):
        cfg.hardening_require_rustfmt = args.hardening_require_rustfmt
    if hasattr(args, "hardening_reject_unsafe"):
        cfg.hardening_reject_unsafe = args.hardening_reject_unsafe
    if hasattr(args, "hardening_deny_antipatterns"):
        cfg.hardening_deny_antipatterns = args.hardening_deny_antipatterns
    if args.hardening_min_edition:
        cfg.hardening_min_edition = args.hardening_min_edition
    if args.hardening_style_edition:
        cfg.hardening_style_edition = args.hardening_style_edition
        if not args.rustfmt_style_edition:
            cfg.rustfmt_style_edition = args.hardening_style_edition
    if args.rustfmt_style_edition:
        cfg.rustfmt_style_edition = args.rustfmt_style_edition
    if args.max_json_parse_failure_rate is not None:
        cfg.max_json_parse_failure_rate = args.max_json_parse_failure_rate

    # Multi-GPU configuration
    if args.multi_gpu_enabled is not None:
        cfg.multi_gpu_enabled = args.multi_gpu_enabled
    if args.multi_gpu_count is not None:
        cfg.multi_gpu_count = args.multi_gpu_count
    if args.multi_gpu_model_path is not None:
        cfg.multi_gpu_model_path = args.multi_gpu_model_path

    if cfg.enable_rejection_log:
        if not cfg.rejection_log_path:
            cfg.rejection_log_path = str(
                Path(cfg.output_dir) / "rejected_samples.jsonl"
            )
    else:
        cfg.rejection_log_path = None

    # Run pipeline
    asyncio.run(run_pipeline(cfg))


if __name__ == "__main__":
    main()
