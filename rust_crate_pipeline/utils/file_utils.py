# rust_crate_pipeline/utils/file_utils.py
import json
import os
import shutil
from datetime import datetime
from typing import List, Dict


def create_output_dir(base_name: str = "crate_data") -> str:
    """
    Create timestamped output directory

    Args:
        base_name: Base name for output directory

    Returns:
        Path to created directory
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir = f"{base_name}_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def save_checkpoint(data: List[Dict], prefix: str, output_dir: str) -> str:
    """
    Save processing checkpoint with status metadata

    Args:
        data: List of crate dictionaries
        prefix: File name prefix
        output_dir: Target directory

    Returns:
        Path to saved checkpoint file
    """
    timestamp = datetime.now().isoformat()
    filename = os.path.join(output_dir, f"{prefix}_{timestamp}.jsonl")

    with open(filename, "w") as f:
        for item in data:
            f.write(json.dumps(item) + "\n")

    # Save status metadata
    status = {
        "timestamp": timestamp,
        "total_items": len(data),
        "checkpoint_file": filename,
    }

    status_file = os.path.join(output_dir, f"{prefix}_status_{timestamp}.json")
    with open(status_file, "w") as f:
        json.dump(status, f, indent=2)

    return filename


def safe_file_cleanup(path: str):
    """Safely remove files or directories"""
    try:
        if os.path.isfile(path):
            os.remove(path)
        elif os.path.isdir(path):
            shutil.rmtree(path)
    except Exception as e:
        print(f"Failed to cleanup {path}: {str(e)}")


def disk_space_check(min_free_gb: float = 1.0) -> bool:
    """Check if sufficient disk space is available"""
    try:
        free_bytes = shutil.disk_usage(".").free
        free_gb = free_bytes / (1024**3)
        return free_gb >= min_free_gb
    except Exception:
        return True  # Assume OK if check fails
