# main.py
import argparse
import logging
import os
import shutil
import subprocess
import sys
import time
from typing import TYPE_CHECKING, Any

from .config import PipelineConfig
from .github_token_checker import check_and_setup_github_token
from .pipeline import CrateDataPipeline
from .production_config import setup_production_environment

# Optional Sigil import with fallback
_sigil_available = True
SigilCompliantPipeline = None

try:
    sys.path.append(".")  # Add current directory to path
    from sigil_enhanced_pipeline import SigilCompliantPipeline

    _sigil_available = True
except ImportError:
    _sigil_available = False
    if TYPE_CHECKING:
        from sigil_enhanced_pipeline import SigilCompliantPipeline
    else:
        SigilCompliantPipeline = None  # type: ignore[assignment,misc]


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Rust Crate Data Processing Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m rust_crate_pipeline                    # Run with defaults
  python -m rust_crate_pipeline --limit 50         # Process only 50 crates
  python -m rust_crate_pipeline --batch-size 5     # Smaller batches
  python -m rust_crate_pipeline --output-dir ./data # Custom output directory
  python -m rust_crate_pipeline --log-level DEBUG   # Verbose logging
  PRODUCTION=true python -m rust_crate_pipeline     # Production mode (quieter)
        """,
    )

    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=None,
        help="Limit the number of crates to process (default: process all)",
    )

    parser.add_argument(
        "--batch-size",
        "-b",
        type=int,
        default=10,
        help="Number of crates to process in each batch (default: 10)",
    )

    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=4,
        help="Number of parallel workers for API requests (default: 4)",
    )

    parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        default=None,
        help=(
            "Output directory for results (default: auto-generated timestamped "
            "directory)"),
    )

    parser.add_argument(
        "--model-path",
        "-m",
        type=str,
        default=None,
        help=(
            "Path to the LLM model file (default: ~/models/deepseek/deepseek-coder-"
            "6.7b-instruct.Q4_K_M.gguf)"),
    )

    parser.add_argument(
        "--max-tokens",
        type=int,
        default=256,
        help="Maximum tokens for LLM generation (default: 256)",
    )

    parser.add_argument(
        "--checkpoint-interval",
        type=int,
        default=10,
        help="Save checkpoint every N crates (default: 10)",
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )

    parser.add_argument(
        "--skip-ai",
        action="store_true",
        help="Skip AI enrichment (faster, metadata only)",
    )

    parser.add_argument(
        "--skip-source-analysis",
        action="store_true",
        help="Skip source code analysis",
    )

    # Enhanced scraping with Crawl4AI
    parser.add_argument(
        "--enable-crawl4ai",
        action="store_true",
        default=True,
        help="Enable enhanced web scraping with Crawl4AI (default: enabled)",
    )

    parser.add_argument(
        "--disable-crawl4ai",
        action="store_true",
        help="Disable Crawl4AI enhanced scraping (use basic scraping only)",
    )

    parser.add_argument(
        "--crawl4ai-model",
        type=str,
        default="~/models/deepseek/deepseek-coder-6.7b-instruct.Q4_K_M.gguf",
        help=(
            "GGUF model path for Crawl4AI content analysis (default: ~/models/deepseek/"
            "deepseek-coder-6.7b-instruct.Q4_K_M.gguf)"),
    )

    parser.add_argument(
        "--enable-sigil-protocol",
        action="store_true",
        help="Enable Sigil Protocol Sacred Chain processing (Rule Zero compliance)",
    )

    parser.add_argument(
        "--sigil-mode",
        choices=["enhanced", "direct-llm", "hybrid"],
        default="enhanced",
        help=(
            "Sigil processing mode: enhanced (API-based), direct-llm (local), "
            "hybrid (both)"
        ),
    )

    parser.add_argument(
        "--crate-list",
        type=str,
        nargs="+",
        help="Specific crates to process (space-separated list)",
    )

    parser.add_argument(
        "--config-file",
        type=str,
        help="JSON config file to override default settings",
    )

    return parser.parse_args()


def configure_logging(log_level: str = "INFO") -> None:
    """Configure logging with both console and file output"""
    level = getattr(logging, log_level.upper())

    # Clear any existing handlers to avoid conflicts
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Set root logger level
    root_logger.setLevel(level)

    # Create formatters
    detailed_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    simple_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s")

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(simple_formatter)
    root_logger.addHandler(console_handler)

    # File handler with unique timestamp
    log_filename = f"crate_enrichment_{time.strftime('%Y%m%d-%H%M%S')}.log"
    try:
        file_handler = logging.FileHandler(
            log_filename, mode="w", encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)  # Always capture DEBUG+ to file
        file_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(file_handler)

        # Log a test message to verify file handler works
        logging.info(f"Logging initialized - file: {log_filename}")

    except Exception as e:
        logging.error(f"Failed to create log file {log_filename}: {e}")
        print(f"Warning: Could not create log file: {e}")

    # Set library loggers to less verbose levels
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests_cache").setLevel(logging.WARNING)
    logging.getLogger("llama_cpp").setLevel(logging.WARNING)


def check_disk_space() -> None:
    """Check if there is at least 1GB of free disk space, log a warning if not."""
    if shutil.disk_usage(".").free < 1_000_000_000:  # 1GB
        logging.warning("Low disk space! This may affect performance.")


def enforce_rule_zero_reinforcement() -> None:
    """
    Enforce Rule Zero rigor by validating the canonical DB hash/signature
    before pipeline actions.

    Allows override for local dev, but enforces in CI/prod. Logs all events
    for traceability.
    """
    enforce: bool = (
        os.environ.get("ENFORCE_RULE_ZERO", "false").lower() == "true"
        or os.environ.get("CI", "false").lower() == "true"
        or os.environ.get("PRODUCTION", "false").lower() == "true"
    )
    if not enforce:
        logging.info(
            "Rule Zero DB hash/signature check skipped (dev mode or override)")
        return

    # Detect project root robustly (works in subdirs, CI, etc.)
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        project_root: str = result.stdout.strip()
    except Exception as e:
        logging.critical(
            f"Failed to detect project root for Rule Zero validation: {e}")
        sys.exit(1)

    db_path: str = os.path.join(project_root, "sigil_rag_cache.db")
    hash_path: str = os.path.join(project_root, "sigil_rag_cache.hash")

    # Validate DB hash/signature using the provided script with explicit
    # arguments
    try:
        logging.info("Validating Rule Zero DB hash/signature...")
        result = subprocess.run(
            [
                sys.executable,
                os.path.join(project_root, "audits", "validate_db_hash.py"),
                "--db",
                db_path,
                "--expected-hash",
                hash_path,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            logging.error(
                f"Rule Zero DB hash/signature validation failed: "
                f"{result.stdout}\n{result.stderr}"
            )
            # Allow manual override with justification
            override_justification = os.environ.get("RULE_ZERO_OVERRIDE", "")
            if override_justification:
                logging.warning(
                    "Manual override of Rule Zero DB hash/signature validation enabled."
                )
                logging.warning(
                    f"Override justification: {override_justification}")
            else:
                logging.critical(
                    "Rule Zero DB hash/signature validation failed and no override "
                    "provided. Exiting.")
                sys.exit(1)
        else:
            logging.info("Rule Zero DB hash/signature validation successful.")
    except Exception as e:
        logging.critical(
            f"Exception during Rule Zero DB hash/signature validation: {e}"
        )
        sys.exit(1)

    # Log environment metadata for traceability
    try:
        subprocess.run(
            [
                sys.executable,
                os.path.join(project_root, "scripts", "cache_env_metadata.py"),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception as e:
        logging.warning(f"Failed to cache environment metadata: {e}")


def main() -> None:
    # Enforce Rule Zero rigor before any pipeline action
    enforce_rule_zero_reinforcement()

    # Setup production environment first for optimal logging
    logging.debug(
        "Starting main() function - setting up production environment")
    prod_config: dict[str, Any] = setup_production_environment()
    logging.debug(
        f"Production environment setup complete: {
            bool(prod_config)}")

    logging.debug("Parsing command line arguments")
    args = parse_arguments()
    logging.debug(f"Arguments parsed: {vars(args)}")

    logging.debug(f"Configuring logging with level: {args.log_level}")
    configure_logging(args.log_level)
    logging.info("Logging configuration complete")

    logging.debug("Checking disk space")
    check_disk_space()
    logging.debug("Disk space check complete")

    # Check GitHub token before proceeding
    logging.debug("Checking GitHub token setup")
    if not check_and_setup_github_token():
        logging.error("GitHub token setup cancelled or failed. Exiting.")
        sys.exit(1)
    logging.info("GitHub token validation successful")

    try:
        # Create config from command line arguments
        logging.debug("Building configuration from arguments")
        config_kwargs: dict[str, Any] = {}

        # Apply production optimizations if available
        if prod_config:
            logging.debug(f"Applying production config: {prod_config}")
            config_kwargs.update(
                {
                    "max_retries": prod_config.get(
                        "max_retries", 3), "batch_size": prod_config.get(
                        "batch_size", 10), "checkpoint_interval": prod_config.get(
                        "checkpoint_interval", 10), })

        if args.batch_size:
            logging.debug(f"Setting batch_size to {args.batch_size}")
            config_kwargs["batch_size"] = args.batch_size
        if args.workers:
            logging.debug(f"Setting n_workers to {args.workers}")
            config_kwargs["n_workers"] = args.workers
        if args.model_path:
            logging.debug(f"Setting model_path to {args.model_path}")
            config_kwargs["model_path"] = args.model_path
        if args.max_tokens:
            logging.debug(f"Setting max_tokens to {args.max_tokens}")
            config_kwargs["max_tokens"] = args.max_tokens
        if args.checkpoint_interval:
            logging.debug(
                f"Setting checkpoint_interval to {
                    args.checkpoint_interval}")
            config_kwargs["checkpoint_interval"] = args.checkpoint_interval

        # Load config file if provided
        if args.config_file:
            logging.debug(f"Loading config file: {args.config_file}")
            import json

            with open(args.config_file) as f:
                file_config = json.load(f)
                logging.debug(f"Config file loaded: {file_config}")
                config_kwargs.update(file_config)  # type: ignore

        # Handle Crawl4AI configuration
        logging.debug("Configuring Crawl4AI settings")
        enable_crawl4ai = (
            args.enable_crawl4ai and not args.disable_crawl4ai
            if hasattr(args, "disable_crawl4ai")
            else True
        )
        logging.debug(f"Crawl4AI enabled: {enable_crawl4ai}")
        config_kwargs.update(
            {
                "enable_crawl4ai": enable_crawl4ai,
                "crawl4ai_model": getattr(
                    args,
                    "crawl4ai_model",
                    "~/models/deepseek/deepseek-coder-6.7b-instruct.Q4_K_M.gguf",
                ),
            }
        )

        logging.debug(f"Creating PipelineConfig with kwargs: {config_kwargs}")
        config = PipelineConfig(**config_kwargs)
        logging.info("Pipeline configuration created successfully")

        # Pass additional arguments to pipeline
        logging.debug("Building pipeline kwargs")
        pipeline_kwargs: dict[str, Any] = {}
        if args.output_dir:
            logging.debug(f"Setting output_dir to {args.output_dir}")
            pipeline_kwargs["output_dir"] = args.output_dir
        if args.limit:
            logging.debug(f"Setting limit to {args.limit}")
            pipeline_kwargs["limit"] = args.limit
        if args.crate_list:
            logging.debug(f"Setting crate_list to {args.crate_list}")
            pipeline_kwargs["crate_list"] = args.crate_list
        if args.skip_ai:
            logging.debug("Enabling skip_ai mode")
            pipeline_kwargs["skip_ai"] = True
        if args.skip_source_analysis:
            logging.debug("Enabling skip_source mode")
            pipeline_kwargs["skip_source"] = True

        logging.debug(f"Pipeline kwargs: {pipeline_kwargs}")

        # Sigil Protocol integration - handle pipeline creation properly
        if hasattr(
                args,
                "enable_sigil_protocol") and args.enable_sigil_protocol:
            logging.info("Sigil Protocol mode requested")
            logging.debug(
                f"Sigil available: {_sigil_available}, SigilCompliantPipeline: {
                    SigilCompliantPipeline is not None}")

            # Import Sigil enhanced pipeline
            if _sigil_available and SigilCompliantPipeline is not None:
                logging.info("Creating Sigil Protocol compliant pipeline")
                sigil_pipeline = SigilCompliantPipeline(
                    config, **pipeline_kwargs)
                logging.info(
                    "Starting Sigil Protocol compliant pipeline with "
                    "Sacred Chain processing"
                )

                # Run Sigil pipeline (synchronous)
                logging.debug(
                    "About to run Sigil pipeline - this is synchronous")
                result = sigil_pipeline.run()  # type: ignore[misc]
                logging.debug(f"Sigil pipeline run() returned: {result}")

                if result:
                    logging.info("Sigil pipeline completed successfully")
                else:
                    logging.warning("Sigil pipeline completed with no results")
            else:
                logging.warning("Sigil enhanced pipeline not available")
                logging.info("Falling back to standard pipeline")

                logging.debug("Creating standard pipeline as Sigil fallback")
                standard_pipeline = CrateDataPipeline(
                    config, **pipeline_kwargs)
                logging.debug(
                    "Standard pipeline created, about to run asynchronously")

                # Run standard pipeline (asynchronous)
                import asyncio

                logging.debug("Starting asyncio.run() for standard pipeline")
                result = asyncio.run(
                    standard_pipeline.run()
                )  # type: ignore[misc,assignment]
                logging.debug(
                    f"Standard pipeline asyncio.run() returned: {result}")

                if result:
                    logging.info("Standard pipeline completed successfully")
                else:
                    logging.warning(
                        "Standard pipeline completed with no results")
        else:
            logging.info("Standard pipeline mode")
            logging.debug("Creating standard pipeline")
            standard_pipeline = CrateDataPipeline(config, **pipeline_kwargs)
            logging.info(f"Starting pipeline with {len(vars(args))} arguments")
            logging.debug(
                "Standard pipeline created, about to run asynchronously")

            # Run standard pipeline (asynchronous)
            import asyncio

            logging.debug("Starting asyncio.run() for standard pipeline")
            result = asyncio.run(
                standard_pipeline.run()
            )  # type: ignore[misc,assignment]
            logging.debug(
                f"Standard pipeline asyncio.run() returned: {result}")

            if result:
                logging.info("Standard pipeline completed successfully")
            else:
                logging.warning("Standard pipeline completed with no results")

        logging.info("Main function execution completed successfully")

    except Exception as e:
        logging.critical(f"Pipeline failed: {str(e)}")
        logging.debug(
            f"Exception details: {
                type(e).__name__}: {
                str(e)}",
            exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
