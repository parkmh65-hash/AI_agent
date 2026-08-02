# PowerShell script to sync ONLY ver_01/Server to GitHub
Param(
    [string]$CommitMessage = "Server update: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
)

Write-Host "🚀 GitHub Sync: Syncing ver_01/Server changes only to GitHub..." -ForegroundColor Cyan

$projectRoot = Resolve-Path "$PSScriptRoot\..\.."
Set-Location -Path $projectRoot

# Stage only ver_01/Server directory
git add ver_01/Server

$status = git status --porcelain ver_01/Server
if ([string]::IsNullOrWhiteSpace($status)) {
    Write-Host "ℹ️ No changes detected in ver_01/Server. Skipping commit." -ForegroundColor Yellow
} else {
    git commit -m $CommitMessage ver_01/Server
    Write-Host "✅ Successfully committed ver_01/Server changes!" -ForegroundColor Green
    Write-Host "Pushing to GitHub..." -ForegroundColor Cyan
    git push origin main
    Write-Host "✅ Successfully pushed ver_01/Server changes to GitHub!" -ForegroundColor Green
}
