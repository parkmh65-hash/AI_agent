# deploy.ps1 - Windows PowerShell script to build and deploy to Google Cloud Run with env variables
$serviceName = "project-19-service"
$region = "us-central1"

# Check if gcloud is configured with a project
$projectId = gcloud config get-value project 2>$null

if ([string]::IsNullOrEmpty($projectId) -or $projectId -eq "(unset)") {
    Write-Host "❌ [ERROR] No active Google Cloud project selected." -ForegroundColor Red
    Exit
}

# Read variables from parent directory's .env file
$envVars = @()
$dotenvPath = "C:\Anti-project\.env"
if (Test-Path $dotenvPath) {
    Get-Content $dotenvPath | ForEach-Object {
        if ($_ -match "^\s*([^#=\s]+)\s*=\s*(.*)\s*$") {
            $key = $Matches[1].Trim()
            $val = $Matches[2].Trim()
            if ($val -and -not ($val -like "your_*")) {
                $envVars += "$key=$val"
            }
        }
    }
}
$envString = $envVars -join ","

Write-Host "🚀 Starting deployment to Google Cloud for project: $projectId..." -ForegroundColor Cyan

# 1. Run Google Cloud Build
Write-Host "`n📦 Step 1: Submitting source code to Google Cloud Build..." -ForegroundColor Yellow
gcloud builds submit --tag gcr.io/$projectId/$serviceName .

# 2. Deploy container image to Cloud Run with env vars
Write-Host "`n⚡ Step 2: Deploying to Google Cloud Run with environment variables..." -ForegroundColor Yellow
gcloud run deploy $serviceName `
    --image gcr.io/$projectId/$serviceName `
    --platform managed `
    --region $region `
    --set-env-vars $envString `
    --allow-unauthenticated

Write-Host "`n✅ Deployment complete!" -ForegroundColor Green
$serviceUrl = gcloud run services describe $serviceName --region $region --format='value(status.url)'
Write-Host "🔗 Backend Cloud Run URL: $serviceUrl" -ForegroundColor Green
