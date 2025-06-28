#!/usr/bin/env python3
"""
Test script to verify feature handling fixes for both dict and list formats using real Azure OpenAI credentials and config.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'rust_crate_pipeline'))

import rust_crate_pipeline.config as config
import rust_crate_pipeline.ai_processing as ai_processing
import rust_crate_pipeline.azure_ai_processing as azure_ai_processing

def get_azure_pipeline_config():
    endpoint = os.environ.get('AZURE_OPENAI_ENDPOINT', '')
    api_key = os.environ.get('AZURE_OPENAI_API_KEY', '')
    deployment = os.environ.get('AZURE_OPENAI_DEPLOYMENT_NAME', '')
    api_version = os.environ.get('AZURE_OPENAI_API_VERSION', '2024-02-15-preview')
    if not all([endpoint, api_key, deployment]):
        raise RuntimeError("Azure OpenAI environment variables are not all set.")
    return config.PipelineConfig(
        use_azure_openai=True,
        azure_openai_endpoint=endpoint,
        azure_openai_api_key=api_key,
        azure_openai_deployment_name=deployment,
        azure_openai_api_version=api_version
    )

def get_llm_config():
    # Use Azure as provider for LLMEnricher if available, else fallback to local
    endpoint = os.environ.get('AZURE_OPENAI_ENDPOINT', '')
    api_key = os.environ.get('AZURE_OPENAI_API_KEY', '')
    deployment = os.environ.get('AZURE_OPENAI_DEPLOYMENT_NAME', '')
    api_version = os.environ.get('AZURE_OPENAI_API_VERSION', '2024-02-15-preview')
    
    # Always use Azure if credentials are available
    if all([endpoint, api_key, deployment]):
        return config.PipelineConfig(
            use_azure_openai=True,
            azure_openai_endpoint=endpoint,
            azure_openai_api_key=api_key,
            azure_openai_deployment_name=deployment,
            azure_openai_api_version=api_version
        )
    else:
        # Fallback: use local config (should be set up in your environment)
        return config.PipelineConfig()

def test_feature_handling():
    """Test that feature handling works for both dict and list formats."""
    
    # Test with dict features (normal case)
    crate_dict = config.CrateMetadata(
        name="test-crate-dict",
        version="1.0.0",
        description="Test crate with dict features",
        repository="https://github.com/test/test-crate",
        keywords=["test", "rust"],
        categories=["dev-tools"],
        readme="# Test README\nThis is a test crate.",
        downloads=1000,
        github_stars=50,
        features={
            "default": ["serde"],
            "async": ["tokio"],
            "web": ["actix-web"]
        }
    )
    
    # Test with list features (problematic case)
    # We use a workaround: create as dict, then assign list to .features
    crate_list = config.CrateMetadata(
        name="test-crate-list",
        version="1.0.0",
        description="Test crate with list features",
        repository="https://github.com/test/test-crate",
        keywords=["test", "rust"],
        categories=["dev-tools"],
        readme="# Test README\nThis is a test crate.",
        downloads=1000,
        github_stars=50,
        features={}
    )
    crate_list.features = ["default", "async", "web"]
    
    # Test with empty features
    crate_empty = config.CrateMetadata(
        name="test-crate-empty",
        version="1.0.0",
        description="Test crate with no features",
        repository="https://github.com/test/test-crate",
        keywords=["test", "rust"],
        categories=["dev-tools"],
        readme="# Test README\nThis is a test crate.",
        downloads=1000,
        github_stars=50,
        features={}
    )
    
    print("Testing feature handling fixes...")
    
    # Test LLMEnricher
    try:
        llm_config = get_llm_config()
        enricher = ai_processing.LLMEnricher(llm_config)
        
        # Test summarize_features
        print("\n1. Testing LLMEnricher.summarize_features:")
        result_dict = enricher.summarize_features(crate_dict)
        print(f"   Dict features: {result_dict[:100]}...")
        
        result_list = enricher.summarize_features(crate_list)
        print(f"   List features: {result_list[:100]}...")
        
        result_empty = enricher.summarize_features(crate_empty)
        print(f"   Empty features: {result_empty[:100]}...")
        
        # Test generate_factual_pairs
        print("\n2. Testing LLMEnricher.generate_factual_pairs:")
        result_dict = enricher.generate_factual_pairs(crate_dict)
        print(f"   Dict features: {result_dict[:100]}...")
        
        result_list = enricher.generate_factual_pairs(crate_list)
        print(f"   List features: {result_list[:100]}...")
        
        result_empty = enricher.generate_factual_pairs(crate_empty)
        print(f"   Empty features: {result_empty[:100]}...")
        
        print("\n✅ LLMEnricher tests passed!")
        
    except Exception as e:
        print(f"\n❌ LLMEnricher test failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Test AzureOpenAIEnricher
    try:
        azure_config = get_azure_pipeline_config()
        azure_enricher = azure_ai_processing.AzureOpenAIEnricher(azure_config)
        
        # Test summarize_features
        print("\n3. Testing AzureOpenAIEnricher.summarize_features:")
        result_dict = azure_enricher.summarize_features(crate_dict)
        print(f"   Dict features: {result_dict[:100]}...")
        
        result_list = azure_enricher.summarize_features(crate_list)
        print(f"   List features: {result_list[:100]}...")
        
        result_empty = azure_enricher.summarize_features(crate_empty)
        print(f"   Empty features: {result_empty[:100]}...")
        
        print("\n✅ AzureOpenAIEnricher tests passed!")
        
    except Exception as e:
        print(f"\n❌ AzureOpenAIEnricher test failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n🎉 All feature handling tests completed!")

if __name__ == "__main__":
    test_feature_handling() 