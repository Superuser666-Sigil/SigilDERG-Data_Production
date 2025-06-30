#!/usr/bin/env python3
"""
Resume Pipeline Script - Process remaining crates after OOM crash

This script continues processing from where we left off, with optimizations:
- Only processes remaining unprocessed crates
- Smaller batch sizes to reduce memory pressure
- Skip problematic crates if needed
- Memory monitoring and limits
"""

import asyncio
import argparse
import logging
import sys
import time
import psutil
import os
from pathlib import Path
from typing import List, Optional

# Add the project root to the path
sys.path.append(str(Path(__file__).parent.parent))

from rust_crate_pipeline.unified_pipeline import (
    UnifiedSigilPipeline, 
    create_pipeline_from_args, 
    add_llm_arguments,
)
from rust_crate_pipeline.config import PipelineConfig
from rust_crate_pipeline.unified_llm_processor import create_llm_processor_from_args


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('pipeline_resume.log', encoding='utf-8')
        ]
    )


def load_remaining_crates() -> List[str]:
    """Load the list of remaining unprocessed crates"""
    try:
        with open('remaining_crates.txt', 'r', encoding='utf-8') as f:
            crates = [line.strip() for line in f if line.strip()]
        logging.info(f"Loaded {len(crates)} remaining crates to process")
        return crates
    except FileNotFoundError:
        logging.error("remaining_crates.txt not found. Run the main analysis first.")
        return []


def check_memory_usage() -> float:
    """Check current memory usage percentage"""
    return psutil.virtual_memory().percent


def should_skip_crate(crate_name: str) -> bool:
    """Check if a crate should be skipped due to known issues"""
    # Known problematic crates that cause OOM
    problematic_crates = {
        'kuchiki',  # Already processed but caused 1.54GB file
        'syn',      # Often large due to macro processing
        'proc-macro2',  # Macro heavy
        'html5ever',    # HTML parsing can be memory intensive
        'scraper',      # Web scraping, large dependency trees
    }
    
    return crate_name.lower() in problematic_crates


async def main() -> None:
    parser = argparse.ArgumentParser(description="Resume Rust Crate Pipeline Processing")
    add_llm_arguments(parser)
    
    parser.add_argument('--batch-size', type=int, default=4, 
                       help='Batch size for processing (default: 4 for memory safety)')
    parser.add_argument('--memory-limit', type=float, default=85.0,
                       help='Memory usage limit percentage (default: 85%%)')
    parser.add_argument('--skip-problematic', action='store_true',
                       help='Skip known problematic crates')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    setup_logging(args.verbose)
    
    # Load remaining crates
    remaining_crates = load_remaining_crates()
    if not remaining_crates:
        print("❌ No remaining crates to process!")
        return
    
    # Filter out problematic crates if requested
    if args.skip_problematic:
        original_count = len(remaining_crates)
        remaining_crates = [c for c in remaining_crates if not should_skip_crate(c)]
        skipped = original_count - len(remaining_crates)
        if skipped > 0:
            logging.info(f"⚠️  Skipped {skipped} known problematic crates")
    
    print(f"🚀 Resuming pipeline with {len(remaining_crates)} remaining crates")
    print(f"💾 Memory limit: {args.memory_limit}%")
    print(f"📦 Batch size: {args.batch_size}")
    
    # Set up Azure credentials FIRST (before creating PipelineConfig)
    os.environ['AZURE_OPENAI_ENDPOINT'] = 'https://david-mc08tirc-eastus2.services.ai.azure.com/'
    os.environ['AZURE_OPENAI_API_KEY'] = '2hw0jjqwjtKke7DMGiJSPtlj6GhuLCNdQWPXoDGN2I3JMvzp4PmGJQQJ99BFACHYHv6XJ3w3AAAAACOGFPYA'
    os.environ['AZURE_OPENAI_DEPLOYMENT_NAME'] = 'gpt-4o'
    os.environ['AZURE_OPENAI_API_VERSION'] = '2024-02-15-preview'
    
    # Create pipeline with optimized config
    config = PipelineConfig(
        batch_size=args.batch_size,
        n_workers=min(args.batch_size, 4),  # Limit concurrency
        checkpoint_interval=5,  # More frequent checkpoints
        use_azure_openai=True,
    )
    
    # Create LLM processor with Azure configuration
    llm_config = create_llm_processor_from_args(
        provider='azure',
        model='gpt-4o',
        api_base=os.environ['AZURE_OPENAI_ENDPOINT'],
        api_key=os.environ['AZURE_OPENAI_API_KEY'],
        azure_deployment='gpt-4o',
        azure_api_version='2024-02-15-preview',
        temperature=0.2,
        max_tokens=256,
        budget=None
    )
    
    start_time = time.time()
    successful_crates = 0
    failed_crates = []
    
    async with UnifiedSigilPipeline(config, llm_config) as pipeline:
        for i in range(0, len(remaining_crates), args.batch_size):
            batch = remaining_crates[i:i + args.batch_size]
            
            # Memory check before processing batch
            memory_usage = check_memory_usage()
            if memory_usage > args.memory_limit:
                logging.warning(f"⚠️  Memory usage ({memory_usage:.1f}%) exceeds limit ({args.memory_limit}%). Pausing...")
                # Force garbage collection
                import gc
                gc.collect()
                await asyncio.sleep(2)  # Brief pause
                memory_usage = check_memory_usage()
                logging.info(f"💾 Memory usage after GC: {memory_usage:.1f}%")
            
            logging.info(f"🔄 Processing batch {i//args.batch_size + 1}/{(len(remaining_crates) + args.batch_size - 1)//args.batch_size}: {batch}")
            
            try:
                results = await pipeline.analyze_multiple_crates(batch)
                successful_crates += len([r for r in results.values() if r is not None])
                
                batch_failed = [name for name, result in results.items() if result is None]
                failed_crates.extend(batch_failed)
                
                if batch_failed:
                    logging.warning(f"⚠️  Failed crates in batch: {batch_failed}")
                
                # Progress report
                elapsed = time.time() - start_time
                avg_time = elapsed / (successful_crates + len(failed_crates)) if (successful_crates + len(failed_crates)) > 0 else 0
                logging.info(f"✅ Progress: {successful_crates + len(failed_crates)}/{len(remaining_crates)} ({avg_time:.2f}s/crate)")
                
            except Exception as e:
                logging.error(f"❌ Batch failed: {e}")
                failed_crates.extend(batch)
    
    total_time = time.time() - start_time
    
    print(f"\n🎉 Resume pipeline completed!")
    print(f"✅ Successfully processed: {successful_crates} crates")
    print(f"❌ Failed: {len(failed_crates)} crates")
    print(f"⏱️  Total time: {total_time:.2f}s")
    print(f"📈 Average time per crate: {total_time/(successful_crates + len(failed_crates)):.2f}s")
    
    if failed_crates:
        print(f"\n⚠️  Failed crates: {failed_crates}")


if __name__ == "__main__":
    asyncio.run(main()) 