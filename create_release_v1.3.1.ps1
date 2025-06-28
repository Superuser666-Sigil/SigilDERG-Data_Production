# GitHub Release Creation Script for v1.3.1
# This script creates a release on GitHub using the GitHub API

param(
    [string]$Tag = "v1.3.1",
    [string]$Repo = "Superuser666-Sigil/SigilDERG-Data_Production"
)

# Check if GitHub token is available
$token = $env:GITHUB_TOKEN
if (-not $token) {
    Write-Host "Error: GITHUB_TOKEN environment variable not set."
    Write-Host "Please set your GitHub personal access token as GITHUB_TOKEN environment variable."
    exit 1
}

# Read changelog content
$changelogPath = "CHANGELOG_v1.3.1.md"
if (Test-Path $changelogPath) {
    $changelogContent = Get-Content $changelogPath -Raw
} else {
    $changelogContent = "Release v1.3.1 - Type annotation compatibility fixes and code quality improvements."
}

# Create release notes
$releaseNotes = @"
# Release v1.3.1

## 🐛 Bug Fixes

### Type Annotation Compatibility
- **Fixed Python 3.9 compatibility issues** in type annotations
- **Resolved IDE linter errors** in core modules:
  - `rust_crate_pipeline/network.py`
  - `rust_crate_pipeline/pipeline.py` 
  - `rust_crate_pipeline/production_config.py`

### Specific Fixes Applied
- **Updated `dict[str, Any]` → `"dict[str, Any]"`** format for Python 3.9 compatibility
- **Fixed `list[str]` → `"list[str]"`** type annotations
- **Resolved `Union` type expressions** in conditional imports
- **Fixed variable references in type expressions** by using `Any` type where appropriate
- **Updated User-Agent strings** to version 1.3.1

## 🔧 Code Quality Improvements

### Type Safety
- **Enhanced type checking compatibility** across all Python versions
- **Improved IDE support** with proper type annotations
- **Reduced linter warnings** and errors
- **Better code maintainability** with consistent type patterns

### Development Experience
- **Fixed import issues** with conditional module loading
- **Improved error handling** in type-sensitive operations
- **Enhanced code readability** with proper type hints

## 📦 Technical Details

### Files Modified
- `rust_crate_pipeline/version.py` - Version bump and changelog
- `setup.py` - Package version update
- `pyproject.toml` - Project version update
- `rust_crate_pipeline/network.py` - Type annotation fixes
- `rust_crate_pipeline/pipeline.py` - Type annotation fixes
- `rust_crate_pipeline/production_config.py` - Type annotation fixes

### Compatibility
- **Python**: 3.9+ (improved compatibility)
- **Type Checkers**: pyright, mypy, and other type checkers now work without errors
- **IDEs**: Enhanced support for VS Code, PyCharm, and other IDEs

## 🚀 Installation

\`\`\`bash
pip install rust-crate-pipeline==1.3.1
\`\`\`

## 🔄 Migration from 1.3.0

This is a **patch release** with no breaking changes. All existing functionality remains the same, but with improved type safety and IDE support.

## 📋 Testing

All fixes have been verified:
- ✅ Syntax validation passed
- ✅ Import tests successful
- ✅ Type annotation compatibility confirmed
- ✅ No breaking changes introduced

## 🎯 Impact

- **Developers**: Better IDE experience with proper type hints
- **Users**: No functional changes, improved stability
- **Maintainers**: Cleaner codebase with resolved linter issues

## 📋 Changelog

\`\`\`
$changelogContent
\`\`\`

---

**Note**: This release focuses on code quality improvements and type safety enhancements. All existing APIs and functionality remain unchanged.
"@

# Prepare the release data
$releaseData = @{
    tag_name = $Tag
    name = "Release v1.3.1"
    body = $releaseNotes
    draft = $false
    prerelease = $false
} | ConvertTo-Json -Depth 10

# Create the release
$headers = @{
    "Authorization" = "token $token"
    "Accept" = "application/vnd.github.v3+json"
    "Content-Type" = "application/json"
}

$uri = "https://api.github.com/repos/$Repo/releases"

try {
    Write-Host "Creating release for tag: $Tag"
    $response = Invoke-RestMethod -Uri $uri -Method Post -Headers $headers -Body $releaseData
    
    Write-Host "Release created successfully!"
    Write-Host "Release URL: $($response.html_url)"
    Write-Host "Release ID: $($response.id)"
    
} catch {
    Write-Host "Error creating release: $($_.Exception.Message)"
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $responseBody = $reader.ReadToEnd()
        Write-Host "Response: $responseBody"
    }
    exit 1
} 