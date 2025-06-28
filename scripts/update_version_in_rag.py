#!/usr/bin/env python3
"""
Update version information in the RAG cache for version 1.3.1
"""

import sqlite3
import json
from datetime import datetime, timezone

def update_rag_version_info():
    """Update version information in the RAG cache"""
    db_path = "sigil_rag_cache.db"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Update environment metadata with new version
        version_info = {
            "version": "1.3.1",
            "release_date": datetime.now(timezone.utc).isoformat(),
            "release_type": "patch",
            "changes": [
                "Fixed Python 3.9 compatibility for type annotations",
                "Resolved IDE linter errors in core modules",
                "Updated dict[str, Any] to dict[str, Any] format",
                "Fixed Union type expressions in conditional imports",
                "Improved code quality and maintainability"
            ],
            "files_modified": [
                "rust_crate_pipeline/version.py",
                "setup.py", 
                "pyproject.toml",
                "rust_crate_pipeline/network.py",
                "rust_crate_pipeline/pipeline.py",
                "rust_crate_pipeline/production_config.py"
            ]
        }
        
        # Insert version update into environment metadata
        cursor.execute("""
            INSERT INTO environment_metadata (label, os_name, os_version, system_type, processor, bios_version, enforcement_rank, timestamp, commit_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "version_1.3.1",
            "Version Update",
            "1.3.1",
            "Type Annotation Fixes",
            json.dumps(version_info),
            "Patch Release",
            10,
            datetime.now(timezone.utc).isoformat(),
            "version_1.3.1_update"
        ))
        
        # Update project context with version info
        cursor.execute("""
            INSERT INTO project_context (context_type, content, metadata, timestamp)
            VALUES (?, ?, ?, ?)
        """, (
            "version_update",
            f"Updated to version 1.3.1 - Type annotation compatibility fixes",
            json.dumps(version_info),
            datetime.now(timezone.utc).isoformat()
        ))
        
        conn.commit()
        print("✅ Successfully updated RAG cache with version 1.3.1 information")
        
    except Exception as e:
        print(f"❌ Error updating RAG cache: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    update_rag_version_info() 