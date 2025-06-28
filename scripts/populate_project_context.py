#!/usr/bin/env python3
"""
Populate Project Context Table

This script populates the project_context table with current project state,
context, and metadata that would be useful for AI assistants and analysis.
"""

import sqlite3
import json
import os
import subprocess
import platform
from datetime import datetime
from typing import Dict, Any, List
from pathlib import Path

def get_git_info() -> Dict[str, Any]:
    """Get current Git repository information"""
    try:
        # Get current branch
        branch = subprocess.run(['git', 'branch', '--show-current'], 
                              capture_output=True, text=True).stdout.strip()
        
        # Get last commit
        last_commit = subprocess.run(['git', 'log', '-1', '--pretty=format:%H|%s|%an|%ad'], 
                                   capture_output=True, text=True).stdout.strip()
        
        # Get remote URL
        remote_url = subprocess.run(['git', 'remote', 'get-url', 'origin'], 
                                  capture_output=True, text=True).stdout.strip()
        
        # Get file count
        file_count = subprocess.run(['git', 'ls-files'], 
                                  capture_output=True, text=True).stdout.count('\n')
        
        return {
            'branch': branch,
            'last_commit': last_commit,
            'remote_url': remote_url,
            'file_count': file_count
        }
    except:
        return {}

def get_project_structure() -> Dict[str, Any]:
    """Analyze project structure and key files"""
    structure = {
        'directories': [],
        'key_files': [],
        'file_types': {},
        'total_files': 0
    }
    
    for root, dirs, files in os.walk('.'):
        # Skip hidden directories and common exclusions
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'node_modules', '.git']]
        
        rel_path = os.path.relpath(root, '.')
        if rel_path != '.':
            structure['directories'].append(rel_path)
        
        for file in files:
            if not file.startswith('.'):
                structure['total_files'] += 1
                ext = os.path.splitext(file)[1]
                structure['file_types'][ext] = structure['file_types'].get(ext, 0) + 1
                
                # Track key files
                if file in ['README.md', 'pyproject.toml', 'requirements.txt', 'Dockerfile', 'docker-compose.yml']:
                    structure['key_files'].append(os.path.join(rel_path, file))
    
    return structure

def get_environment_info() -> Dict[str, Any]:
    """Get current environment information"""
    return {
        'platform': platform.platform(),
        'python_version': platform.python_version(),
        'architecture': platform.architecture()[0],
        'processor': platform.processor(),
        'working_directory': os.getcwd(),
        'environment_variables': {
            'AZURE_OPENAI_ENDPOINT': os.getenv('AZURE_OPENAI_ENDPOINT', 'Not set'),
            'AZURE_OPENAI_API_KEY': 'Set' if os.getenv('AZURE_OPENAI_API_KEY') else 'Not set',
            'OPENAI_API_KEY': 'Set' if os.getenv('OPENAI_API_KEY') else 'Not set',
            'GITHUB_TOKEN': 'Set' if os.getenv('GITHUB_TOKEN') else 'Not set',
            'PYPI_TOKEN': 'Set' if os.getenv('PYPI_TOKEN') else 'Not set'
        }
    }

def get_pipeline_status() -> Dict[str, Any]:
    """Get current pipeline and processing status"""
    status = {
        'output_files': [],
        'processed_crates': 0,
        'database_status': 'Unknown',
        'last_run': None
    }
    
    # Check output directory
    if os.path.exists('output'):
        output_files = [f for f in os.listdir('output') if f.endswith('.json')]
        status['output_files'] = output_files
        status['processed_crates'] = len(output_files)
    
    # Check database
    if os.path.exists('sigil_rag_cache.db'):
        try:
            conn = sqlite3.connect('sigil_rag_cache.db')
            cursor = conn.cursor()
            
            # Check environment metadata
            cursor.execute("SELECT COUNT(*) FROM environment_metadata")
            env_count = cursor.fetchone()[0]
            
            # Check hardware profiles
            cursor.execute("SELECT COUNT(*) FROM hardware_profiles")
            hw_count = cursor.fetchone()[0]
            
            # Check code index
            cursor.execute("SELECT COUNT(*) FROM code_index")
            code_count = cursor.fetchone()[0]
            
            status['database_status'] = f"Active (env: {env_count}, hw: {hw_count}, code: {code_count})"
            conn.close()
        except:
            status['database_status'] = "Error accessing database"
    
    # Check for recent run logs
    log_files = [f for f in os.listdir('.') if f.endswith('.log') or 'audit' in f.lower()]
    if log_files:
        status['last_run'] = max(log_files, key=lambda f: os.path.getmtime(f))
    
    return status

def populate_project_context():
    """Populate the project_context table with current context"""
    
    db_path = "sigil_rag_cache.db"
    
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return
    
    # Get current context data
    git_info = get_git_info()
    project_structure = get_project_structure()
    environment_info = get_environment_info()
    pipeline_status = get_pipeline_status()
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Clear existing context
        cursor.execute("DELETE FROM project_context")
        
        # Insert main project context
        cursor.execute("""
            INSERT INTO project_context 
            (project_name, project_path, description, tech_stack, dependencies, 
             configuration, environment_vars, build_commands, test_commands, 
             deployment_info, last_updated, active, tags, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "SigilDERG-Data_Production",
            os.getcwd(),
            "AI-powered Rust crate analysis pipeline with Rule Zero compliance, multi-provider LLM support, and enhanced web scraping using Crawl4AI",
            json.dumps([
                "Python 3.8+",
                "Crawl4AI",
                "Azure OpenAI",
                "SQLite",
                "Docker",
                "GitHub Actions",
                "Rule Zero Protocol"
            ]),
            json.dumps([
                "requests>=2.28.0",
                "crawl4ai>=0.6.0",
                "llama-cpp-python>=0.2.0",
                "tiktoken>=0.5.0",
                "psutil>=5.9.0",
                "python-dateutil>=2.8.0"
            ]),
            json.dumps({
                "version": "1.3.0",
                "python_version": ">=3.8",
                "production_mode": True,
                "enable_crawl4ai": True,
                "rule_zero_compliance": True
            }),
            json.dumps(environment_info['environment_variables']),
            json.dumps([
                "pip install -e .",
                "pip install -r requirements.txt",
                "pip install -r requirements-dev.txt"
            ]),
            json.dumps([
                "pytest tests/ -v",
                "python scripts/verify_data_accuracy.py",
                "python scripts/validate_signature.py"
            ]),
            json.dumps({
                "docker": "docker-compose up -d",
                "production": "python run_production.py",
                "development": "python -m rust_crate_pipeline --limit 20"
            }),
            datetime.now().isoformat(),
            True,
            json.dumps(["rust", "ai", "pipeline", "analysis", "rule_zero", "production"]),
            datetime.now().isoformat()
        ))
        
        # Add additional context entries for different aspects
        context_entries = [
            {
                "name": "git_repository_state",
                "path": os.getcwd(),
                "description": "Current Git repository state and version control information",
                "tech_stack": json.dumps(["Git", "GitHub"]),
                "dependencies": json.dumps([]),
                "configuration": json.dumps(git_info),
                "environment_vars": json.dumps({}),
                "build_commands": json.dumps([]),
                "test_commands": json.dumps([]),
                "deployment_info": json.dumps({}),
                "tags": json.dumps(["git", "version_control", "repository"])
            },
            {
                "name": "project_structure_analysis",
                "path": os.getcwd(),
                "description": "Project structure analysis and file organization",
                "tech_stack": json.dumps(["Python", "File System"]),
                "dependencies": json.dumps([]),
                "configuration": json.dumps(project_structure),
                "environment_vars": json.dumps({}),
                "build_commands": json.dumps([]),
                "test_commands": json.dumps([]),
                "deployment_info": json.dumps({}),
                "tags": json.dumps(["structure", "files", "organization"])
            },
            {
                "name": "environment_configuration",
                "path": os.getcwd(),
                "description": "Current environment configuration and system information",
                "tech_stack": json.dumps(["Python", "Platform", "OS"]),
                "dependencies": json.dumps([]),
                "configuration": json.dumps(environment_info),
                "environment_vars": json.dumps(environment_info['environment_variables']),
                "build_commands": json.dumps([]),
                "test_commands": json.dumps([]),
                "deployment_info": json.dumps({}),
                "tags": json.dumps(["environment", "configuration", "deployment"])
            },
            {
                "name": "pipeline_operational_status",
                "path": os.getcwd(),
                "description": "Current pipeline operational status and processing metrics",
                "tech_stack": json.dumps(["SQLite", "Pipeline", "Monitoring"]),
                "dependencies": json.dumps([]),
                "configuration": json.dumps(pipeline_status),
                "environment_vars": json.dumps({}),
                "build_commands": json.dumps([]),
                "test_commands": json.dumps([]),
                "deployment_info": json.dumps({}),
                "tags": json.dumps(["pipeline", "status", "monitoring"])
            }
        ]
        
        for entry in context_entries:
            cursor.execute("""
                INSERT INTO project_context 
                (project_name, project_path, description, tech_stack, dependencies, 
                 configuration, environment_vars, build_commands, test_commands, 
                 deployment_info, last_updated, active, tags, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry["name"],
                entry["path"],
                entry["description"],
                entry["tech_stack"],
                entry["dependencies"],
                entry["configuration"],
                entry["environment_vars"],
                entry["build_commands"],
                entry["test_commands"],
                entry["deployment_info"],
                datetime.now().isoformat(),
                True,
                entry["tags"],
                datetime.now().isoformat()
            ))
        
        conn.commit()
        print(f"Populated project context with {len(context_entries) + 1} entries")
        
        # Verify insertion
        cursor.execute("SELECT COUNT(*) FROM project_context")
        count = cursor.fetchone()[0]
        print(f"Total context entries in database: {count}")
        
    except Exception as e:
        print(f"Error populating project context: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    populate_project_context() 