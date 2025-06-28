#!/usr/bin/env python3
"""
Populate Code Changes Table

This script populates the code_changes table with Git diff history
to track code evolution and changes over time.
"""

import sqlite3
import subprocess
import json
import os
import re
from datetime import datetime
from typing import List, Dict, Any

def get_git_log():
    """Get Git log with detailed information"""
    try:
        # Get detailed git log with file changes
        result = subprocess.run([
            'git', 'log', '--pretty=format:%H|%an|%ae|%ad|%s',
            '--date=iso',
            '--numstat'
        ], capture_output=True, text=True, check=True)
        
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Git command failed: {e}")
        return None
    except FileNotFoundError:
        print("Git not found. Make sure you're in a Git repository.")
        return None

def parse_git_log(git_output: str) -> List[Dict[str, Any]]:
    """Parse Git log output into structured data"""
    if not git_output:
        return []
    
    changes = []
    lines = git_output.strip().split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Skip empty lines
        if not line:
            i += 1
            continue
        
        # Parse commit header
        if '|' in line and not line[0].isdigit():
            try:
                commit_hash, author, email, date, message = line.split('|', 4)
                
                # Collect file changes for this commit
                file_changes = []
                i += 1
                
                while i < len(lines) and lines[i].strip() and lines[i][0].isdigit():
                    parts = lines[i].strip().split('\t')
                    if len(parts) >= 3:
                        additions, deletions, filename = parts[0], parts[1], parts[2]
                        file_changes.append({
                            'filename': filename,
                            'additions': int(additions) if additions.isdigit() else 0,
                            'deletions': int(deletions) if deletions.isdigit() else 0
                        })
                    i += 1
                
                changes.append({
                    'commit_hash': commit_hash,
                    'author': author,
                    'email': email,
                    'date': date,
                    'message': message,
                    'file_changes': file_changes
                })
                
            except ValueError:
                i += 1
        else:
            i += 1
    
    return changes

def get_file_diff(commit_hash: str, filename: str) -> str:
    """Get diff for a specific file in a commit"""
    try:
        result = subprocess.run([
            'git', 'show', f'{commit_hash}:{filename}'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            return result.stdout
        else:
            # File might have been deleted
            return ""
    except:
        return ""

def analyze_change_impact(file_changes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze the impact of changes"""
    total_additions = sum(fc['additions'] for fc in file_changes)
    total_deletions = sum(fc['deletions'] for fc in file_changes)
    
    # Categorize files
    file_types = {}
    for fc in file_changes:
        ext = os.path.splitext(fc['filename'])[1]
        file_types[ext] = file_types.get(ext, 0) + 1
    
    # Determine change type
    if total_additions > total_deletions * 2:
        change_type = "feature_addition"
    elif total_deletions > total_additions * 2:
        change_type = "cleanup_removal"
    elif total_additions > 100 or total_deletions > 100:
        change_type = "major_refactor"
    else:
        change_type = "minor_change"
    
    return {
        'total_additions': total_additions,
        'total_deletions': total_deletions,
        'net_change': total_additions - total_deletions,
        'files_modified': len(file_changes),
        'file_types': file_types,
        'change_type': change_type,
        'impact_score': min(10, (total_additions + total_deletions) / 10)
    }

def populate_code_changes():
    """Populate the code_changes table with Git history"""
    
    db_path = "sigil_rag_cache.db"
    
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return
    
    # Get Git log
    git_output = get_git_log()
    if not git_output:
        return
    
    # Parse changes
    changes = parse_git_log(git_output)
    if not changes:
        print("No Git changes found")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Clear existing changes
        cursor.execute("DELETE FROM code_changes")
        
        # Insert changes (limit to last 50 commits to avoid overwhelming the DB)
        for change in changes[:50]:
            # Analyze impact
            impact = analyze_change_impact(change['file_changes'])
            
            # Get sample file content (first file)
            old_content = ""
            new_content = ""
            if change['file_changes']:
                filename = change['file_changes'][0]['filename']
                new_content = get_file_diff(change['commit_hash'], filename)
            
            # Create diff summary
            diff_summary = f"Modified {len(change['file_changes'])} files: +{impact['total_additions']} -{impact['total_deletions']} lines"
            
            cursor.execute("""
                INSERT INTO code_changes 
                (file_path, change_type, old_content, new_content, diff_summary, 
                 commit_hash, commit_message, author, timestamp, impact_score, 
                 affected_functions, breaking_changes, tags, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                change['file_changes'][0]['filename'] if change['file_changes'] else "",
                impact['change_type'],
                old_content,
                new_content,
                diff_summary,
                change['commit_hash'],
                change['message'],
                change['author'],
                change['date'],
                impact['impact_score'],
                json.dumps([]),  # affected_functions - would need deeper analysis
                json.dumps([]),  # breaking_changes - would need semantic analysis
                json.dumps(list(impact['file_types'].keys())),  # tags based on file types
                datetime.now().isoformat()
            ))
        
        conn.commit()
        print(f"Populated {len(changes[:50])} code changes from Git history")
        
        # Verify insertion
        cursor.execute("SELECT COUNT(*) FROM code_changes")
        count = cursor.fetchone()[0]
        print(f"Total code changes in database: {count}")
        
    except Exception as e:
        print(f"Error populating code changes: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    populate_code_changes() 