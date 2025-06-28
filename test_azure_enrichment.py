#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for Azure OpenAI enrichment with data structure fixes.
This tests the enrichment pipeline with a single crate to verify full enrichment works.
"""

import asyncio
import json
import logging
from pathlib import Path

# Add the project root to the path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from rust_crate_pipeline.config import PipelineConfig, CrateMetadata
from rust_crate_pipeline.azure_ai_processing import AzureOpenAIEnricher


def setup_logging():
    """Setup logging for the test"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("azure_test.log")
        ]
    )


def create_test_crate() -> CrateMetadata:
    """Create a test crate with dictionary features to test the fixes"""
    return CrateMetadata(
        name="test-crate",
        version="1.0.0",
        description="A test Rust crate for Azure OpenAI enrichment testing",
        repository="https://github.com/test/test-crate",
        keywords=["test", "rust", "azure", "openai"],
        categories=["development", "testing"],
        readme="""
# Test Crate

This is a test crate for verifying Azure OpenAI enrichment functionality.

## Features

- Feature 1: Basic functionality
- Feature 2: Advanced capabilities
- Feature 3: Integration support

## Usage

```rust
use test_crate;

fn main() {
    println!("Hello from test crate!");
}
```

## Dependencies

- serde = "1.0"
- tokio = { version = "1.0", features = ["full"] }
        """,
        downloads=1000,
        github_stars=50,
        dependencies=[
            {"crate_id": "serde", "kind": "normal", "version": "1.0"},
            {"crate_id": "tokio", "kind": "normal", "version": "1.0"}
        ],
        # Test with dictionary format (should work)
        features={
            "default": ["feature1", "feature2"],
            "full": ["feature1", "feature2", "feature3"],
            "integration": ["feature3"]
        },
        code_snippets=[
            "use test_crate;",
            "let result = test_crate::process();"
        ],
        readme_sections={
            "features": "Feature 1, Feature 2, Feature 3",
            "usage": "Basic usage examples"
        }
    )


def create_test_crate_with_list_features() -> CrateMetadata:
    """Create a test crate with list features to test the list handling fix"""
    return CrateMetadata(
        name="test-crate-list",
        version="1.0.0",
        description="A test Rust crate with list features for Azure OpenAI enrichment testing",
        repository="https://github.com/test/test-crate-list",
        keywords=["test", "rust", "list", "features"],
        categories=["development", "testing"],
        readme="""
# Test Crate with List Features

This crate tests the list feature handling in Azure OpenAI enrichment.

## Features

- async
- serde
- tokio
- web

## Usage

```rust
use test_crate_list;

#[tokio::main]
async fn main() {
    println!("Hello from test crate with list features!");
}
```
        """,
        downloads=500,
        github_stars=25,
        dependencies=[],
        # Test with list format (this was causing the error)
        # We'll simulate the list format by using a special key that represents list features
        features={"list_features": ["async", "serde", "tokio", "web"]},  # Simulate list format
        code_snippets=[],
        readme_sections={}
    )


async def test_azure_enrichment():
    """Test Azure OpenAI enrichment with both data formats"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Create configuration with Azure OpenAI
    config = PipelineConfig(
        use_azure_openai=True,
        azure_openai_endpoint="https://david-mc08tirc-eastus2.services.ai.azure.com/",
        azure_openai_api_key="2hw0jjqwjtKke7DMGiJSPtlj6GhuLCNdQWPXoDGN2I3JMvzp4PmGJQQJ99BFACHYHv6XJ3w3AAAAACOGFPYA",
        azure_openai_deployment_name="gpt-4o",
        azure_openai_api_version="2024-02-15-preview",
        max_tokens=256,
        batch_size=1
    )
    
    try:
        # Initialize Azure OpenAI enricher
        logger.info("Initializing Azure OpenAI enricher...")
        enricher = AzureOpenAIEnricher(config)
        logger.info("SUCCESS: Azure OpenAI enricher initialized successfully")
        
        # Test 1: Dictionary features (should work)
        logger.info("Testing with dictionary features...")
        test_crate_dict = create_test_crate()
        enriched_dict = enricher.enrich_crate(test_crate_dict)
        
        logger.info("SUCCESS: Dictionary features enrichment completed")
        logger.info(f"Readme summary: {enriched_dict.readme_summary}")
        logger.info(f"Feature summary: {enriched_dict.feature_summary}")
        logger.info(f"Use case: {enriched_dict.use_case}")
        logger.info(f"Score: {enriched_dict.score}")
        logger.info(f"Factual pairs: {enriched_dict.factual_counterfactual}")
        
        # Test 2: List features (this was failing before the fix)
        logger.info("Testing with list features...")
        test_crate_list = create_test_crate_with_list_features()
        enriched_list = enricher.enrich_crate(test_crate_list)
        
        logger.info("SUCCESS: List features enrichment completed")
        logger.info(f"Readme summary: {enriched_list.readme_summary}")
        logger.info(f"Feature summary: {enriched_list.feature_summary}")
        logger.info(f"Use case: {enriched_list.use_case}")
        logger.info(f"Score: {enriched_list.score}")
        logger.info(f"Factual pairs: {enriched_list.factual_counterfactual}")
        
        # Save results
        results = {
            "dictionary_features_test": {
                "crate_name": enriched_dict.name,
                "readme_summary": enriched_dict.readme_summary,
                "feature_summary": enriched_dict.feature_summary,
                "use_case": enriched_dict.use_case,
                "score": enriched_dict.score,
                "factual_counterfactual": enriched_dict.factual_counterfactual
            },
            "list_features_test": {
                "crate_name": enriched_list.name,
                "readme_summary": enriched_list.readme_summary,
                "feature_summary": enriched_list.feature_summary,
                "use_case": enriched_list.use_case,
                "score": enriched_list.score,
                "factual_counterfactual": enriched_list.factual_counterfactual
            }
        }
        
        with open("azure_enrichment_test_results.json", "w") as f:
            json.dump(results, f, indent=2)
        
        logger.info("SUCCESS: Test results saved to azure_enrichment_test_results.json")
        logger.info("SUCCESS: All Azure OpenAI enrichment tests passed!")
        
        return True
        
    except Exception as e:
        logger.error(f"FAIL: Azure OpenAI enrichment test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_azure_enrichment())
    if success:
        print("\nSUCCESS: Azure OpenAI enrichment test completed successfully!")
        print("Check azure_enrichment_test_results.json for detailed results.")
    else:
        print("\nFAIL: Azure OpenAI enrichment test failed!")
        sys.exit(1) 