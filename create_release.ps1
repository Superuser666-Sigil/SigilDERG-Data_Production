# GitHub Release Creation Script
# This script creates a release on GitHub using the GitHub API

param(
    [string]$Tag = "v1.3.0",
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
$changelogPath = "CHANGELOG_v1.3.0.txt"
if (Test-Path $changelogPath) {
    $changelogContent = Get-Content $changelogPath -Raw
} else {
    $changelogContent = "Release v1.3.0 - Major updates including Azure OpenAI integration, LiteLLM support, and enhanced pipeline features."
}

# Create release notes
$releaseNotes = @"
# Release v1.3.0

## Major Features
- **Azure OpenAI Integration**: Added support for Azure OpenAI endpoints with proper configuration
- **LiteLLM Support**: Unified LLM processor supporting multiple providers (OpenAI, Azure, Ollama, LM Studio)
- **Enhanced RAG Cache**: Populated database with Rule Zero policies, architectural patterns, and project context
- **Docker Improvements**: Updated Dockerfile and docker-compose.yml for production deployment
- **PyPI Publishing**: Automated workflow for publishing to PyPI
- **GitHub Actions**: Comprehensive CI/CD workflows for testing and validation

## Technical Improvements
- Fixed type annotations and import issues
- Consolidated redundant test files
- Enhanced error handling and logging
- Improved code organization and structure
- Added comprehensive documentation

## Changelog
```
$changelogContent
```

## Installation
\`\`\`bash
pip install rust-crate-pipeline==1.3.0
\`\`\`

## Breaking Changes
None - this is a feature release with backward compatibility maintained.
"@

# Prepare the release data
$releaseData = @{
    tag_name = $Tag
    name = "Release v1.3.0"
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