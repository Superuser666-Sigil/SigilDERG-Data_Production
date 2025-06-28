from __future__ import annotations
#!/usr/bin/env python3
"""Quick test to verify the balanced crate dataset works correctly."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_balanced_crates() -> None:
    """Test the balanced crate dataset without loading the model."""
    try:
        from rust_crate_pipeline.config import PipelineConfig
        from rust_crate_pipeline.pipeline import CrateDataPipeline

        # Use a real PipelineConfig for type safety
        config = PipelineConfig(n_workers=4, batch_size=10)
        pipeline = CrateDataPipeline.__new__(CrateDataPipeline)
        pipeline.config = config

        crates = pipeline.get_crate_list()  # Fixed: Use public method

        print("BALANCED DATASET TEST RESULTS:")
        print(f"   Total crates: {len(crates)}")

        unique_crates = set(crates)
        duplicates = [c for c in unique_crates if crates.count(c) > 1]
        assert len(unique_crates) == len(crates), f"Duplicates found: {duplicates}"
        print("   No duplicates found")

        ml_ai_start = crates.index("tokenizers") if "tokenizers" in crates else -1
        assert ml_ai_start != -1, "ML/AI section not found"
        ml_crates = crates[ml_ai_start:]
        ml_percentage = (len(ml_crates) / len(crates)) * 100
        print(f"   ML/AI crates: {len(ml_crates)} ({ml_percentage:.1f}%)")
        other_crates_count = len(crates) - len(ml_crates)
        other_percentage = 100 - ml_percentage
        print(f"   Other crates: {other_crates_count} ({other_percentage:.1f}%)")
        assert ml_percentage < 20, "Dataset still unbalanced"
        print("   Dataset successfully balanced!")
    except ImportError as e:
        print(f"   Required module missing: {e}")
        assert False, f"Required module missing: {e}"
    except FileNotFoundError as e:
        print(f"   Required file missing: {e}")
        assert False, f"Required file missing: {e}"
    except Exception as e:
        print(f"   Test failed: {str(e)}")
        assert False, f"Unexpected error: {e}"


if __name__ == "__main__":
    success = test_balanced_crates()
    print(f"\nBUILD & TEST: {'SUCCESS' if success else 'FAILED'}")
    deployment_msg = "Version 1.3.6 ready for deployment!"
    issue_msg = "Issues need to be resolved"
    print(deployment_msg if success else issue_msg)
    sys.exit(0 if success else 1)
