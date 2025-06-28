#!/usr/bin/env python3
"""
Remote deployment configuration for G2-Standard-4 with L4 GPU
Using local DeepSeek model at ~/models/deepseek
"""

import os
from pathlib import Path

# GPU Configuration
os.environ["CUDA_VISIBLE_DEVICES"] = "0"  # Use first GPU (L4)
os.environ["TOKENIZERS_PARALLELISM"] = "false"  # Avoid tokenizer warnings

# Model Configuration
DEEPSEEK_MODEL_PATH = os.path.expanduser("~/models/deepseek")
os.environ["DEEPSEEK_MODEL_PATH"] = DEEPSEEK_MODEL_PATH

# LLM Provider Configuration
LLM_CONFIG = {
    "provider": "ollama",  # Using Ollama for local model
    "model_name": "deepseek-coder:33b",  # Adjust based on your model name
    "base_url": "http://localhost:11434",  # Ollama default URL
    "api_key": "ollama",  # Not needed for local Ollama
    "temperature": 0.1,
    "max_tokens": 4096,
    "timeout": 120
}

# Pipeline Configuration
PIPELINE_CONFIG = {
    "max_workers": 4,  # G2-Standard-4 has 4 vCPUs
    "batch_size": 2,   # Conservative batch size for GPU memory
    "enable_gpu": True,
    "gpu_memory_fraction": 0.8,  # Use 80% of GPU memory
    "crate_limit": 50,  # Process 50 crates per run
    "output_dir": "./output",
    "log_level": "INFO"
}

# Database Configuration
DB_CONFIG = {
    "rag_cache_path": "./sigil_rag_cache.db",
    "enable_caching": True,
    "cache_ttl": 3600  # 1 hour cache TTL
}

# API Tokens (set these as environment variables)
REQUIRED_TOKENS = {
    "GITHUB_TOKEN": "Your GitHub token for API access",
    "PYPI_TOKEN": "Your PyPI token for package metadata"
}

def setup_environment():
    """Setup environment variables for remote deployment"""
    # Set GPU environment
    os.environ["CUDA_VISIBLE_DEVICES"] = "0"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    
    # Set model path
    os.environ["DEEPSEEK_MODEL_PATH"] = DEEPSEEK_MODEL_PATH
    
    # Verify model exists
    if not Path(DEEPSEEK_MODEL_PATH).exists():
        print(f"Warning: DeepSeek model not found at {DEEPSEEK_MODEL_PATH}")
        print("Please ensure the model is properly installed")
    
    # Verify required tokens
    missing_tokens = []
    for token_name in REQUIRED_TOKENS:
        if not os.environ.get(token_name):
            missing_tokens.append(token_name)
    
    if missing_tokens:
        print(f"Warning: Missing environment variables: {missing_tokens}")
        print("Some features may not work without these tokens")

if __name__ == "__main__":
    setup_environment()
    print("Remote configuration loaded successfully")
    print(f"DeepSeek model path: {DEEPSEEK_MODEL_PATH}")
    print(f"GPU enabled: {PIPELINE_CONFIG['enable_gpu']}")
    print(f"Max workers: {PIPELINE_CONFIG['max_workers']}") 