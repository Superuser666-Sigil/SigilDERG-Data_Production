# Changelog v1.3.6

## [1.3.6] - 2025-01-21

### Changed
- **BREAKING**: Updated Python version requirement from 3.9+ to 3.12+
- Updated all type annotations to use modern syntax (dict[str, Any] instead of Dict[str, Any])
- Removed support for Python 3.8, 3.9, 3.10, and 3.11
- Updated classifiers in pyproject.toml to reflect new Python version support

### Technical Improvements
- Leveraged Python 3.12+ features for better type safety and performance
- Simplified type annotations throughout the codebase
- Improved compatibility with modern Python tooling and linters
- Enhanced code readability with modern Python syntax
- Added `from __future__ import annotations` to enable lazy type evaluation

### Documentation
- Updated README.md to clearly specify Python 3.12+ requirement
- Added requirements section with detailed system dependencies
- Updated installation instructions to reflect new version requirements

### Build System
- Updated pyproject.toml with new Python version constraint
- Updated setup.py to match pyproject.toml requirements
- Improved build process compatibility with modern Python versions

### Compatibility
- This version is **not backward compatible** with Python versions below 3.12
- Users must upgrade to Python 3.12 or higher to use this version
- All modern type annotations now use the simplified syntax introduced in Python 3.9+

### Migration Notes
- If you're currently using Python 3.11 or earlier, you'll need to upgrade to Python 3.12+
- No code changes are required for existing users, only Python version upgrade
- All existing functionality remains the same with improved type safety 