#!/usr/bin/env python3
"""
Additional tests for rust_crate_pipeline.config to achieve 100% coverage
"""

from rust_crate_pipeline.config import CrateMetadata


def test_crate_metadata_to_dict():
    """Test CrateMetadata.to_dict method (line 62 coverage)"""
    metadata = CrateMetadata(
        name="test-crate",
        version="1.0.0", 
        description="A test crate",
        repository="https://github.com/test/crate",
        keywords=["test", "crate"],
        categories=["testing"],
        readme="# Test Crate\nThis is a test.",
        downloads=1000,
        github_stars=50
    )
    
    # Call the to_dict method to cover line 62
    metadata_dict = metadata.to_dict()
    
    # Verify the result is a dictionary with expected keys
    assert isinstance(metadata_dict, dict)
    assert metadata_dict["name"] == "test-crate"
    assert metadata_dict["version"] == "1.0.0"
    assert metadata_dict["description"] == "A test crate"
    assert metadata_dict["repository"] == "https://github.com/test/crate"
    assert metadata_dict["keywords"] == ["test", "crate"]
    assert metadata_dict["categories"] == ["testing"]
    assert metadata_dict["downloads"] == 1000
    assert metadata_dict["github_stars"] == 50


def test_crate_metadata_to_dict_with_defaults():
    """Test CrateMetadata.to_dict with default field values"""
    metadata = CrateMetadata(
        name="minimal-crate",
        version="0.1.0",
        description="Minimal test",
        repository="",
        keywords=[],
        categories=[],
        readme="",
        downloads=0
    )
    
    metadata_dict = metadata.to_dict()
    
    # Check that default values are properly serialized
    assert isinstance(metadata_dict, dict)
    assert metadata_dict["github_stars"] == 0  # default value
    assert metadata_dict["dependencies"] == []  # default factory
    assert metadata_dict["features"] == {}  # default factory
    assert metadata_dict["source"] == "crates.io"  # default value


if __name__ == "__main__":
    # Allow running this test directly
    test_crate_metadata_to_dict()
    test_crate_metadata_to_dict_with_defaults()
    print("✅ All config coverage tests passed!")
