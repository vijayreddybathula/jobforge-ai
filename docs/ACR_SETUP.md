# Azure Container Registry Setup

## Overview
This guide explains how to set up Azure Container Registry (ACR) and configure the CI/CD pipeline to automatically push Docker images on merge.

## Prerequisites
- Azure subscription
- Azure CLI installed locally
- GitHub repository access with admin permissions

## Step 1: Create Azure Container Registry

### Option A: Using Azure Portal
1. Go to Azure Portal → Create a resource → Container Registry
2. Fill in the details:
   - **Resource Group**: Create or select existing
   - **Registry name**: `jobforge` or `jobforgeai` (must be globally unique)
   - **Location**: Select closest to your deployment region
   - **SKU**: Standard (recommended) or Premium for advanced features

3. Click **Create**

### Option B: Using Azure CLI
```bash
az group create --name jobforge-rg --location eastus

az acr create \
  --resource-group jobforge-rg \
  --name jobforge \
  --sku Standard
```

## Step 2: Create Service Principal for CI/CD

### Using Azure CLI
```bash
# Create service principal
az ad sp create-for-rbac \
  --name jobforge-ci-cd \
  --role AcrPush \
  --scopes /subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{RESOURCE_GROUP}/providers/Microsoft.ContainerRegistry/registries/{REGISTRY_NAME}
```

**Output will include:**
```json
{
  "appId": "YOUR_APP_ID",
  "password": "YOUR_PASSWORD",
  "tenant": "YOUR_TENANT_ID"
}
```

Store these credentials securely!

## Step 3: Get ACR Credentials

### Method 1: Service Principal (Recommended for CI/CD)
From the output above:
- **Username**: `appId` 
- **Password**: `password`

### Method 2: Admin Account (Simpler, less secure)
```bash
az acr update -n jobforge --admin-enabled true
az acr credential show -n jobforge --resource-group jobforge-rg
```

This gives you:
- **Username**: `jobforge`
- **Password**: One of the two passwords shown

## Step 4: Configure GitHub Secrets

1. Go to your GitHub repository → **Settings** → **Secrets and variables** → **Actions**

2. Add these secrets:
   - **ACR_REGISTRY_URL**: `jobforge.azurecr.io`
     - Format: `{registry-name}.azurecr.io`
   
   - **ACR_USERNAME**: 
     - Service Principal: Use `appId`
     - Admin Account: Use `jobforge`
   
   - **ACR_PASSWORD**: 
     - Service Principal: Use `password`
     - Admin Account: Use the password from credential show

## Step 5: Verify Setup

### Test login locally
```bash
# Option 1: Service Principal
az acr login -n jobforge --username {APP_ID} --password {PASSWORD}

# Option 2: Admin Account  
az acr login -n jobforge
```

### Verify credentials
```bash
docker login jobforge.azurecr.io \
  -u {USERNAME} \
  -p {PASSWORD}
```

## Step 6: View Images in ACR

```bash
# List repositories
az acr repository list -n jobforge -o table

# List tags for a repository
az acr repository show-tags -n jobforge --repository jobforge-web -o table

# Get image details
az acr repository show -n jobforge --image jobforge-web:latest
```

## Image Naming Convention

After merge, images are tagged as:
- **Main branch**: 
  - `jobforge.azurecr.io/jobforge/web:latest`
  - `jobforge.azurecr.io/jobforge/worker:latest`
  - `jobforge.azurecr.io/jobforge/web:main-{COMMIT_SHA}`
  - `jobforge.azurecr.io/jobforge/worker:main-{COMMIT_SHA}`

- **Develop branch**:
  - `jobforge.azurecr.io/jobforge/web:develop-{COMMIT_SHA}`
  - `jobforge.azurecr.io/jobforge/worker:develop-{COMMIT_SHA}`

## Automation Flow

```
Code Merge to main/develop
    ↓
GitHub Actions CI/CD triggered
    ↓
Tests run (unit + integration)
    ↓
Docker images built
    ↓
Images pushed to ACR (on merge)
    ↓
Images pushed to GitHub Container Registry (all events)
    ↓
Snapshots available for deployment
```

## Manual Image Push (Local Testing)

If you need to manually push images:

```bash
# 1. Authenticate
docker login jobforge.azurecr.io -u {USERNAME} -p {PASSWORD}

# 2. Build images
docker build -f infra/docker/Dockerfile.web -t jobforge-web:latest .
docker build -f infra/docker/Dockerfile.worker -t jobforge-worker:latest .

# 3. Tag for ACR
docker tag jobforge-web:latest jobforge.azurecr.io/jobforge/web:latest
docker tag jobforge-worker:latest jobforge.azurecr.io/jobforge/worker:latest

# 4. Push
docker push jobforge.azurecr.io/jobforge/web:latest
docker push jobforge.azurecr.io/jobforge/worker:latest
```

## Troubleshooting

### Failed to authenticate
```bash
# Verify credentials are correct
az acr credential show -n jobforge

# If using service principal, verify it has AcrPush role
az role assignment list --scope /subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{RESOURCE_GROUP}/providers/Microsoft.ContainerRegistry/registries/{REGISTRY_NAME}
```

### Images not appearing in ACR
1. Check GitHub Actions logs for build errors
2. Verify service principal has `AcrPush` role
3. Confirm ACR_REGISTRY_URL secret is set correctly

### Push quota exceeded
- ACR Standard SKU has storage limits
- Upgrade to Premium or delete old images
```bash
az acr repository delete -n jobforge --image jobforge-web:old-tag
```

## Clean Up Old Images

```bash
# List all tags for a repository
az acr repository show-tags -n jobforge --repository jobforge-web -o table

# Delete specific tag
az acr repository delete -n jobforge --image jobforge-web:old-tag

# Delete entire repository
az acr repository delete -n jobforge --repository jobforge-web
```

## Next Steps

1. Set up deployment from ACR to:
   - Azure Container Instances (ACI)
   - Azure Kubernetes Service (AKS)
   - Azure App Service

2. Configure image retention policies:
```bash
az acr config retention update -n jobforge --days 30 --enabled true
```

3. Enable vulnerability scanning:
```bash
az acr config content-trust update -n jobforge --status enabled
```

## References
- [Azure Container Registry Documentation](https://docs.microsoft.com/en-us/azure/container-registry/)
- [ACR Authentication Methods](https://docs.microsoft.com/en-us/azure/container-registry/container-registry-authentication)
- [Push and Pull Container Images](https://docs.microsoft.com/en-us/azure/container-registry/container-registry-get-started-docker-cli)
