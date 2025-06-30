#!/usr/bin/env python3
"""
Resume Utilities - Centralized auto-resume logic for enterprise pipeline
Consolidates scattered resume logic from multiple scripts into one reusable module
"""

import os
import logging
from pathlib import Path
from typing import List, Set, Tuple

logger = logging.getLogger(__name__)


def get_processed_crates(output_dir: str = "output") -> Set[str]:
    """
    Get set of already processed crates from output directory
    
    Args:
        output_dir: Directory containing enriched output files
        
    Returns:
        Set of crate names that have been processed
    """
    processed = set()
    
    if not os.path.exists(output_dir):
        logger.info(f"Output directory {output_dir} does not exist - starting fresh")
        return processed
    
    try:
        for filename in os.listdir(output_dir):
            if filename.endswith('_enriched.json'):
                # Extract crate name from filename
                crate_name = filename.replace('_enriched.json', '')
                processed.add(crate_name)
        
        logger.info(f"Found {len(processed)} already processed crates in {output_dir}")
        return processed
        
    except Exception as e:
        logger.error(f"Error reading output directory {output_dir}: {e}")
        return processed


def load_crate_list(crates_file: str = "rust_crate_pipeline/crate_list.txt") -> List[str]:
    """
    Load the master list of crates to process
    
    Args:
        crates_file: Path to file containing crate names (one per line)
        
    Returns:
        List of all crates to process
    """
    try:
        with open(crates_file, 'r', encoding='utf-8') as f:
            crates = [line.strip() for line in f if line.strip()]
        
        logger.info(f"Loaded {len(crates)} crates from {crates_file}")
        return crates
        
    except FileNotFoundError:
        logger.error(f"Crate list file not found: {crates_file}")
        return []
    except Exception as e:
        logger.error(f"Error loading crate list from {crates_file}: {e}")
        return []


def get_remaining_crates(
    crates_file: str = "rust_crate_pipeline/crate_list.txt",
    output_dir: str = "output",
    skip_problematic: bool = False
) -> Tuple[List[str], int, int]:
    """
    Enterprise-ready auto-resume: Get list of crates that need processing
    
    Args:
        crates_file: Path to master crate list
        output_dir: Directory containing processed outputs
        skip_problematic: Whether to skip known problematic crates
        
    Returns:
        Tuple of (remaining_crates, total_crates, already_processed_count)
    """
    # Load all crates from master list
    all_crates = load_crate_list(crates_file)
    if not all_crates:
        return [], 0, 0
    
    # Get already processed crates
    processed = get_processed_crates(output_dir)
    
    # Calculate remaining
    remaining = [crate for crate in all_crates if crate not in processed]
    
    # Filter out problematic crates if requested
    if skip_problematic:
        original_count = len(remaining)
        remaining = [c for c in remaining if not _is_problematic_crate(c)]
        skipped_count = original_count - len(remaining)
        if skipped_count > 0:
            logger.info(f"⚠️  Skipped {skipped_count} known problematic crates")
    
    logger.info(f"📊 Resume Analysis:")
    logger.info(f"   Total crates: {len(all_crates)}")
    logger.info(f"   Already processed: {len(processed)}")
    logger.info(f"   Remaining: {len(remaining)}")
    logger.info(f"   Progress: {len(processed)}/{len(all_crates)} ({len(processed)/len(all_crates)*100:.1f}%)")
    
    return remaining, len(all_crates), len(processed)


def _is_problematic_crate(crate_name: str) -> bool:
    """
    Check if a crate should be skipped due to known issues
    Consolidated from run_pipeline_remaining.py
    """
    # Known problematic crates that cause issues
    problematic_crates = {
        'kuchiki',      # Large output files (1.54GB+)
        'syn',          # Macro heavy, memory intensive
        'proc-macro2',  # Macro processing issues
        'html5ever',    # HTML parsing memory issues
        'scraper',      # Large dependency trees
        'webpki',       # Complex certificate parsing
        'ring',         # Cryptographic library compilation issues
    }
    
    return crate_name.lower() in problematic_crates


def validate_resume_state(
    remaining_crates: List[str],
    total_crates: int,
    processed_count: int,
    output_dir: str = "output"
) -> bool:
    """
    Validate that the resume state is consistent and safe to proceed
    
    Args:
        remaining_crates: List of crates still to process
        total_crates: Total number of crates in master list
        processed_count: Number of already processed crates
        output_dir: Output directory to validate
        
    Returns:
        True if resume state is valid and safe
    """
    try:
        # Basic sanity checks
        if processed_count + len(remaining_crates) != total_crates:
            logger.error(f"Resume state inconsistent: {processed_count} + {len(remaining_crates)} != {total_crates}")
            return False
        
        # Verify output directory exists and is writable
        os.makedirs(output_dir, exist_ok=True)
        test_file = os.path.join(output_dir, ".pipeline_test")
        try:
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
        except Exception as e:
            logger.error(f"Output directory {output_dir} is not writable: {e}")
            return False
        
        # Check for reasonable progress (not starting over)
        if processed_count > 0:
            logger.info(f"✅ Resuming from {processed_count}/{total_crates} completed ({processed_count/total_crates*100:.1f}%)")
        else:
            logger.info("🆕 Starting fresh pipeline run")
        
        return True
        
    except Exception as e:
        logger.error(f"Resume state validation failed: {e}")
        return False


def create_resume_report(
    remaining_crates: List[str],
    total_crates: int,
    processed_count: int,
    output_dir: str = "output"
) -> str:
    """
    Generate a human-readable resume report
    
    Returns:
        Formatted report string
    """
    progress_pct = (processed_count / total_crates * 100) if total_crates > 0 else 0
    
    report = f"""
🔄 **Pipeline Resume Report**
========================

📊 **Progress Summary:**
   • Total crates: {total_crates:,}
   • Already processed: {processed_count:,}
   • Remaining: {len(remaining_crates):,}
   • Progress: {progress_pct:.1f}%

🎯 **Next Actions:**
   • Will process {len(remaining_crates)} remaining crates
   • Output directory: {output_dir}
   • Resume mode: {'Continuing' if processed_count > 0 else 'Starting fresh'}

⚡ **Performance:**
   • Estimated time: {len(remaining_crates) * 30} seconds (30s/crate avg)
   • Memory usage: Optimized batch processing
   • Auto-skip: Already processed crates automatically skipped
"""
    
    return report.strip() 