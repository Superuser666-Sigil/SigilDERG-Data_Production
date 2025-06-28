#!/usr/bin/env python3
"""
Unified Rust Crate Pipeline with Multi-LLM Provider Support

This script demonstrates how to use the unified pipeline with different LLM providers:
- Azure OpenAI
- Ollama (local models)
- LM Studio (local models)
- OpenAI
- Anthropic
- Google AI
- And all other LiteLLM providers

Usage Examples:

# Azure OpenAI (default)
python run_pipeline_with_llm.py --llm-provider azure --llm-model gpt-4o --crates tokio serde

# Ollama with local model
python run_pipeline_with_llm.py --llm-provider ollama --llm-model llama2 --crates tokio

# LM Studio with local model
python run_pipeline_with_llm.py --llm-provider lmstudio --llm-model llama2 --crates serde

# OpenAI API
python run_pipeline_with_llm.py --llm-provider openai --llm-model gpt-4 --llm-api-key YOUR_KEY --crates tokio

# Anthropic Claude
python run_pipeline_with_llm.py --llm-provider anthropic --llm-model claude-3-sonnet --llm-api-key YOUR_KEY --crates serde

# Custom API endpoint
python run_pipeline_with_llm.py --llm-provider openai --llm-model gpt-4 --llm-api-base https://api.openai.com/v1 --crates tokio
"""

import asyncio
import argparse
import logging
import sys
import json
from pathlib import Path
from typing import List, Optional
from dataclasses import asdict
import time

# Add the project root to the path
sys.path.append(str(Path(__file__).parent.parent))

from rust_crate_pipeline.unified_pipeline import (
    UnifiedSigilPipeline, 
    create_pipeline_from_args, 
    add_llm_arguments,
    quick_analyze_crate,
    batch_analyze_crates
)
from rust_crate_pipeline.config import PipelineConfig
from rust_crate_pipeline.unified_llm_processor import (
    create_llm_processor_from_args,
    BudgetManager,
)
from rust_crate_pipeline.config import CrateMetadata, EnrichedCrate


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('pipeline.log', encoding='utf-8')
        ]
    )


def validate_llm_config(args: argparse.Namespace) -> bool:
    """Validate LLM configuration"""
    if not args.llm_provider:
        print("❌ No LLM provider specified. Use --llm-provider to specify one.")
        return False
    
    # Check provider-specific requirements
    if args.llm_provider in ['openai', 'anthropic', 'google', 'cohere']:
        if not args.llm_api_key:
            print(f"❌ API key required for {args.llm_provider}. Use --llm-api-key.")
            return False
    
    if args.llm_provider == 'azure':
        # These are now loaded from environment variables by default
        pass
    
    if not args.llm_model:
        print("❌ Model name required. Use --llm-model.")
        return False
    
    return True


def print_llm_provider_info(provider: str) -> None:
    """Print information about the selected LLM provider"""
    provider_info = {
        'azure': {
            'name': 'Azure OpenAI',
            'description': 'Microsoft Azure OpenAI Service',
            'setup': 'Requires Azure OpenAI endpoint, API key, and deployment name',
            'models': 'gpt-4, gpt-4o, gpt-35-turbo, etc.'
        },
        'ollama': {
            'name': 'Ollama',
            'description': 'Local LLM server for running open-source models',
            'setup': 'Install Ollama and run: ollama serve',
            'models': 'llama2, codellama, mistral, etc.'
        },
        'lmstudio': {
            'name': 'LM Studio',
            'description': 'Local LLM server with GUI for model management',
            'setup': 'Install LM Studio and start the local server',
            'models': 'llama2, codellama, mistral, etc.'
        },
        'openai': {
            'name': 'OpenAI',
            'description': 'OpenAI API service',
            'setup': 'Requires OpenAI API key',
            'models': 'gpt-4, gpt-3.5-turbo, etc.'
        },
        'anthropic': {
            'name': 'Anthropic',
            'description': 'Anthropic Claude API service',
            'setup': 'Requires Anthropic API key',
            'models': 'claude-3-sonnet, claude-3-haiku, claude-3-opus, etc.'
        },
        'google': {
            'name': 'Google AI',
            'description': 'Google AI (Gemini) API service',
            'setup': 'Requires Google AI API key',
            'models': 'gemini-pro, gemini-pro-vision, etc.'
        }
    }
    
    info = provider_info.get(provider, {
        'name': provider.title(),
        'description': 'Custom LLM provider',
        'setup': 'Check provider documentation',
        'models': 'Varies by provider'
    })
    
    print(f"\n🤖 Using LLM Provider: {info['name']}")
    print(f"📝 Description: {info['description']}")
    print(f"⚙️  Setup: {info['setup']}")
    print(f"🧠 Models: {info['models']}")


def report_progress(
    processed_crates: int,
    total_crates: int,
    start_time: float,
    budget_manager: Optional[BudgetManager] = None,
) -> None:
    """Report the progress of the pipeline run."""
    elapsed_time = time.time() - start_time
    avg_time_per_crate = elapsed_time / processed_crates if processed_crates > 0 else 0
    
    progress_message = (
        f"Processed {processed_crates}/{total_crates} crates "
        f"({avg_time_per_crate:.2f}s/crate, total: {elapsed_time:.2f}s)"
    )

    if budget_manager:
        progress_message += (
            f" | Cost: ${budget_manager.get_total_cost():.4f}"
        )
    
    print(progress_message)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Unified Rust Crate Pipeline with Multi-LLM Provider Support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Add LLM arguments
    add_llm_arguments(parser)
    
    # Add pipeline arguments
    parser.add_argument(
        '--crates',
        nargs='+',
        required=False,
        help='List of Rust crates to analyze'
    )
    
    parser.add_argument(
        '--crates-file',
        type=str,
        help='Path to a file containing a list of Rust crates to analyze (one per line)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    parser.add_argument(
        '--output-dir',
        default='output',
        help='Output directory for analysis results (default: output)'
    )
    
    parser.add_argument(
        '--batch-size',
        type=int,
        default=5,
        help='Number of crates to process in parallel (default: 5)'
    )
    
    parser.add_argument(
        "--budget",
        type=float,
        default=None,
        help="Maximum budget for LLM API calls.",
    )
    
    args = parser.parse_args()

    if not args.crates and not args.crates_file:
        parser.error("at least one of --crates or --crates-file is required")

    return args


async def main() -> None:
    """Main function"""
    args = parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    if not args.crates and not args.crates_file:
        logger.error("You must provide either --crates or --crates-file.")
        sys.exit(1)

    if args.crates_file:
        try:
            with open(args.crates_file, 'r') as f:
                args.crates = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            logger.error(f"Crates file not found: {args.crates_file}")
            sys.exit(1)

    if not args.crates:
        logger.error("No crates to analyze.")
        sys.exit(1)
    
    # Validate configuration
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
    except ImportError as e:
        logger.error(f"Failed to create LLM processor: {e}")
        sys.exit(1)

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    # Process crates
    crates_to_process = args.crates
    total_crates = len(crates_to_process)
    start_time = time.time()
    
    logger.info(f"Starting LLM enrichment for {total_crates} crates...")
    
    # Create a pipeline config to pass to quick_analyze_crate
    pipeline_config = PipelineConfig(
        use_azure_openai=args.llm_provider == 'azure',
        azure_openai_endpoint=args.llm_api_base,
        azure_openai_api_key=args.llm_api_key,
        azure_openai_deployment_name=args.azure_deployment,
        azure_openai_api_version=args.azure_api_version,
    )

    for i, crate_name in enumerate(crates_to_process):
        try:
            logger.info(f"Analyzing crate: {crate_name}")
            
            # First, get the basic metadata by running the analysis part of the pipeline
            trace = await quick_analyze_crate(crate_name, pipeline_config, llm_processor.config)
            crate_metadata_dict = trace.audit_info.get("crate_metadata")

            if not crate_metadata_dict:
                logger.error(f"Could not retrieve metadata for {crate_name}. Skipping enrichment.")
                continue
            
            # Re-create the CrateMetadata object from the dictionary
            crate_metadata = CrateMetadata(**crate_metadata_dict)

            logger.info(f"Enriching crate: {crate_name}")
            # Enrich crate with LLM
            enriched_crate = llm_processor.enrich_crate(crate_metadata)
            
            # Save enriched data
            output_file = output_dir / f"{crate_name}_enriched.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(asdict(enriched_crate), f, indent=4)
            
            logger.info(f"Successfully processed and saved: {output_file}")
            
        except Exception as e:
            logger.error(f"Failed to process {crate_name}: {e}")
            
        finally:
            report_progress(i + 1, total_crates, start_time, llm_processor.budget_manager)

    logger.info("LLM enrichment pipeline finished.")


if __name__ == "__main__":
    asyncio.run(main()) 