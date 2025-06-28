from typing import Dict, List, Tuple, Optional, Any
#!/usr/bin/env python3
"""Final verification of the balanced crate list"""

# Quick check without duplicate
from rust_crate_pipeline.pipeline import CrateDataPipeline


class MockConfig:
    def __init__(self) -> None:
        self.n_workers = 4
        self.batch_size = 10


# Mock the LLMEnricher to avoid model loading

# Temporarily replace the enricher init
original_init = None


def mock_init(self, config) -> None:
    self.config = config
    # Don't load model


# Patch the LLMEnricher temporarily
try:
    from rust_crate_pipeline.ai_processing import LLMEnricher

    original_init = LLMEnricher.__init__
    LLMEnricher.__init__ = mock_init

    config = MockConfig()
    pipeline = CrateDataPipeline.__new__(CrateDataPipeline)
    pipeline.config = config
    crates = pipeline.get_crate_list()

    print("✅ FINAL VERIFICATION:")
    print(f"📊 Total crates: {len(crates)}")

    # Check duplicates
    unique_crates = set(crates)
    if len(unique_crates) == len(crates):
        print("✅ No duplicates found!")
    else:
        duplicates = [c for c in unique_crates if crates.count(c) > 1]
        print(f"⚠️  Duplicates: {duplicates}")

    # ML/AI percentage
    ml_start = crates.index("tokenizers") if "tokenizers" in crates else -1
    if ml_start != -1:
        ml_crates = crates[ml_start:]
        ml_percentage = (len(ml_crates) / len(crates)) * 100
        print(f"🎯 ML/AI: {len(ml_crates)} crates ({ml_percentage:.1f}%)")
        print(
            f"🎯 Other: {
                len(crates) -
                len(ml_crates)} crates ({
                100 -
                ml_percentage:.1f}%)"
        )
        print(f"🚀 Balanced dataset ready! {len(crates)} total crates")

finally:
    # Restore original if we had it
    if original_init:
        LLMEnricher.__init__ = original_init
