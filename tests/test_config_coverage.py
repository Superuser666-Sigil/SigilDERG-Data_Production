from typing import Dict, List, Tuple, Optional, Any
#!/usr/bin/env python3
"""
Additional tests for rust_crate_pipeline.config to achieve 100% coverage
"""

from rust_crate_pipeline.config import CrateMetadata


def test_crate_metadata_to_dict() -> None:
    """Test CrateMetadata.to_dict method (line 62 coverage)"""
    metadata = CrateMetadata(
        name="test-crate",
        version="1.3.0",
        description="A test crate",
        repository="https://github.com/test/test-crate",
        keywords=["test", "example"],
        categories=["development-tools"],
        readme="README.md",
        downloads=1000,
    )
    metadata_dict = metadata.to_dict()
    assert isinstance(metadata_dict, dict)
    assert metadata_dict["name"] == "test-crate"
    assert metadata_dict["version"] == "1.3.0"
    assert metadata_dict["description"] == "A test crate"
    assert metadata_dict["repository"] == "https://github.com/test/test-crate"
    assert metadata_dict["keywords"] == ["test", "example"]
    assert metadata_dict["categories"] == ["development-tools"]
    assert metadata_dict["readme"] == "README.md"
    assert metadata_dict["downloads"] == 1000
    assert metadata_dict["source"] == "crates.io"


def test_crate_metadata_to_dict_with_defaults() -> None:
    """Test CrateMetadata.to_dict with default field values"""
    metadata = CrateMetadata(
        name="test-crate",
        version="1.3.0",
        description="A test crate",
        repository="",
        keywords=[],
        categories=[],
        readme="",
        downloads=0,
    )
    metadata_dict = metadata.to_dict()
    assert isinstance(metadata_dict, dict)
    assert metadata_dict["name"] == "test-crate"
    assert metadata_dict["version"] == "1.3.0"
    assert metadata_dict["description"] == "A test crate"
    assert metadata_dict["source"] == "crates.io"  # default value


if __name__ == "__main__":
    # Allow running this test directly
    test_crate_metadata_to_dict()
    test_crate_metadata_to_dict_with_defaults()
    print("✅ All config coverage tests passed!")
