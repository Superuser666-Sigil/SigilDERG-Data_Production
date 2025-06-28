from typing import Dict, List, Tuple, Optional, Any
#!/usr/bin/env python3
"""
Agent RAG Demo

This script demonstrates how an agent can use the local RAG system to access
hardware data, code index, and documentation without external dependencies.
"""

import os
import sys
import json
from pathlib import Path

# Add the parent directory to the path to import utils
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.local_rag_manager import LocalRAGManager


class AgentRAGInterface:
    """Interface for agents to interact with local RAG system"""

    def __init__(self, db_path: str = "sigil_rag_cache.db") -> None:
        self.rag_manager = LocalRAGManager(db_path)

    def get_system_info(self) -> dict:
        """Get comprehensive system information"""
        profile = self.rag_manager.get_hardware_profile("current")
        if not profile:
            # If no profile exists, create one
            profile = self.rag_manager.store_hardware_profile("current")

        return {
            "hardware": {
                "cpu": {
                    "model": profile.get("cpu_model", "Unknown"),
                    "cores": profile.get("cpu_cores", 0),
                    "threads": profile.get("cpu_threads", 0),
                },
                "memory": {"total_gb": profile.get("ram_total_gb", 0)},
                "storage": {
                    "type": profile.get("storage_type", "Unknown"),
                    "capacity_gb": profile.get("storage_capacity_gb", 0),
                },
                "gpu": {
                    "model": profile.get("gpu_model", "Unknown"),
                    "vram_gb": profile.get("gpu_vram_gb", 0),
                },
            },
            "software": {
                "os": {
                    "platform": profile.get("os_platform", "Unknown"),
                    "version": profile.get("os_version", "Unknown"),
                },
                "python": profile.get("python_version", "Unknown"),
            },
            "models": self._parse_models(profile.get("available_models", "[]")),
        }

    def search_code(self, query: str, limit: int = 5) -> list:
        """Search for code-related information"""
        results = self.rag_manager.search_knowledge(query, limit)
        return [r for r in results if r["source"] == "code"]

    def search_documentation(self, query: str, limit: int = 5) -> list:
        """Search for documentation"""
        results = self.rag_manager.search_knowledge(query, limit)
        return [r for r in results if r["source"] == "documentation"]

    def get_file_info(self, file_path: str) -> dict:
        """Get information about a specific file"""
        # This would need to be implemented in the RAG manager
        # For now, return basic file info
        path = Path(file_path)
        if path.exists():
            return {
                "exists": True,
                "size_bytes": path.stat().st_size,
                "modified": path.stat().st_mtime,
                "extension": path.suffix,
            }
        return {"exists": False}

    def get_project_context(self) -> dict:
        """Get current project context"""
        current_dir = os.getcwd()
        return self.rag_manager.get_project_context(current_dir)

    def cache_external_doc(
        self, title: str, content: str, doc_type: str = "external"
    ) -> bool:
        """Cache external documentation for future use"""
        return self.rag_manager.cache_documentation(
            doc_type=doc_type, title=title, content=content, tags="external,cached"
        )

    def _parse_models(self, models_json: str) -> list:
        """Parse available models from JSON"""
        try:
            models = json.loads(models_json)
            return [os.path.basename(model) for model in models]
        except (json.JSONDecodeError, ValueError, TypeError):
            return []

    def close(self) -> None:
        """Close the RAG manager"""
        self.rag_manager.close()


def demo_agent_usage() -> None:
    """Demonstrate agent usage of the RAG system"""
    print("🤖 Agent RAG System Demo")
    print("=" * 50)

    # Initialize agent interface
    agent_rag = AgentRAGInterface()

    try:
        # Demo 1: Get system information
        print("\n📊 Demo 1: System Information")
        system_info = agent_rag.get_system_info()
        print(f"CPU: {system_info['hardware']['cpu']['model']}")
        print(
            f"Cores: {system_info['hardware']['cpu']['cores']} physical, "
            f"{system_info['hardware']['cpu']['threads']} logical"
        )
        print(f"RAM: {system_info['hardware']['memory']['total_gb']:.1f} GB")
        print(
            f"OS: {system_info['software']['os']['platform']} "
            f"{system_info['software']['os']['version']}"
        )
        print(f"Python: {system_info['software']['python']}")
        print(f"Available Models: {len(system_info['models'])}")

        # Demo 2: Search for code
        print("\n🔍 Demo 2: Code Search")
        pipeline_code = agent_rag.search_code("pipeline", limit=3)
        print(f"Found {len(pipeline_code)} code results for 'pipeline':")
        for i, result in enumerate(pipeline_code, 1):
            print(
                f"  {i}. {result['title']} (relevance: {result['relevance_score']:.2f})"
            )

        # Demo 3: Search for documentation
        print("\n📚 Demo 3: Documentation Search")
        docs_results = agent_rag.search_documentation("rust", limit=3)
        print(f"Found {len(docs_results)} documentation results for 'rust':")
        for i, result in enumerate(docs_results, 1):
            print(
                f"  {i}. {result['title']} (relevance: {result['relevance_score']:.2f})"
            )

        # Demo 4: Get file information
        print("\n📁 Demo 4: File Information")
        main_py_info = agent_rag.get_file_info("rust_crate_pipeline/main.py")
        if main_py_info["exists"]:
            print(f"main.py exists: {main_py_info['size_bytes']} bytes")
        else:
            print("main.py not found")

        # Demo 5: Cache external documentation
        print("\n💾 Demo 5: Caching External Documentation")
        external_doc = """
        # Rust Crate Analysis Guide

        This guide explains how to analyze Rust crates for:
        - Dependencies and their versions
        - Performance characteristics
        - Code quality metrics

        ## Key Metrics
        - Download count
        - Documentation quality
        - Test coverage
        - Security vulnerabilities
        """

        success = agent_rag.cache_external_doc(
            "Rust Crate Analysis Guide", external_doc, "guide"
        )
        print(f"External documentation cached: {'✅' if success else '❌'}")

        # Demo 6: Search for cached content
        print("\n🔍 Demo 6: Search Cached Content")
        cached_results = agent_rag.search_documentation("analysis", limit=2)
        print(f"Found {len(cached_results)} results for 'analysis':")
        for i, result in enumerate(cached_results, 1):
            print(f"  {i}. {result['title']}")

        print("\n✅ Agent RAG Demo Complete!")

    except Exception as e:
        print(f"❌ Demo failed: {e}")

    finally:
        agent_rag.close()


def agent_decision_example() -> None:
    """Example of how an agent might use RAG for decision making"""
    print("\n🧠 Agent Decision Making Example")
    print("=" * 40)

    agent_rag = AgentRAGInterface()

    try:
        # Scenario: Agent needs to decide on optimal batch size for processing
        system_info = agent_rag.get_system_info()

        # Get hardware capabilities
        cpu_cores = system_info["hardware"]["cpu"]["cores"]
        ram_gb = system_info["hardware"]["memory"]["total_gb"]

        # Search for batch processing patterns
        batch_results = agent_rag.search_code("batch", limit=3)

        print("System Analysis:")
        print(f"  CPU Cores: {cpu_cores}")
        print(f"  RAM: {ram_gb:.1f} GB")
        print(f"  Found {len(batch_results)} batch-related code patterns")

        # Decision logic based on hardware and code patterns
        if cpu_cores >= 8 and ram_gb >= 16:
            recommended_batch_size = 20
            reasoning = "High-end system with 8+ cores and 16+ GB RAM"
        elif cpu_cores >= 4 and ram_gb >= 8:
            recommended_batch_size = 10
            reasoning = "Mid-range system with 4+ cores and 8+ GB RAM"
        else:
            recommended_batch_size = 5
            reasoning = "Lower-end system, conservative batch size"

        print("\nAgent Decision:")
        print(f"  Recommended Batch Size: {recommended_batch_size}")
        print(f"  Reasoning: {reasoning}")

        # Cache the decision for future reference
        decision_doc = f"""
        # Batch Processing Decision

        System: {cpu_cores} cores, {ram_gb:.1f} GB RAM
        Recommended batch size: {recommended_batch_size}
        Reasoning: {reasoning}
        """

        agent_rag.cache_external_doc(
            "Batch Processing Decision", decision_doc, "decision"
        )

        print("  Decision cached for future reference")

    except Exception as e:
        print(f"❌ Decision example failed: {e}")

    finally:
        agent_rag.close()


if __name__ == "__main__":
    demo_agent_usage()
