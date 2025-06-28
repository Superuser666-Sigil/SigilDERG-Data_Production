#!/usr/bin/env python3
"""
Populate All RAG Tables

Master script to populate all empty RAG cache tables with appropriate data.
This script runs all the individual population scripts in the correct order.
"""

import subprocess
import sys
import os
from datetime import datetime

def run_script(script_name: str) -> bool:
    """Run a population script and return success status"""
    script_path = os.path.join("scripts", script_name)
    
    if not os.path.exists(script_path):
        print(f"Script not found: {script_path}")
        return False
    
    print(f"\nRunning {script_name}...")
    print("=" * 50)
    
    try:
        result = subprocess.run([sys.executable, script_path], 
                              capture_output=True, text=True, check=True)
        print(result.stdout)
        if result.stderr:
            print(f"Warnings: {result.stderr}")
        print(f"{script_name} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"{script_name} failed:")
        print(f"   Error: {e.stderr}")
        return False

def main():
    """Run all population scripts in order"""
    print("Starting RAG cache table population...")
    print(f"Started at: {datetime.now().isoformat()}")
    print("=" * 60)
    
    # Define scripts to run in order
    scripts = [
        "populate_rule_zero_policies.py",
        "populate_code_changes.py", 
        "populate_architectural_patterns.py",
        "populate_project_context.py",
        "populate_agent_sessions.py"
    ]
    
    success_count = 0
    failed_scripts = []
    
    for script in scripts:
        if run_script(script):
            success_count += 1
        else:
            failed_scripts.append(script)
    
    # Summary
    print("\n" + "=" * 60)
    print("POPULATION SUMMARY")
    print("=" * 60)
    print(f"Successful: {success_count}/{len(scripts)}")
    print(f"Failed: {len(failed_scripts)}")
    
    if failed_scripts:
        print(f"\nFailed scripts:")
        for script in failed_scripts:
            print(f"   - {script}")
    
    if success_count == len(scripts):
        print("\nAll RAG tables populated successfully!")
        print("\nTables populated:")
        print("   • rule_zero_policies - Rule Zero compliance policies")
        print("   • code_changes - Git history and code evolution")
        print("   • architectural_patterns - System design patterns")
        print("   • project_context - Current project state and metadata")
        print("   • agent_sessions - AI assistant session data")
        
        print("\nYou can now scan the RAG database to see the populated data:")
        print("   python scripts/scan_rag_db.py")
    else:
        print(f"\n{len(failed_scripts)} scripts failed. Check the errors above.")
    
    print(f"\nCompleted at: {datetime.now().isoformat()}")

if __name__ == "__main__":
    main() 