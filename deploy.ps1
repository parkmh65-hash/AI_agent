# deploy.ps1 - Native Windows PowerShell script for local deployment using Google Cloud Build
#
# This script builds the container image in the cloud using Cloud Build and deploys it to Cloud Run.
# No local Docker installation is required!

$serviceName = "langgraph-rag-service"
$region = "us-central1"

# 1. Check if gcloud is configured with a project
$projectId = gcloud config get-value project 2>$null

if ([string]::IsNullOrEmpty($projectId) -or $projectId -eq "(unset)") {
    Write-Host "❌ [ERROR] No active Google Cloud project selected." -ForegroundColor Red
    Write-Host "Please login and select a project using:" -ForegroundColor Yellow
    Write-Host "  gcloud auth login"
    Write-Host "  gcloud config set project [YOUR_PROJECT_ID]"
    Exit
}

Write-Host "🚀 Starting deployment to Google Cloud for project: $projectId..." -ForegroundColor Cyan

# 2. Run Google Cloud Build (packages and builds container in the cloud)
Write-Host "`n📦 Step 1: Submitting source code to Google Cloud Build..." -ForegroundColor Yellow
gcloud builds submit --tag gcr.io/$projectId/$serviceName .

# 3. Deploy container image to Cloud Run
Write-Host "`n⚡ Step 2: Deploying to Google Cloud Run..." -ForegroundColor Yellow
gcloud run deploy $serviceName `
    --image gcr.io/$projectId/$serviceName `
    --platform managed `
    --region $region `
    --allow-unauthenticated

Write-Host "`n✅ Deployment complete!" -ForegroundColor Green
$serviceUrl = gcloud run services describe $serviceName --region $region --format='value(status.url)'
Write-Host "🔗 Backend Cloud Run URL: $serviceUrl" -ForegroundColor Green
Write-Host "💡 Add '/chat' to the URL above and set it as 'BACKEND_URL' in Google Apps Script properties." -ForegroundColor Yellow
