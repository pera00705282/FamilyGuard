# CI/CD Pipeline Setup

## Required GitHub Secrets

1. Go to your repository Settings > Secrets and variables > Actions
2. Click "New repository secret" and add:

### Required Secrets:
- STAGING_SSH_PRIVATE_KEY: Your SSH private key for the staging server
- STAGING_HOST: Your server's IP or domain

### Optional Secrets:
- CODECOV_TOKEN: For code coverage reporting
- STAGING_SSH_PORT: (default: 22)
- STAGING_SSH_USER: (default: 'ubuntu')
- SLACK_WEBHOOK_URL: For deployment notifications

## Required GitHub Environments

1. Go to your repository Settings > Environments
2. Create these environments:
   - staging
   - 
otifications

## First Deployment

1. Push to the main branch to trigger the workflow
2. Monitor the workflow in the Actions tab
