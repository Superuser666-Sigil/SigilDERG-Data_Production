#!/usr/bin/env python3
"""
Azure OpenAI Connection Test - Find working configuration
Tests different timeout and retry strategies to avoid hanging
"""

import os
import time
import litellm
from typing import Dict, Any

def test_azure_config(config_name: str, config: Dict[str, Any]) -> bool:
    """Test a specific Azure configuration"""
    print(f"\n--- Testing {config_name} ---")
    
    # Apply configuration
    if 'timeout' in config:
        litellm.request_timeout = config['timeout']
    if 'retries' in config:
        litellm.num_retries = config['retries']
    
    start_time = time.time()
    try:
        response = litellm.completion(
            model="azure/gpt-4o",
            messages=[{"role": "user", "content": "Test connection"}],
            api_key=os.getenv('AZURE_OPENAI_API_KEY'),
            api_base=os.getenv('AZURE_OPENAI_ENDPOINT'),
            api_version=config.get('api_version', '2025-01-01-preview'),
            timeout=config.get('call_timeout', config.get('timeout', 30)),
            max_tokens=20
        )
        duration = time.time() - start_time
        print(f"✅ SUCCESS in {duration:.2f}s")
        print(f"   Response: {response.choices[0].message.content[:50]}...")
        return True
        
    except Exception as e:
        duration = time.time() - start_time
        print(f"❌ FAILED in {duration:.2f}s: {type(e).__name__}")
        print(f"   Error: {str(e)[:100]}...")
        return False

def main():
    print("🔧 Azure OpenAI Connection Diagnostics")
    print("=" * 50)
    
    # Check credentials
    if not os.getenv('AZURE_OPENAI_API_KEY'):
        print("❌ AZURE_OPENAI_API_KEY not found in environment")
        return
    if not os.getenv('AZURE_OPENAI_ENDPOINT'):
        print("❌ AZURE_OPENAI_ENDPOINT not found in environment")
        return
    
    print(f"Endpoint: {os.getenv('AZURE_OPENAI_ENDPOINT')}")
    print(f"Key: {os.getenv('AZURE_OPENAI_API_KEY')[:10]}...")
    
    # Test configurations from least to most aggressive
    configs = {
        "Conservative (60s timeout)": {
            "timeout": 60,
            "retries": 1,
            "api_version": "2024-02-01"
        },
        "Fast Fail (30s timeout)": {
            "timeout": 30,
            "retries": 0,
            "api_version": "2025-01-01-preview"
        },
        "Ultra Fast (15s timeout)": {
            "timeout": 15,
            "retries": 0,
            "call_timeout": 15,
            "api_version": "2025-01-01-preview"
        },
        "Different API Version": {
            "timeout": 30,
            "retries": 0,
            "api_version": "2024-06-01"
        },
        "Minimal Timeout (10s)": {
            "timeout": 10,
            "retries": 0,
            "call_timeout": 10,
            "api_version": "2025-01-01-preview"
        }
    }
    
    working_configs = []
    
    for config_name, config in configs.items():
        if test_azure_config(config_name, config):
            working_configs.append((config_name, config))
    
    print("\n" + "=" * 50)
    print("📊 RESULTS SUMMARY")
    print("=" * 50)
    
    if working_configs:
        print(f"✅ Found {len(working_configs)} working configuration(s):")
        for name, config in working_configs:
            print(f"   • {name}: timeout={config.get('timeout')}s, retries={config.get('retries')}")
        
        print(f"\n🎯 RECOMMENDED: Use '{working_configs[0][0]}'")
        best_config = working_configs[0][1]
        print("   Apply these settings to your pipeline:")
        print(f"   - timeout: {best_config.get('timeout')} seconds")
        print(f"   - retries: {best_config.get('retries')}")
        print(f"   - api_version: {best_config.get('api_version')}")
        
    else:
        print("❌ No working configurations found.")
        print("   This suggests a deeper Azure OpenAI service issue.")
        print("   Try again in a few minutes, or contact Azure support.")

if __name__ == "__main__":
    main() 