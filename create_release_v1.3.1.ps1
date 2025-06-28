# GitHub Release Creation Script for v1.3.2
# This script creates a release on GitHub using the GitHub API

param(
    [string]$Tag = "v1.3.2",
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
$changelogPath = "CHANGELOG_v1.3.2.md"
if (Test-Path $changelogPath) {
    $changelogContent = Get-Content $changelogPath -Raw
} else {
    $changelogContent = "Release v1.3.2 - Version bump and rollup of previous fixes."
}

# Create release notes
$releaseNotes = @"
# Release v1.3.2

## 🚀 Patch Release

- Version bump to 1.3.2
- All bug fixes and improvements from 1.3.1

## Changelog
```
$changelogContent
```

---

**Note**: This release is a rollup of previous bug fixes and improvements.
"@

# Prepare the release data
$releaseData = @{
    tag_name = $Tag
    name = "Release v1.3.2"
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