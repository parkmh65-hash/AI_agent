# Google Cloud Run Deploy Script for heritage-min (Project: heritage-503408, Region: us-central1)
Param(
    [string]$ProjectId = "my-second-project-502012",
    [string]$ServiceName = "heritage",
    [string]$Region = "us-central1"
)

Write-Host "🚀 Deploying Sejong Heritage Backend Server to GCP Cloud Run..." -ForegroundColor Cyan
Write-Host "Project: $ProjectId | Service: $ServiceName | Region: $Region" -ForegroundColor Yellow

# Ensure gcloud CLI is authenticated and configured
gcloud config set project $ProjectId

# Build image using Cloud Build and Deploy to Cloud Run
gcloud run deploy $ServiceName `
    --source . `
    --region $Region `
    --project $ProjectId `
    --platform managed `
    --allow-unauthenticated `
    --port 8080 `
    --set-env-vars "APP_NAME=세종시 AI 문화유산 플랫폼 API,DEBUG=False"

Write-Host "✅ Cloud Run Deployment Complete!" -ForegroundColor Green
