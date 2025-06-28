#!/usr/bin/env python3
"""
Update version information in the RAG cache for version 1.4.0
"""

import sqlite3
import json
from datetime import datetime, timezone
import os

def update_rag_version_info():
    """Update version information in the RAG cache"""
    db_path = "sigil_rag_cache.db"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Update environment metadata with new version
        version_info = {
            "version": "1.4.0",
            "release_date": datetime.now(timezone.utc).isoformat(),
            "release_type": "minor",
            "changes": [
                "Robust Ed25519 and RSA cryptographic signing for RAG database",
                "Automated provenance and signature validation workflows",
                "GitHub Actions for signature/hash validation and RAG auto-update",
                "Docker image and compose updates for new version",
                "Signature validation for Ed25519 keys in both scripts and CI",
                "Public key tracking in git, private key protection",
                "Workflow reliability for PyPI and Docker builds"
            ],
            "files_modified": [
                "rust_crate_pipeline/version.py",
                "setup.py", 
                "pyproject.toml",
                "docker-compose.yml",
                "scripts/update_rag_codebase_state.py",
                "scripts/validate_signature.py"
            ]
        }
        
        # Insert version update into environment metadata
        cursor.execute("""
            INSERT INTO environment_metadata (label, os_name, os_version, system_type, processor, bios_version, enforcement_rank, timestamp, commit_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "version_1.4.0",
            "Version Update",
            "1.4.0",
            "Security & Provenance",
            json.dumps(version_info),
            "Minor Release",
            10,
            datetime.now(timezone.utc).isoformat(),
            "version_1.4.0_update"
        ))
        
        # Update project context with version info
        cursor.execute("""
            INSERT INTO project_context (project_name, project_path, description, tech_stack, dependencies, configuration, last_updated, active, tags, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "rust_crate_pipeline_v1.4.0",
            os.getcwd(),
            f"Updated to version 1.4.0 - Security, provenance, and workflow improvements",
            json.dumps(["python", "rust", "sqlite", "llm", "rag", "security", "provenance"]),
            json.dumps({}),
            json.dumps(version_info),
            datetime.now(timezone.utc).isoformat(),
            True,
            "version_update,security,provenance,1.4.0",
            datetime.now(timezone.utc).isoformat()
        ))
        
        conn.commit()
        print("✅ Successfully updated RAG cache with version 1.4.0 information")
        
    except Exception as e:
        print(f"❌ Error updating RAG cache: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    update_rag_version_info() 