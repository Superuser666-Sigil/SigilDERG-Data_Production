#!/usr/bin/env python3
"""
Enterprise Rust Crate Pipeline with LLM Enrichment

Multi-provider LLM support with intelligent auto-resume capability.
Consolidates and replaces: run_pipeline_with_llm.py, run_production.py, run_pipeline_remaining.py

Supported Providers:
- Azure OpenAI (recommended)
- OpenAI API
- Anthropic Claude
- Ollama (local models)
- LM Studio (local models)
- Google AI, and all other LiteLLM providers

Enterprise Features:
- ✅ Auto-resume: Automatically skips already processed crates
- ✅ Progress tracking: Real-time progress monitoring
- ✅ Error recovery: Robust error handling and retries
- ✅ Memory optimization: Configurable batch sizes
- ✅ Cost control: Budget management and tracking

Usage Examples:

# Resume Azure OpenAI processing (recommended)
python run_with_llm.py --provider azure --model gpt-4o

# Process specific crates with OpenAI
python run_with_llm.py --provider openai --model gpt-4 --api-key YOUR_KEY --crates tokio serde

# Resume with local Ollama model
python run_with_llm.py --provider ollama --model llama2

# Custom batch size for memory optimization
python run_with_llm.py --provider azure --model gpt-4o --batch-size 2

# Skip known problematic crates
python run_with_llm.py --provider azure --model gpt-4o --skip-problematic
"""

import asyncio
import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import List, Optional

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from rust_crate_pipeline.unified_pipeline import (
    UnifiedSigilPipeline, 
    add_llm_arguments,
    quick_analyze_crate,
)
from rust_crate_pipeline.config import PipelineConfig, CrateMetadata
from rust_crate_pipeline.unified_llm_processor import (
    create_llm_processor_from_args,
    BudgetManager,
    UnifiedLLMProcessor,
)
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
    
    file_handler = logging.FileHandler('pipeline.log', encoding='utf-8')
    file_handler.setFormatter(detailed_formatter)
    file_handler.setLevel(logging.DEBUG)
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        handlers=[console_handler, file_handler]
    )


def validate_llm_config(args: argparse.Namespace) -> bool:
    """Validate LLM configuration before proceeding"""
    logger = logging.getLogger(__name__)
    
    # Provider-specific validation
    if args.llm_provider == 'azure':
        if not args.llm_api_key:
            logger.error("Azure OpenAI requires --api-key")
            return False
        if not args.llm_api_base:
            logger.error("Azure OpenAI requires --api-base")
            return False
            
    elif args.llm_provider == 'openai':
        if not args.llm_api_key:
            logger.error("OpenAI requires --api-key")
            return False
            
    elif args.llm_provider == 'anthropic':
        if not args.llm_api_key:
            logger.error("Anthropic requires --api-key")
            return False
    
    # Budget validation
    if args.budget and args.budget <= 0:
        logger.error("Budget must be positive")
        return False
    
    return True


def print_llm_provider_info(provider: str) -> None:
    """Print information about the selected LLM provider"""
    provider_info = {
        'azure': '🔵 Azure OpenAI - Enterprise-grade with high rate limits',
        'openai': '🟢 OpenAI API - Direct access to latest models',
        'anthropic': '🟠 Anthropic Claude - Advanced reasoning capabilities',
        'ollama': '🔴 Ollama - Local models, privacy-focused',
        'lmstudio': '🟡 LM Studio - Local models with studio interface',
    }
    
    info = provider_info.get(provider, f'🟣 {provider.title()} - Third-party LLM provider')
    print(f"\n{info}")
    print("=" * 60)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments with enterprise defaults"""
    parser = argparse.ArgumentParser(
        description="Enterprise Rust Crate Pipeline with LLM Enrichment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Add LLM arguments from unified processor
    add_llm_arguments(parser)
    
    # Pipeline-specific arguments
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
        default=5,
        help='Crates to process in parallel (default: 5, reduce for memory issues)'
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
        '--budget',
        type=float,
        help='Maximum budget for LLM API calls (USD)'
    )
    
    # Set enterprise defaults
    args = parser.parse_args()
    
    # Load environment variables for Azure by default
    if args.llm_provider == 'azure' and not args.llm_api_key:
        import os
        args.llm_api_key = os.getenv('AZURE_OPENAI_API_KEY')
        args.llm_api_base = os.getenv('AZURE_OPENAI_ENDPOINT', 
                                     'https://david-mc08tirc-eastus2.cognitiveservices.azure.com/')
        args.azure_deployment = os.getenv('AZURE_DEPLOYMENT_NAME', 'gpt-4o')
        args.azure_api_version = os.getenv('AZURE_API_VERSION', '2025-01-01-preview')
    
    return args


def report_progress(current: int, total: int, start_time: float, 
                   budget_manager: Optional[BudgetManager] = None) -> None:
    """Report processing progress with enterprise metrics"""
    elapsed = time.time() - start_time
    rate = current / elapsed if elapsed > 0 else 0
    remaining = total - current
    eta = remaining / rate if rate > 0 else 0
    
    progress_msg = f"Progress: {current}/{total} ({current/total*100:.1f}%) - "
    progress_msg += f"Rate: {rate:.2f} crates/sec - "
    progress_msg += f"ETA: {eta/60:.1f} min"
    
    if budget_manager:
        progress_msg += f" - Cost: ${budget_manager.total_cost:.3f}"
        if budget_manager.budget:
            progress_msg += f"/${budget_manager.budget:.2f}"
    
    logging.info(progress_msg)


async def process_crate_with_llm(
    crate_name: str,
    llm_processor: 'UnifiedLLMProcessor',
    output_dir: Path,
    pipeline_config: PipelineConfig
) -> bool:
    """Process a single crate with LLM enrichment"""
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"🔄 Analyzing crate: {crate_name}")
        
        # First, get basic metadata using the quick analysis
        trace = await quick_analyze_crate(crate_name, pipeline_config, llm_processor.config)
        crate_metadata_dict = trace.audit_info.get("crate_metadata")

        if not crate_metadata_dict:
            logger.error(f"❌ Could not retrieve metadata for {crate_name}")
            return False
        
        # Re-create the CrateMetadata object
        crate_metadata = CrateMetadata(**crate_metadata_dict)

        logger.info(f"🤖 Enriching crate with LLM: {crate_name}")
        
        # Enrich with LLM
        enriched_crate = llm_processor.enrich_crate(crate_metadata)
        
        if not enriched_crate:
            logger.error(f"❌ LLM enrichment failed for {crate_name}")
            return False

        # Convert to serializable format
        try:
            enriched_data = to_serializable(enriched_crate.to_dict())
        except Exception as e:
            logger.warning(f"⚠️  Serialization issue for {crate_name}: {e}")
            # Fallback: ensure basic serializability
            enriched_data = {
                'name': crate_name,
                'enrichment_error': str(e),
                'basic_metadata': crate_metadata_dict
            }

        # Save enriched crate
        output_file = output_dir / f"{crate_name}_enriched.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(enriched_data, f, indent=2, default=str)
        
        logger.info(f"✅ Successfully processed: {crate_name}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to process {crate_name}: {e}")
        return False


async def main() -> None:
    """Main enterprise pipeline execution"""
    args = parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    logger.info("🚀 Starting Enterprise Rust Crate Pipeline with LLM Enrichment")
    
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
    
    # Validate LLM configuration
    if not validate_llm_config(args):
        sys.exit(1)
    
    # Print provider information
    print_llm_provider_info(args.llm_provider)
    
    # Create LLM processor
    try:
        llm_processor = create_llm_processor_from_args(
            provider=args.llm_provider,
            model=args.llm_model,
            api_base=args.llm_api_base,
            api_key=args.llm_api_key,
            temperature=args.llm_temperature,
            max_tokens=args.llm_max_tokens,
            azure_deployment=args.azure_deployment,
            azure_api_version=args.azure_api_version,
            ollama_host=args.ollama_host,
            lmstudio_host=args.lmstudio_host,
            budget=args.budget,
        )
    except Exception as e:
        logger.error(f"❌ Failed to create LLM processor: {e}")
        sys.exit(1)

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    # Initialize progress monitoring
    progress_monitor = ProgressMonitor(total_crates, str(output_dir))
    
    # Create pipeline config
    pipeline_config = PipelineConfig(
        use_azure_openai=args.llm_provider == 'azure',
        azure_openai_endpoint=args.llm_api_base,
        azure_openai_api_key=args.llm_api_key,
        azure_openai_deployment_name=args.azure_deployment,
        azure_openai_api_version=args.azure_api_version,
        batch_size=args.batch_size,
    )

    # Process crates
    start_time = time.time()
    successful = 0
    failed = 0
    
    logger.info(f"🎯 Processing {len(crates_to_process)} crates with batch size {args.batch_size}")
    
    for i, crate_name in enumerate(crates_to_process):
        progress_monitor.start_crate(crate_name)
        crate_start_time = time.time()
        
        try:
            success = await process_crate_with_llm(
                crate_name, llm_processor, output_dir, pipeline_config
            )
            
            crate_time = time.time() - crate_start_time
            progress_monitor.complete_crate(crate_name, success, crate_time)
            
            if success:
                successful += 1
            else:
                failed += 1
                
        except Exception as e:
            logger.error(f"❌ Unexpected error processing {crate_name}: {e}")
            progress_monitor.complete_crate(crate_name, False)
            failed += 1
        
        # Report progress every 10 crates or at the end
        if (i + 1) % 10 == 0 or i == len(crates_to_process) - 1:
            report_progress(i + 1, len(crates_to_process), start_time, llm_processor.budget_manager)

    # Final report
    total_time = time.time() - start_time
    overall_successful = processed_count + successful
    
    logger.info("\n" + "="*60)
    logger.info("📊 PIPELINE COMPLETION REPORT")
    logger.info("="*60)
    logger.info(f"✅ Successful: {successful}")
    logger.info(f"❌ Failed: {failed}")
    logger.info(f"⏱️  Total time: {total_time/60:.1f} minutes")
    logger.info(f"📈 Overall progress: {overall_successful}/{total_crates} ({overall_successful/total_crates*100:.1f}%)")
    
    if llm_processor.budget_manager:
        logger.info(f"💰 Total cost: ${llm_processor.budget_manager.total_cost:.3f}")
    
    if overall_successful == total_crates:
        logger.info("🎉 PIPELINE COMPLETED SUCCESSFULLY!")
    else:
        remaining = total_crates - overall_successful
        logger.info(f"🔄 {remaining} crates remaining - run again to continue")


if __name__ == "__main__":
    asyncio.run(main()) 