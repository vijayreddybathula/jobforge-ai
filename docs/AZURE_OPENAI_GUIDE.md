# Azure OpenAI Integration Guide

Complete guide for using Azure OpenAI with jobforge-ai (GPT-4 deployment).

---

## 🔑 Azure Configuration

### Prerequisites
- Azure subscription with OpenAI deployed
- Azure API key
- Azure endpoint URL
- Deployment name (GPT-4)

### Environment Variables

```bash
# Azure OpenAI Configuration
AZURE_OPENAPI_KEY=your-azure-api-key-here
AZURE_OPENAPI_ENDPOINT=https://your-instance.openai.azure.com/
AZURE_OPENAPI_DEPLOYMENT=GPT-4
AZURE_OPENAPI_VERSION=2024-06-01-preview
AZURE_OPENAPI_API_VERSION=2024-06-01-preview
```

---

## 📋 Supported Operations

### 1. Job Description Parsing
- Uses Azure GPT-4 to parse job descriptions
- Extracts: title, company, skills, requirements, salary, location
- Handles multiple job formats and languages

### 2. Resume Analysis
- Analyzes candidate resumes with GPT-4
- Extracts: skills, experience, education, achievements
- Scores compatibility with job requirements

### 3. Job Scoring
- Matches candidates to jobs using GPT-4
- Provides compatibility score (0-10)
- Explains match reasoning
- Recommends hiring decisions

---

## 🚀 Getting Started

### 1. Get Azure Credentials

```bash
# From Azure Portal:
1. Create Azure OpenAI resource
2. Deploy GPT-4 model
3. Copy API key from Keys & Endpoints
4. Copy endpoint URL
```

### 2. Update .env File

```bash
# Copy Azure credentials from Test-Project
cp ../Test-Project/.env .env.azure
cat .env.azure | grep AZURE >> .env
```

### 3. Start Services

```bash
cd infra/
docker-compose up --build
```

### 4. Verify Azure Integration

```bash
# Check environment variables loaded
docker exec jobforge-web env | grep AZURE

# Test health check
curl http://localhost:8000/health
```

---

## 💰 Cost Tracking

### Understanding Costs

Azure OpenAI GPT-4 pricing (as of Jan 2024):
- **Input tokens:** $0.03 / 1K tokens
- **Output tokens:** $0.06 / 1K tokens

Example costs:
- Job parsing: ~500-1000 tokens ($0.015-0.03)
- Resume analysis: ~1000-2000 tokens ($0.03-0.12)
- Job scoring: ~500 tokens ($0.015-0.03)

### Monitoring Costs

```bash
# Enable Azure cost monitoring
# 1. Check Azure Portal > Cost Management
# 2. Set up budget alerts
# 3. Monitor usage in Application Insights
```

### Cost Optimization

1. **Batch Processing**
   - Process multiple jobs in single API call
   - Group related requests

2. **Caching**
   - Cache parsed job descriptions
   - Reuse analysis results
   - TTL: 24 hours for jobs, 7 days for profiles

3. **Token Optimization**
   - Use shorter prompts
   - Remove unnecessary context
   - Fine-tune prompt templates

---

## 🔍 API Testing

### Test Job Parsing

```bash
curl -X POST http://localhost:8000/api/jobs/parse \
  -H "Content-Type: application/json" \
  -d '{
    "job_description": "Senior Software Engineer needed...",
    "source": "linkedin"
  }'
```

### Test Resume Analysis

```bash
curl -X POST http://localhost:8000/api/resume/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "resume_text": "John Doe\n10 years experience...",
    "format": "text"
  }'
```

### Test Job Scoring

```bash
curl -X POST http://localhost:8000/api/jobs/score \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "job_123",
    "candidate_id": "candidate_456"
  }'
```

---

## ⚠️ Error Handling

### Common Issues

#### 1. Authentication Error
```
Error: "Invalid API key"
Solution: 
  - Verify AZURE_OPENAPI_KEY in .env
  - Check key hasn't expired in Azure Portal
  - Regenerate key if needed
```

#### 2. Endpoint Error
```
Error: "Invalid endpoint"
Solution:
  - Verify AZURE_OPENAPI_ENDPOINT format
  - Should be: https://[resource-name].openai.azure.com/
  - Check resource is in same region as deployment
```

#### 3. Deployment Not Found
```
Error: "Deployment not found"
Solution:
  - Verify AZURE_OPENAPI_DEPLOYMENT = "GPT-4"
  - Check deployment exists in Azure Portal
  - Ensure deployment is active
```

#### 4. Rate Limit Exceeded
```
Error: "429 - Too Many Requests"
Solution:
  - Implement exponential backoff (built-in)
  - Reduce request frequency
  - Upgrade Azure quota if available
```

#### 5. Timeout
```
Error: "Request timeout"
Solution:
  - Check Azure service status
  - Increase timeout threshold
  - Reduce payload size
```

---

## 📊 Monitoring & Logging

### View Logs

```bash
# Web service logs
docker-compose logs -f web | grep -i azure

# Worker logs
docker-compose logs -f worker | grep -i azure

# Full logs with timestamps
docker-compose logs --timestamps web | grep AZURE
```

### Key Metrics to Track

```bash
# API response times
curl -w "@curl-format.txt" http://localhost:8000/api/jobs/parse

# Token usage (from response headers)
curl -i -X POST http://localhost:8000/api/jobs/parse ...

# Error rates
docker-compose logs web | grep -i error | wc -l
```

---

## 🔐 Security Best Practices

### API Key Management

1. **Never commit keys to Git**
   ```bash
   # .gitignore already includes .env
   grep ".env" .gitignore
   ```

2. **Rotate keys regularly**
   ```bash
   # In Azure Portal
   # Keys & Endpoints > Regenerate key 1 or 2
   ```

3. **Use separate keys for environments**
   ```bash
   # Development: one key
   # Staging: another key
   # Production: third key
   ```

4. **Monitor key usage**
   ```bash
   # Azure Portal > Activity Log
   # Filter: "Azure OpenAI"
   ```

### Rate Limiting

```bash
# Implemented in FastAPI
# Max 100 requests per minute per IP
# Burst: 10 requests per second
```

### Request Validation

- All requests validated before Azure API call
- Input sanitization
- XSS prevention
- Rate limiting by IP

---

## 🧪 Testing

### Unit Tests

```bash
poetry run pytest tests/unit/test_azure_openai.py -v
```

### Integration Tests

```bash
# Set Azure credentials
export AZURE_OPENAPI_KEY=your-key
export AZURE_OPENAPI_ENDPOINT=your-endpoint

poetry run pytest tests/integration/test_azure_openai.py -v
```

### Cost Tracking Tests

```bash
# Verify costs are logged
poetry run pytest tests/integration/test_azure_cost.py -v
```

---

## 📈 Performance Optimization

### Caching Strategy

```python
# Job descriptions cached for 24 hours
CACHE_JOB_DESC_TTL = 86400

# Profiles cached for 7 days  
CACHE_PROFILE_TTL = 604800

# Score cache for 30 days
CACHE_SCORE_TTL = 2592000
```

### Batch Processing

```python
# Process up to 10 jobs in single request
MAX_BATCH_SIZE = 10

# Process with 2 second delay between batches
BATCH_DELAY = 2
```

### Token Optimization

```python
# Prompt template optimized for token count
# Average: 200-300 tokens per request
# (vs 500+ for verbose prompts)
```

---

## 🚀 Production Deployment

### Pre-Production Checklist

- [ ] Azure credentials configured
- [ ] Rate limiting enabled
- [ ] Cost monitoring active
- [ ] Error handling tested
- [ ] Logging configured
- [ ] Keys rotated
- [ ] Performance benchmarked
- [ ] Load tested

### Production Environment

```yaml
# docker-compose.prod.yml
# - No hot reload
# - Optimized caching
# - Production logging
# - Error tracking enabled
```

### Monitoring in Production

```bash
# Application Insights
# Set up alerts for:
# - High error rate (>1%)
# - High response time (>5s)
# - Cost threshold alerts
```

---

## 📚 Additional Resources

- [Azure OpenAI Documentation](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/)
- [GPT-4 API Reference](https://platform.openai.com/docs/api-reference/chat)
- [Cost Management](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/)
- [REST API Documentation](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/reference)

---

## 🆘 Support

### Troubleshooting Checklist

1. **Verify Azure Credentials**
   ```bash
   docker exec jobforge-web env | grep AZURE
   ```

2. **Test API Directly**
   ```bash
   curl http://localhost:8000/health
   ```

3. **Check Logs**
   ```bash
   docker-compose logs web | tail -50
   ```

4. **Verify Azure Portal**
   - Check resource status
   - Verify deployment is active
   - Check API key hasn't expired
   - Monitor quota usage

### Contact Azure Support

- Azure Portal > Support + Troubleshooting
- Priority: High (for production issues)
- Provide: Error messages, timestamps, request IDs

---

**Last Updated:** January 24, 2026  
**Version:** 1.0  
**Status:** Production Ready
