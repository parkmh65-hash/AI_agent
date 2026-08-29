#!/bin/bash
# deploy.sh - Bash script for local deployment using Google Cloud Build (alternative for Git Bash or WSL)

SERVICE_NAME="langgraph-rag-service"
REGION="us-central1"

# Get current GCP Project
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)

if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" == "(unset)" ]; then
    echo -e "\033[0;31m❌ [ERROR] No active Google Cloud project selected.\033[0m"
    echo -e "\033[0;33mPlease log in and set a project:\033[0m"
    echo "  gcloud auth login"
    echo "  gcloud config set project [YOUR_PROJECT_ID]"
    exit 1
fi

echo -e "\033[0;36m🚀 Starting deployment for project: $PROJECT_ID...\033[0m"

# 1. Cloud Build
echo -e "\n\033[0;33m📦 Step 1: Submitting to Google Cloud Build...\033[0m"
gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_NAME .

# 2. Deploy to Cloud Run
echo -e "\n\033[0;33m⚡ Step 2: Deploying to Google Cloud Run...\033[0m"
gcloud run deploy $SERVICE_NAME \
    --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated

echo -e "\n\033[0;32m✅ Deployment complete!\033[0m"
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format='value(status.url)')
echo -e "\033[0;32m🔗 Backend Cloud Run URL: $SERVICE_URL\033[0m"
echo -e "\033[0;33m💡 Add '/chat' to the URL above and set it as 'BACKEND_URL' in Google Apps Script properties.\033[0m"
