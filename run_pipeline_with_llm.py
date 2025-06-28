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

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from rust_crate_pipeline.unified_pipeline import (
    UnifiedSigilPipeline, 
    create_pipeline_from_args, 
    add_llm_arguments,
    quick_analyze_crate,
    batch_analyze_crates
)
from rust_crate_pipeline.config import PipelineConfig


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('pipeline.log')
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
        if not args.llm_api_key:
            print("❌ Azure API key required. Use --llm-api-key.")
            return False
        if not args.azure_deployment:
            print("❌ Azure deployment name required. Use --azure-deployment.")
            return False
    
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


async def main() -> None:
    """Main function"""
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
        required=True,
        help='List of Rust crates to analyze'
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
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    # Validate configuration
    if not validate_llm_config(args):
        sys.exit(1)
    
    # Print provider information
    print_llm_provider_info(args.llm_provider)
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    
    try:
        # Create pipeline from arguments
        logger.info("🚀 Initializing unified pipeline...")
        pipeline = create_pipeline_from_args(args)
        
        # Print pipeline summary
        summary = pipeline.get_pipeline_summary()
        logger.info(f"📊 Pipeline Summary: {summary}")
        
        # Analyze crates
        logger.info(f"🔍 Starting analysis of {len(args.crates)} crates...")
        
        if len(args.crates) == 1:
            # Single crate analysis
            crate_name = args.crates[0]
            logger.info(f"📦 Analyzing single crate: {crate_name}")
            
            trace = await quick_analyze_crate(crate_name, pipeline.config, pipeline.llm_config)
            
            # Save results
            output_file = output_dir / f"{crate_name}_analysis.json"
            with open(output_file, 'w') as f:
                json.dump(asdict(trace), f, indent=2, default=str)
            
            logger.info(f"✅ Analysis completed for {crate_name}")
            logger.info(f"📄 Results saved to: {output_file}")
            
        else:
            # Batch analysis
            logger.info(f"📦 Analyzing {len(args.crates)} crates in batch...")
            
            results = await batch_analyze_crates(args.crates, pipeline.config, pipeline.llm_config)
            
            # Save results
            for crate_name, trace in results.items():
                output_file = output_dir / f"{crate_name}_analysis.json"
                with open(output_file, 'w') as f:
                    json.dump(asdict(trace), f, indent=2, default=str)
                logger.info(f"📄 Results saved to: {output_file}")
            
            logger.info(f"✅ Batch analysis completed for {len(results)} crates")
        
        # Print final summary
        successful = len([c for c in args.crates if (output_dir / f"{c}_analysis.json").exists()])
        logger.info(f"🎉 Pipeline completed successfully!")
        logger.info(f"📊 Processed: {successful}/{len(args.crates)} crates")
        logger.info(f"📁 Output directory: {output_dir.absolute()}")
        
    except KeyboardInterrupt:
        logger.info("⏹️  Pipeline interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Pipeline failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 