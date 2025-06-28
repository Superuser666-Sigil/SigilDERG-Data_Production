from typing import Dict, List, Tuple, Optional, Any
#!/usr/bin/env python3
"""
Setup Local RAG System

This script demonstrates how to initialize and populate the local RAG system
with hardware data, code index, and documentation for agent use.
"""

import os
import sys
import logging
from pathlib import Path
import json

# Add the parent directory to the path to import utils
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.local_rag_manager import LocalRAGManager


def setup_logging() -> None:
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def main() -> None:
    """Main setup function"""
    setup_logging()
    logger = logging.getLogger(__name__)

    print("🚀 Setting up Local RAG System for Agent Knowledge Base")
    print("=" * 60)

    # Initialize RAG manager
    rag_manager = LocalRAGManager()

    try:
        # Step 1: Store hardware profile
        print("\n📊 Step 1: Storing hardware profile...")
        hardware_profile = rag_manager.store_hardware_profile("current")
        if hardware_profile:
            print("✅ Hardware profile stored:")
            print(f"   CPU: {hardware_profile.get('cpu_model', 'Unknown')}")
            print(f"   Cores: {hardware_profile.get('cpu_cores', 0)}")
            print(f"   RAM: {hardware_profile.get('ram_total_gb', 0):.1f} GB")
            print(f"   OS: {hardware_profile.get('os_platform', 'Unknown')}")
            print(f"   Python: {hardware_profile.get('python_version', 'Unknown')}")
        else:
            print("❌ Failed to store hardware profile")

        # Step 2: Index codebase
        print("\n📁 Step 2: Indexing codebase...")
        current_dir = os.getcwd()
        indexed_count = rag_manager.index_codebase(
            current_dir,
            file_patterns=[
                "*.py",
                "*.rs",
                "*.js",
                "*.ts",
                "*.md",
                "*.txt",
                "*.yml",
                "*.yaml",
            ],
        )
        print(f"✅ Indexed {indexed_count} files")

        # Step 3: Cache some documentation
        print("\n📚 Step 3: Caching documentation...")

        # Cache README
        readme_path = Path("README.md")
        if readme_path.exists():
            readme_content = readme_path.read_text(encoding="utf-8", errors="ignore")
            rag_manager.cache_documentation(
                doc_type="readme",
                title="Project README",
                content=readme_content,
                source_url=str(readme_path),
                package_name="rust-crate-pipeline",
                language="markdown",
                tags="documentation,readme,project",
            )
            print("✅ Cached README.md")

        # Cache requirements
        requirements_files = [
            "requirements.txt",
            "requirements-dev.txt",
            "pyproject.toml",
        ]
        for req_file in requirements_files:
            req_path = Path(req_file)
            if req_path.exists():
                req_content = req_path.read_text(encoding="utf-8", errors="ignore")
                rag_manager.cache_documentation(
                    doc_type="dependencies",
                    title=f"{req_file} - Dependencies",
                    content=req_content,
                    source_url=str(req_path),
                    package_name="rust-crate-pipeline",
                    language="text",
                    tags="dependencies,requirements,setup",
                )
                print(f"✅ Cached {req_file}")

        # Step 4: Demonstrate search capabilities
        print("\n🔍 Step 4: Testing search capabilities...")

        # Search for pipeline-related content
        pipeline_results = rag_manager.search_knowledge("pipeline", limit=5)
        print(f"Found {len(pipeline_results)} results for 'pipeline':")
        for i, result in enumerate(pipeline_results, 1):
            print(f"  {i}. [{result['source']}] {result['title']}")

        # Search for hardware information
        hardware_results = rag_manager.search_knowledge("hardware", limit=3)
        print(f"Found {len(hardware_results)} results for 'hardware':")
        for i, result in enumerate(hardware_results, 1):
            print(f"  {i}. [{result['source']}] {result['title']}")

        # Step 5: Show hardware profile
        print("\n💻 Step 5: Retrieved hardware profile:")
        profile = rag_manager.get_hardware_profile("current")
        if profile:
            print(f"   Profile: {profile.get('profile_name', 'Unknown')}")
            print(f"   CPU: {profile.get('cpu_model', 'Unknown')}")
            print(
                f"   Cores: {profile.get('cpu_cores', 0)} physical, "
                f"{profile.get('cpu_threads', 0)} logical"
            )
            print(f"   RAM: {profile.get('ram_total_gb', 0):.1f} GB")
            print(
                f"   Storage: {profile.get('storage_capacity_gb', 0):.1f} GB "
                f"({profile.get('storage_type', 'Unknown')})"
            )
            print(
                f"   OS: {profile.get('os_platform', 'Unknown')} "
                f"{profile.get('os_version', '')}"
            )
            print(f"   Python: {profile.get('python_version', 'Unknown')}")

            # Show available models
            try:
                models = json.loads(profile.get("available_models", "[]"))
                if models:
                    print(f"   Available Models: {len(models)} found")
                    for model in models[:3]:  # Show first 3
                        print(f"     - {os.path.basename(model)}")
                    if len(models) > 3:
                        print(f"     ... and {len(models) - 3} more")
                else:
                    print("   Available Models: None found")
            except (json.JSONDecodeError, ValueError, TypeError, OSError):
                print("   Available Models: Error parsing")

        print("\n✅ Local RAG System Setup Complete!")
        print("\n🎯 Usage Examples:")
        print("   # Search for code or documentation")
        print("   results = rag_manager.search_knowledge('your query')")
        print("   ")
        print("   # Get hardware information")
        print("   profile = rag_manager.get_hardware_profile()")
        print("   ")
        print("   # Get file change history")
        print("   history = rag_manager.get_file_history('path/to/file.py')")
        print("   ")
        print("   # Cache new documentation")
        print("   rag_manager.cache_documentation('api', 'Title', 'Content')")

    except Exception as e:
        logger.error(f"Setup failed: {e}")
        print(f"❌ Setup failed: {e}")
        return 1

    finally:
        rag_manager.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
