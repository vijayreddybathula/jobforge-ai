# Production Deployment Guide

Complete guide for deploying jobforge-ai to production with Azure OpenAI.

---

## 📋 Pre-Deployment Checklist

### Environment & Infrastructure
- [ ] Azure subscription active and configured
- [ ] Azure OpenAI resource deployed with GPT-4
- [ ] Cloud infrastructure provisioned (AWS/Azure/GCP)
- [ ] Database backup strategy in place
- [ ] Redis replication configured
- [ ] SSL/TLS certificates provisioned
- [ ] Domain name configured with DNS

### Security
- [ ] API keys rotated
- [ ] Database passwords updated
- [ ] Redis password secured
- [ ] CORS properly configured
- [ ] Rate limiting enabled
- [ ] WAF (Web Application Firewall) configured
- [ ] DDoS protection enabled
- [ ] Security audit completed
- [ ] Compliance checklist reviewed

### Application
- [ ] All tests passing (unit, integration, performance)
- [ ] Code reviewed and approved
- [ ] Secrets moved to secure vault (AWS Secrets Manager/Azure Key Vault)
- [ ] Environment variables documented
- [ ] Configuration files prepared
- [ ] Database migrations tested
- [ ] Backup/restore procedures tested
- [ ] Rollback plan documented

### Monitoring & Logging
- [ ] Application monitoring configured (DataDog/New Relic)
- [ ] Log aggregation set up (CloudWatch/Log Analytics)
- [ ] Alert thresholds defined
- [ ] Dashboard created
- [ ] Cost monitoring enabled
- [ ] Performance baselines documented
- [ ] Health check endpoints configured

### Documentation
- [ ] Deployment runbook created
- [ ] Runbook tested
- [ ] On-call procedures documented
- [ ] Troubleshooting guide prepared
- [ ] Team trained on procedures

---

## 🚀 Deployment Steps

### Phase 1: Preparation (24 hours before)

```bash
# 1. Create production branch
git checkout -b release/v1.0.0
git push origin release/v1.0.0

# 2. Create release tag
git tag -a v1.0.0 -m "Production release v1.0.0"
git push origin v1.0.0

# 3. Build production images
docker-compose -f infra/docker-compose.prod.yml build

# 4. Run smoke tests
poetry run pytest tests/ -v -m "not slow"

# 5. Performance baseline
poetry run python tests/performance/benchmark.py

# 6. Notify team
echo "Deployment scheduled for [TIME]"
```

### Phase 2: Pre-Deployment (1 hour before)

```bash
# 1. Final code review
git log --oneline origin/main..HEAD

# 2. Database backup
pg_dump production_db > backup_$(date +%Y%m%d_%H%M%S).sql

# 3. Redis backup
docker exec jobforge-redis redis-cli BGSAVE

# 4. Verify all services healthy
docker-compose -f infra/docker-compose.prod.yml ps

# 5. Check monitoring systems
curl https://monitoring.example.com/health

# 6. Notify stakeholders
# "Deployment will begin at [TIME]"
```

### Phase 3: Deployment (Blue-Green Strategy)

```bash
# 1. Start new (Green) environment
docker-compose -f infra/docker-compose.prod.yml up -d --no-deps --build web worker

# 2. Run migrations
docker exec jobforge-web alembic upgrade head

# 3. Run health checks
for i in {1..30}; do
  curl -s http://localhost:8000/health > /dev/null && break
  sleep 2
done

# 4. Run smoke tests
poetry run pytest tests/smoke/ -v

# 5. Run performance checks
poetry run python tests/performance/benchmark.py

# 6. Switch traffic to green (via load balancer)
# AWS: Update target group
# Azure: Update traffic manager
# Manual: Update nginx upstream

# 7. Monitor error rate for 5 minutes
# Should be <0.1%
```

### Phase 4: Verification (30 minutes)

```bash
# 1. Check error rates
curl https://monitoring.example.com/api/errors

# 2. Verify database connectivity
docker exec jobforge-web psql $DATABASE_URL -c "SELECT version();"

# 3. Verify Azure OpenAI connectivity
docker logs jobforge-web | grep -i "azure\|openai"

# 4. Check cost tracking
curl https://monitoring.example.com/api/costs

# 5. Run full test suite
poetry run pytest tests/ --tb=short

# 6. Load test (low volume)
locust -f tests/load/locustfile.py --headless -u 10 -r 1 -t 5m
```

### Phase 5: Rollback (if needed)

```bash
# If deployment fails, rollback to blue environment:

# 1. Switch traffic back to blue
# AWS: Revert target group
# Azure: Revert traffic manager

# 2. Monitor error rate
# Should drop back to baseline

# 3. Investigate issue
docker logs jobforge-web | tail -100

# 4. Fix and redeploy
# Create new release/patch
```

---

## 🏗️ Architecture

### Production Environment

```
┌─────────────────────────────────────────┐
│         Load Balancer (SSL/TLS)         │
└─────────────┬───────────────────────────┘
              │
    ┌─────────┴──────────┬──────────┐
    │                    │          │
┌───▼───┐          ┌─────▼──┐  ┌──▼──┐
│ Web-1 │          │ Web-2  │  │Web-3│
└───┬───┘          └─────┬──┘  └──┬──┘
    │                    │        │
    └─────────────┬──────┴────────┘
                  │
         ┌────────▼────────┐
         │   PostgreSQL    │
         │   (Primary)     │
         └────────┬────────┘
                  │
         ┌────────▼────────┐
         │ PostgreSQL      │
         │ (Standby)       │
         └─────────────────┘

         ┌──────────────────┐
         │  Redis Cluster   │
         │  (3 nodes)       │
         └──────────────────┘

         ┌──────────────────┐
         │ Azure OpenAI     │
         │ (API endpoint)   │
         └──────────────────┘
```

---

## 📊 Monitoring

### Key Metrics

```
API Performance:
  - Response time: < 2s (p95)
  - Throughput: > 100 req/s
  - Error rate: < 0.1%

Database:
  - Connection pool: < 50% utilization
  - Query time: < 500ms (p95)
  - Replication lag: < 100ms

Redis:
  - Memory usage: < 80%
  - Hit ratio: > 80%
  - Evictions: < 1/hour

Azure OpenAI:
  - API latency: < 5s
  - Success rate: > 99%
  - Cost per request: < $0.01
```

### Alerting Rules

```yaml
# CPU Usage
cpu_usage > 80% for 5 minutes

# Memory
memory_usage > 85% for 5 minutes

# Error Rate
error_rate > 1% for 2 minutes

# Azure API Failure
azure_error_count > 5 in 5 minutes

# Database Replication Lag
replication_lag > 1000ms for 5 minutes

# Redis Evictions
redis_evictions > 0 for 5 minutes
```

---

## 🔄 Scaling

### Horizontal Scaling

```bash
# Add more web servers
docker-compose -f infra/docker-compose.prod.yml up -d --scale web=5

# Add more workers
docker-compose -f infra/docker-compose.prod.yml up -d --scale worker=10
```

### Vertical Scaling

```bash
# Increase resource limits
# In docker-compose.prod.yml
resources:
  limits:
    cpus: '2'
    memory: 4G
  reservations:
    cpus: '1'
    memory: 2G
```

### Auto-Scaling

```yaml
# Kubernetes HPA (Horizontal Pod Autoscaler)
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: jobforge-web-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: jobforge-web
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

---

## 🔐 Security Hardening

### SSL/TLS Configuration

```nginx
# nginx.conf
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers HIGH:!aNULL:!MD5;
ssl_prefer_server_ciphers on;
add_header Strict-Transport-Security "max-age=31536000" always;
```

### API Security

```python
# app/security.py
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response
```

### Rate Limiting

```python
# Implemented with redis-py-cluster
MAX_REQUESTS_PER_MINUTE = 100
MAX_REQUESTS_PER_SECOND = 10
```

### Key Rotation

```bash
# Monthly key rotation
#!/bin/bash
# 1. Generate new key in Azure Portal
# 2. Update Key Vault
# 3. Deploy with new key
# 4. Monitor for errors
# 5. Retire old key after 24h
```

---

## 📈 Cost Optimization

### Cost Tracking

```bash
# Daily cost report
curl https://monitoring.example.com/api/costs/daily

# Azure OpenAI costs
echo "Daily GPT-4 usage:"
docker logs jobforge-web | grep "tokens_used" | tail -100
```

### Cost Reduction Strategies

1. **Batch Processing** (10-20% savings)
   - Group jobs by skill requirements
   - Batch parse similar jobs
   - Reuse cached analyses

2. **Token Optimization** (15-25% savings)
   - Shorter prompts
   - Remove unnecessary context
   - Use templates

3. **Caching** (30-50% savings)
   - Cache job descriptions (24h)
   - Cache profiles (7d)
   - Cache scores (30d)

4. **Scheduled Processing** (5-10% savings)
   - Off-peak processing cheaper
   - Batch overnight jobs
   - Monthly bulk analysis

---

## 📞 On-Call Procedures

### Incident Response

```
1. Alert triggered
2. On-call engineer notified
3. Assess severity (P1-P4)
4. Follow runbook
5. Communicate status
6. Resolve issue
7. Post-mortem within 24h
```

### Severity Levels

```
P1 (Critical): Service down, data loss risk
   - Response time: 15 min
   - Fix target: 1 hour

P2 (High): Degraded performance
   - Response time: 30 min
   - Fix target: 4 hours

P3 (Medium): Minor issues, workarounds exist
   - Response time: 2 hours
   - Fix target: 24 hours

P4 (Low): Enhancement requests
   - Response time: Next business day
```

### Runbooks

- [Database Failover](./runbooks/db-failover.md)
- [Redis Recovery](./runbooks/redis-recovery.md)
- [Azure API Outage](./runbooks/azure-api-outage.md)
- [Memory Leak](./runbooks/memory-leak.md)
- [High Error Rate](./runbooks/high-error-rate.md)

---

## ✅ Post-Deployment

### Day 1
- [ ] Monitor dashboards continuously
- [ ] Check error rates hourly
- [ ] Verify Azure API usage
- [ ] Confirm data integrity
- [ ] Performance baseline stable

### Week 1
- [ ] Team debriefing meeting
- [ ] Update runbooks based on learnings
- [ ] Performance analysis
- [ ] Cost analysis
- [ ] Security audit

### Ongoing
- [ ] Weekly performance review
- [ ] Monthly cost optimization
- [ ] Quarterly security audit
- [ ] Regular backup tests
- [ ] Disaster recovery drills

---

## 📚 Reference

### Documentation
- [Azure Deployment Guide](./docs/AZURE_DEPLOYMENT.md)
- [Disaster Recovery Plan](./docs/DISASTER_RECOVERY.md)
- [Security Policies](./docs/SECURITY_POLICIES.md)

### Tools
- Monitoring: DataDog / New Relic
- Logging: CloudWatch / Log Analytics
- Secrets: AWS Secrets Manager / Azure Key Vault
- IaC: Terraform / CloudFormation

---

**Version:** 1.0  
**Last Updated:** January 24, 2026  
**Status:** Ready for Production
