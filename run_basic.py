#!/usr/bin/env python3
"""
Enterprise Rust Crate Pipeline - Basic Analysis (No LLM)

Fast metadata-only analysis with intelligent auto-resume capability.
Provides core crate analysis without LLM enrichment for speed and cost efficiency.

Enterprise Features:
- ✅ Auto-resume: Automatically skips already processed crates
- ✅ Progress tracking: Real-time progress monitoring  
- ✅ Fast execution: Metadata-only analysis for rapid processing
- ✅ Consistent output: Same format as LLM pipeline for interoperability
- ✅ Error recovery: Robust error handling and retries

Usage Examples:

# Resume basic analysis from existing state
python run_basic.py

# Process specific crates only
python run_basic.py --crates tokio serde async-std

# Custom output directory
python run_basic.py --output-dir basic_output

# Force restart from beginning
python run_basic.py --force-restart

# Skip problematic crates  
python run_basic.py --skip-problematic

# Verbose logging for debugging
python run_basic.py --verbose
"""

import asyncio
import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import List

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from rust_crate_pipeline.config import PipelineConfig
from rust_crate_pipeline.pipeline import CrateDataPipeline
from rust_crate_pipeline.utils.resume_utils import (
    get_remaining_crates,
    validate_resume_state,
    create_resume_report,
)
from rust_crate_pipeline.progress_monitor import ProgressMonitor
from utils.serialization_utils import to_serializable


def setup_logging(verbose: bool = False) -> None:
    """Setup enterprise-grade logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    
    # Configure formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Configure handlers
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(simple_formatter)
    console_handler.setLevel(level)
    
    file_handler = logging.FileHandler('pipeline_basic.log', encoding='utf-8')
    file_handler.setFormatter(detailed_formatter)
    file_handler.setLevel(logging.DEBUG)
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        handlers=[console_handler, file_handler]
    )


def parse_args() -> argparse.Namespace:
    """Parse command line arguments with enterprise defaults"""
    parser = argparse.ArgumentParser(
        description="Enterprise Rust Crate Pipeline - Basic Analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Core pipeline arguments
    parser.add_argument(
        '--crates',
        nargs='+',
        help='Specific crates to analyze (overrides crates-file)'
    )
    
    parser.add_argument(
        '--crates-file',
        default='rust_crate_pipeline/crate_list.txt',
        help='File containing crates to analyze (default: rust_crate_pipeline/crate_list.txt)'
    )
    
    parser.add_argument(
        '--output-dir',
        default='output',
        help='Output directory for results (default: output)'
    )
    
    parser.add_argument(
        '--batch-size',
        type=int,
        default=10,
        help='Crates to process in parallel (default: 10, higher than LLM due to no API limits)'
    )
    
    parser.add_argument(
        '--skip-problematic',
        action='store_true',
        help='Skip known problematic crates (kuchiki, syn, proc-macro2, etc.)'
    )
    
    parser.add_argument(
        '--force-restart',
        action='store_true',
        help='Force restart from beginning (ignore already processed crates)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    parser.add_argument(
        '--workers',
        type=int,
        default=4,
        help='Number of worker threads (default: 4)'
    )
    
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of crates to process (for testing)'
    )
    
    return parser.parse_args()


def report_progress(current: int, total: int, start_time: float) -> None:
    """Report processing progress with enterprise metrics"""
    elapsed = time.time() - start_time
    rate = current / elapsed if elapsed > 0 else 0
    remaining = total - current
    eta = remaining / rate if rate > 0 else 0
    
    progress_msg = f"Progress: {current}/{total} ({current/total*100:.1f}%) - "
    progress_msg += f"Rate: {rate:.2f} crates/sec - "
    progress_msg += f"ETA: {eta/60:.1f} min"
    
    logging.info(progress_msg)


async def main() -> None:
    """Main enterprise pipeline execution"""
    args = parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    logger.info("🚀 Starting Enterprise Rust Crate Pipeline - Basic Analysis")
    
    # Determine crates to process
    if args.crates:
        # Use specific crates provided via CLI
        crates_to_process = args.crates
        total_crates = len(crates_to_process)
        processed_count = 0
        logger.info(f"Processing {len(crates_to_process)} specific crates from CLI")
    else:
        # Auto-resume mode: load from file and check for already processed
        if args.force_restart:
            logger.info("🔄 Force restart mode: ignoring already processed crates")
            from rust_crate_pipeline.utils.resume_utils import load_crate_list
            crates_to_process = load_crate_list(args.crates_file)
            total_crates = len(crates_to_process)
            processed_count = 0
        else:
            logger.info("🔍 Auto-resume mode: checking for already processed crates")
            crates_to_process, total_crates, processed_count = get_remaining_crates(
                args.crates_file, 
                args.output_dir,
                args.skip_problematic
            )
    
    # Apply limit if specified
    if args.limit and args.limit < len(crates_to_process):
        logger.info(f"🎯 Limiting to first {args.limit} crates for testing")
        crates_to_process = crates_to_process[:args.limit]
    
    # Validate resume state
    if not validate_resume_state(crates_to_process, total_crates, processed_count, args.output_dir):
        logger.error("❌ Resume state validation failed")
        sys.exit(1)
    
    # Show resume report
    if not args.crates:  # Only show for auto-resume mode
        report = create_resume_report(crates_to_process, total_crates, processed_count, args.output_dir)
        print(report)
    
    # Check if already complete
    if not crates_to_process:
        logger.info("🎉 All crates already processed! Pipeline complete.")
        return
    
    # Create pipeline configuration
    config = PipelineConfig(
        batch_size=args.batch_size,
        n_workers=args.workers,
        checkpoint_interval=20,  # More frequent checkpoints
    )
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    # Initialize progress monitoring
    progress_monitor = ProgressMonitor(total_crates, str(output_dir))
    
    # Create and run the basic pipeline
    start_time = time.time()
    successful = 0
    failed = 0
    
    logger.info(f"🎯 Processing {len(crates_to_process)} crates with batch size {args.batch_size}")
    logger.info(f"💡 Mode: Fast metadata-only analysis (no LLM enrichment)")
    
    try:
        # Create the pipeline with our crate list
        pipeline = CrateDataPipeline(
            config,
            output_dir=str(output_dir),
            crate_list=crates_to_process,
            skip_ai=True,  # This is the key: skip AI/LLM processing
        )
        
        # Run the pipeline 
        result = await pipeline.run()
        
        if result:
            enriched_crates, dependency_analysis = result
            successful = len(enriched_crates)
            
            # The CrateDataPipeline saves its own output, but we need to ensure
            # it's in the same format as the LLM pipeline for consistency
            logger.info(f"✅ Pipeline completed successfully")
            logger.info(f"📊 Processed {successful} crates")
            logger.info(f"📁 Results saved to {output_dir}")
            
            # Convert pipeline output to individual crate files for consistency
            for enriched_crate in enriched_crates:
                try:
                    # Convert to serializable format
                    enriched_data = to_serializable(enriched_crate.to_dict())
                    
                    # Save individual crate file (same format as LLM pipeline)
                    crate_output_file = output_dir / f"{enriched_crate.name}_enriched.json"
                    with open(crate_output_file, "w", encoding="utf-8") as f:
                        json.dump(enriched_data, f, indent=2, default=str)
                    
                    progress_monitor.complete_crate(enriched_crate.name, True)
                    
                except Exception as e:
                    logger.warning(f"⚠️  Error saving {enriched_crate.name}: {e}")
                    progress_monitor.complete_crate(enriched_crate.name, False)
                    failed += 1
        else:
            logger.error("❌ Pipeline returned no results")
            failed = len(crates_to_process)
            
    except Exception as e:
        logger.error(f"❌ Pipeline execution failed: {e}")
        failed = len(crates_to_process)

    # Final report
    total_time = time.time() - start_time
    overall_successful = processed_count + successful
    
    logger.info("\n" + "="*60)
    logger.info("📊 PIPELINE COMPLETION REPORT")
    logger.info("="*60)
    logger.info(f"✅ Successful: {successful}")
    logger.info(f"❌ Failed: {failed}")
    logger.info(f"⏱️  Total time: {total_time/60:.1f} minutes")
    logger.info(f"⚡ Average rate: {successful/(total_time/60):.1f} crates/minute")
    logger.info(f"📈 Overall progress: {overall_successful}/{total_crates} ({overall_successful/total_crates*100:.1f}%)")
    
    if overall_successful == total_crates:
        logger.info("🎉 PIPELINE COMPLETED SUCCESSFULLY!")
    else:
        remaining = total_crates - overall_successful
        logger.info(f"🔄 {remaining} crates remaining - run again to continue")
    
    logger.info("\n💡 TIP: For AI-enriched analysis, use: python run_with_llm.py")


if __name__ == "__main__":
    asyncio.run(main()) 