#!/usr/bin/env python3
"""
Update RAG Database with Current Codebase State and Sign with Keypairs

This script:
1. Updates the RAG database with current codebase information
2. Adds missing provenance table for signatures
3. Signs the database with the existing private key
4. Updates all relevant metadata
"""

import sqlite3
import json
import hashlib
import os
import subprocess
import platform
import psutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.exceptions import InvalidSignature

# Configuration
DB_PATH = "sigil_rag_cache.db"
PRIVATE_KEY_PATH = "scripts/sigil_seal_private.pem"
PUBLIC_KEY_PATH = "scripts/sigil_seal_public.pem"
HASH_FILE = "sigil_rag_cache.hash"

class RAGCodebaseUpdater:
    """Comprehensive RAG database updater with signature functionality"""
    
    def __init__(self):
        self.db_path = DB_PATH
        self.private_key_path = PRIVATE_KEY_PATH
        self.public_key_path = PUBLIC_KEY_PATH
        self.hash_file = HASH_FILE
        
    def add_provenance_table(self) -> bool:
        """Add provenance table to database if it doesn't exist"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if provenance table exists
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='provenance'
            """)
            
            if not cursor.fetchone():
                # Create provenance table
                cursor.execute("""
                    CREATE TABLE provenance (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        db_hash TEXT NOT NULL,
                        signature BLOB NOT NULL,
                        signed_by TEXT NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        metadata TEXT -- JSON metadata about the signing
                    )
                """)
                conn.commit()
                print("Created provenance table")
            else:
                print("Provenance table already exists")
            
            conn.close()
            return True
            
        except Exception as e:
            print(f"Error adding provenance table: {e}")
            return False
    
    def get_current_codebase_state(self) -> Dict[str, Any]:
        """Get comprehensive current codebase state"""
        state = {
            "version": "1.4.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "platform": {
                "os": platform.system(),
                "os_version": platform.version(),
                "python_version": platform.python_version(),
                "architecture": platform.machine()
            },
            "hardware": {
                "cpu_cores": psutil.cpu_count(),
                "cpu_threads": psutil.cpu_count(logical=True),
                "ram_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
                "ram_available_gb": round(psutil.virtual_memory().available / (1024**3), 2)
            },
            "codebase": {
                "total_files": 0,
                "python_files": 0,
                "rust_files": 0,
                "test_files": 0,
                "documentation_files": 0,
                "configuration_files": 0
            },
            "dependencies": {},
            "recent_changes": [],
            "test_coverage": {},
            "llm_providers": {
                "azure_openai": True,
                "local_llama": False,
                "ollama": False,
                "lm_studio": False
            }
        }
        
        # Count files by type
        for root, dirs, files in os.walk("."):
            # Skip hidden directories and common exclusions
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'node_modules', '.git']]
            
            for file in files:
                file_path = os.path.join(root, file)
                state["codebase"]["total_files"] += 1
                
                if file.endswith('.py'):
                    state["codebase"]["python_files"] += 1
                elif file.endswith('.rs'):
                    state["codebase"]["rust_files"] += 1
                elif file.startswith('test_') or file.endswith('_test.py'):
                    state["codebase"]["test_files"] += 1
                elif file.endswith(('.md', '.txt', '.rst')):
                    state["codebase"]["documentation_files"] += 1
                elif file.endswith(('.toml', '.yaml', '.yml', '.json', '.ini', '.cfg')):
                    state["codebase"]["configuration_files"] += 1
        
        # Get dependencies
        if os.path.exists('requirements.txt'):
            with open('requirements.txt', 'r') as f:
                state["dependencies"]["requirements"] = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
        if os.path.exists('pyproject.toml'):
            state["dependencies"]["pyproject"] = "present"
        
        # Get recent git changes
        try:
            result = subprocess.run(
                ['git', 'log', '--oneline', '-10'],
                capture_output=True, text=True, cwd='.'
            )
            if result.returncode == 0:
                state["recent_changes"] = result.stdout.strip().split('\n')
        except:
            pass
        
        # Get test coverage if available
        if os.path.exists('.coverage'):
            state["test_coverage"]["coverage_file"] = "present"
        
        return state
    
    def update_hardware_profile(self, state: Dict[str, Any]) -> bool:
        """Update hardware profile in RAG database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Ensure hardware_profiles table exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hardware_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_name TEXT NOT NULL,
                    cpu_model TEXT,
                    cpu_cores INTEGER,
                    cpu_threads INTEGER,
                    ram_total_gb REAL,
                    gpu_model TEXT,
                    gpu_vram_gb INTEGER,
                    storage_type TEXT,
                    storage_capacity_gb REAL,
                    network_speed_mbps INTEGER,
                    os_platform TEXT,
                    os_version TEXT,
                    python_version TEXT,
                    available_models TEXT,
                    performance_benchmarks TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Insert/update current hardware profile
            cursor.execute("""
                INSERT OR REPLACE INTO hardware_profiles 
                (profile_name, cpu_model, cpu_cores, cpu_threads, ram_total_gb,
                 os_platform, os_version, python_version, available_models, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "dev_machine_current",
                platform.processor(),
                state["hardware"]["cpu_cores"],
                state["hardware"]["cpu_threads"],
                state["hardware"]["ram_total_gb"],
                state["platform"]["os"],
                state["platform"]["os_version"],
                state["platform"]["python_version"],
                json.dumps(state["llm_providers"]),
                datetime.now(timezone.utc).isoformat()
            ))
            
            conn.commit()
            conn.close()
            print("Updated hardware profile")
            return True
            
        except Exception as e:
            print(f"Error updating hardware profile: {e}")
            return False
    
    def update_project_context(self, state: Dict[str, Any]) -> bool:
        """Update project context in RAG database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Ensure project_context table exists with correct schema
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS project_context (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_name TEXT NOT NULL,
                    project_path TEXT NOT NULL,
                    description TEXT,
                    tech_stack TEXT,
                    dependencies TEXT,
                    configuration TEXT,
                    environment_vars TEXT,
                    build_commands TEXT,
                    test_commands TEXT,
                    deployment_info TEXT,
                    last_updated DATETIME,
                    active BOOLEAN DEFAULT TRUE,
                    tags TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Insert current codebase state
            cursor.execute("""
                INSERT INTO project_context 
                (project_name, project_path, description, tech_stack, dependencies, 
                 configuration, last_updated, active, tags, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "rust_crate_pipeline",
                os.getcwd(),
                f"Updated codebase state for version {state['version']}",
                json.dumps(["python", "rust", "sqlite", "llm", "rag"]),
                json.dumps(state["dependencies"]),
                json.dumps(state),
                datetime.now(timezone.utc).isoformat(),
                True,
                "codebase_update,version_1.3.6",
                datetime.now(timezone.utc).isoformat()
            ))
            
            conn.commit()
            conn.close()
            print("Updated project context")
            return True
            
        except Exception as e:
            print(f"Error updating project context: {e}")
            return False
    
    def compute_db_hash(self) -> str:
        """Compute SHA256 hash of database file"""
        BUF_SIZE = 65536
        sha256 = hashlib.sha256()
        with open(self.db_path, "rb") as f:
            while True:
                data = f.read(BUF_SIZE)
                if not data:
                    break
                sha256.update(data)
        return sha256.hexdigest()
    
    def sign_and_store_provenance(self) -> bool:
        """Sign the finalized database and store provenance entry. Ensures hash is computed after all other DB updates."""
        try:
            # Compute database hash after all updates
            db_hash = self.compute_db_hash()

            # Load private key
            with open(self.private_key_path, "rb") as f:
                private_key = serialization.load_pem_private_key(f.read(), password=None)
            key_type = type(private_key).__name__

            # Sign the hash
            if key_type.startswith('Ed25519'):
                signature = private_key.sign(db_hash.encode())
                signing_method = "Ed25519"
            elif key_type.startswith('RSAPrivateKey') or hasattr(private_key, 'private_numbers'):
                signature = private_key.sign(
                    db_hash.encode(),
                    padding.PKCS1v15(),
                    hashes.SHA256()
                )
                signing_method = "RSA-SHA256"
            else:
                raise ValueError(f"Unsupported private key type for signing: {key_type}")

            # Store signature in provenance table (clear old entries first)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM provenance")
            metadata = {
                "version": "1.3.6",
                "signing_method": signing_method,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            cursor.execute("""
                INSERT INTO provenance 
                (db_hash, signature, signed_by, metadata, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (
                db_hash,
                signature,
                "sigil_seal_private_key",
                json.dumps(metadata),
                datetime.now(timezone.utc).isoformat()
            ))
            conn.commit()
            conn.close()

            # Update hash file
            with open(self.hash_file, "w") as f:
                f.write(db_hash + "\n")

            print(f"Database signed and provenance stored. Hash: {db_hash}")
            return True
        except Exception as e:
            print(f"Error signing database: {e}")
            return False

    def verify_signature(self) -> bool:
        """Verify the database signature (supports RSA and Ed25519) using the hash at signing time."""
        try:
            # Load public key
            with open(self.public_key_path, "rb") as f:
                public_key = serialization.load_pem_public_key(f.read())

            # Get signature and hash from provenance
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT db_hash, signature FROM provenance ORDER BY timestamp DESC LIMIT 1")
            row = cursor.fetchone()
            conn.close()

            if not row:
                print("No signature found in provenance table")
                return False

            db_hash, signature = row
            key_type = type(public_key).__name__

            if key_type.startswith('Ed25519'):
                public_key.verify(signature, db_hash.encode())
            elif key_type.startswith('RSAPublicKey') or hasattr(public_key, 'public_numbers'):
                public_key.verify(
                    signature,
                    db_hash.encode(),
                    padding.PKCS1v15(),
                    hashes.SHA256()
                )
            else:
                raise ValueError(f"Unsupported public key type for verification: {key_type}")

            print("Signature verification successful")
            return True

        except InvalidSignature:
            print("Signature verification failed")
            return False
        except Exception as e:
            print(f"Error verifying signature: {e}")
            return False
    
    def update_all(self) -> bool:
        """Perform complete RAG database update and signing"""
        print("Starting comprehensive RAG database update...")
        
        # Step 1: Add provenance table
        if not self.add_provenance_table():
            return False
        
        # Step 2: Get current codebase state
        state = self.get_current_codebase_state()
        print(f"Current codebase state: {state['version']} with {state['codebase']['total_files']} files")
        
        # Step 3: Update hardware profile
        if not self.update_hardware_profile(state):
            return False
        
        # Step 4: Update project context
        if not self.update_project_context(state):
            return False
        
        # Step 5: Sign and store provenance
        if not self.sign_and_store_provenance():
            return False
        
        # Step 6: Verify signature
        if not self.verify_signature():
            return False
        
        print("✅ RAG database update and signing completed successfully")
        return True

def main():
    """Main function"""
    updater = RAGCodebaseUpdater()
    
    if updater.update_all():
        print("\n🎉 RAG database successfully updated and signed!")
        print(f"Database: {DB_PATH}")
        print(f"Hash file: {HASH_FILE}")
        print(f"Public key: {PUBLIC_KEY_PATH}")
        print(f"Private key: {PRIVATE_KEY_PATH}")
    else:
        print("\n❌ RAG database update failed")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main()) 