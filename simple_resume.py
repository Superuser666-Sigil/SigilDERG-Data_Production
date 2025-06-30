#!/usr/bin/env python3
"""
Simple Resume Script - Process remaining crates one by one
This avoids complex async issues that might be causing hangs
"""

import os
import json
import time
import logging
from pathlib import Path

# Set up basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
os.environ['AZURE_OPENAI_ENDPOINT'] = 'https://david-mc08tirc-eastus2.cognitiveservices.azure.com/'
os.environ['AZURE_OPENAI_API_KEY'] = '2hw0jjqwjtKke7DMGiJSPtlj6GhuLCNdQWPXoDGN2I3JMvzp4PmGJQQJ99BFACHYHv6XJ3w3AAAAACOGFPYA'
os.environ['AZURE_DEPLOYMENT_NAME'] = 'gpt-4o'
os.environ['AZURE_API_VERSION'] = '2025-01-01-preview'

def get_remaining_crates():
    """Get list of crates that still need processing"""
    processed = set()
    if os.path.exists('output'):
        for f in os.listdir('output'):
            if f.endswith('_enriched.json'):
                crate_name = f.replace('_enriched.json', '')
                processed.add(crate_name)
    
    with open('rust_crate_pipeline/crate_list.txt', 'r') as f:
        all_crates = [line.strip() for line in f if line.strip()]
    
    remaining = [c for c in all_crates if c not in processed]
    return remaining

def process_single_crate(crate_name):
    """Process a single crate using subprocess to avoid hanging"""
    import subprocess
    import sys
    
    cmd = [
        sys.executable, 'run_pipeline_with_llm.py',
        '--llm-provider', 'azure',
        '--llm-model', 'gpt-4o', 
        '--crates', crate_name,
        '--output-dir', 'output',
        '--batch-size', '1'
    ]
    
    logger.info(f"Processing {crate_name}...")
    
    try:
        # Run with timeout to prevent hanging
        result = subprocess.run(
            cmd, 
            timeout=300,  # 5 minute timeout
            capture_output=True, 
            text=True,
            cwd='.'
        )
        
        if result.returncode == 0:
            # Check if output file was created
            output_file = f'output/{crate_name}_enriched.json'
            if os.path.exists(output_file):
                logger.info(f"✅ Successfully processed {crate_name}")
                return True
            else:
                logger.warning(f"⚠️  Process completed but no output file for {crate_name}")
                return False
        else:
            logger.error(f"❌ Process failed for {crate_name}: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f"⏰ Timeout processing {crate_name}")
        return False
    except Exception as e:
        logger.error(f"💥 Error processing {crate_name}: {e}")
        return False

def main():
    remaining_crates = get_remaining_crates()
    logger.info(f"Found {len(remaining_crates)} crates to process")
    
    if not remaining_crates:
        logger.info("🎉 All crates already processed!")
        return
    
    successful = 0
    failed = 0
    
    # Process first 10 crates as a test
    test_crates = remaining_crates[:10]
    logger.info(f"Processing first 10 crates: {test_crates}")
    
    for crate_name in test_crates:
        if process_single_crate(crate_name):
            successful += 1
        else:
            failed += 1
            
        # Brief pause between crates
        time.sleep(2)
        
        logger.info(f"Progress: {successful} successful, {failed} failed")
    
    logger.info(f"Test batch complete: {successful}/{len(test_crates)} successful")

if __name__ == "__main__":
    main() 