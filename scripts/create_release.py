#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Release automation script for rust-crate-pipeline.
This script automates the release process including version updates,
commits, and tag creation.
"""

import os
import sys
import subprocess
import re
from pathlib import Path
from datetime import datetime

def run_command(cmd, check=True, capture_output=True):
    """Run a shell command and return the result."""
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            check=check, 
            capture_output=capture_output,
            text=True
        )
        return result
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {cmd}")
        print(f"Error: {e}")
        if not check:
            return e
        sys.exit(1)

def get_current_version():
    """Get the current version from version.py."""
    version_file = Path("rust_crate_pipeline/version.py")
    with open(version_file, 'r') as f:
        content = f.read()
        match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
        if match:
            return match.group(1)
    raise ValueError("Could not find version in version.py")

def update_version_files(version):
    """Update version in all relevant files."""
    files_to_update = [
        "rust_crate_pipeline/version.py",
        "pyproject.toml",
        "setup.py"
    ]
    
    for file_path in files_to_update:
        if not Path(file_path).exists():
            continue
            
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Update version in different file formats
        if file_path.endswith('.py'):
            content = re.sub(
                r'__version__\s*=\s*["\'][^"\']+["\']',
                f'__version__ = "{version}"',
                content
            )
        elif file_path.endswith('.toml'):
            content = re.sub(
                r'version\s*=\s*["\'][^"\']+["\']',
                f'version = "{version}"',
                content
            )
        
        with open(file_path, 'w') as f:
            f.write(content)
        
        print(f"Updated version in {file_path}")

def create_changelog(version):
    """Create a changelog entry."""
    changelog_file = f"CHANGELOG_v{version}.md"
    
    if Path(changelog_file).exists():
        print(f"Changelog {changelog_file} already exists")
        return
    
    changelog_content = f"""# Changelog for rust-crate-pipeline v{version}

## [{version}] - {datetime.now().strftime('%Y-%m-%d')}

### Added
- Enhanced scraping functionality with Crawl4AI integration
- Improved cross-platform compatibility
- Better error handling and logging

### Fixed
- Various bug fixes and improvements

### Changed
- Updated dependencies to latest versions

---

**Note**: This is an automated release. See the commit history for detailed changes.
"""
    
    with open(changelog_file, 'w') as f:
        f.write(changelog_content)
    
    print(f"Created changelog: {changelog_file}")

def main():
    """Main release process."""
    if len(sys.argv) != 2:
        print("Usage: python create_release.py <version>")
        print("Example: python create_release.py 1.3.5")
        sys.exit(1)
    
    new_version = sys.argv[1]
    current_version = get_current_version()
    
    print(f"Current version: {current_version}")
    print(f"New version: {new_version}")
    print()
    
    # Confirm release
    response = input(f"Proceed with release v{new_version}? (y/N): ")
    if response.lower() != 'y':
        print("Release cancelled")
        sys.exit(0)
    
    try:
        # Update version files
        print("Updating version files...")
        update_version_files(new_version)
        
        # Create changelog
        print("Creating changelog...")
        create_changelog(new_version)
        
        # Build package
        print("Building package...")
        run_command("python -m build")
        
        # Commit changes
        print("Committing changes...")
        run_command("git add .")
        run_command(f'git commit -m "Release v{new_version}"')
        
        # Create and push tag
        print("Creating and pushing tag...")
        run_command(f'git tag -a "v{new_version}" -m "Release v{new_version}"')
        run_command("git push origin main")
        run_command(f"git push origin v{new_version}")
        
        print(f"\n[SUCCESS] Release v{new_version} created successfully!")
        print("\nNext steps:")
        print("1. GitHub Actions will automatically build and publish to PyPI and Docker Hub")
        print("2. Check the Actions tab in GitHub for build status")
        print("3. Verify the release on PyPI and Docker Hub")
        
    except Exception as e:
        print(f"\n[ERROR] Release failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 