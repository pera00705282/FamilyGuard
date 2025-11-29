# Trading System Monitoring Guide

## 1. Monitoring System Health

### Key Dashboards

1. **Trading Overview**
   - Location: `/d/trading-dashboard`
   - Key Metrics:
     - Trades per minute
     - Strategy performance
     - Position sizing
     - Slippage and latency

2. **System Health**
   - Location: `/d/system-health`
   - Key Metrics:
     - CPU/Memory usage
     - Disk I/O
     - Network latency
     - Service status

3. **Alerting**
   - Location: `/alerting`
   - View and manage alerts
   - Configure notification policies

## 2. Reviewing Logs with Loki

### Common Log Queries

1. **View Recent Errors**
   ```logql
   {level="error"} | json | line_format "{{.message}}"
   ```

2. **Search for Specific Errors**
   ```logql
   {app=~"trading-.*"} |= "connection error" | json
   ```

3. **Monitor API Latency**
   ```logql
   {app="api"} | json | latency > 500ms
   ```

4. **Track User Activity**
   ```logql
   {app=~"api|auth"} | json | user_id!="" | line_format "{{.user_id}}: {{.message}}"
   ```

5. **Monitor Specific Strategy**
   ```logql
   {app="trading-engine"} | json | strategy="mean-reversion"
   ```

## 3. Alerting Configuration

### Alert Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| CPU Usage | > 80% | > 95% |
| Memory Usage | > 75% | > 90% |
| Trade Latency | > 500ms | > 1s |
| Error Rate | > 1% | > 5% |
| Drawdown | > 2% | > 5% |

### Alert Channels

1. **Email**
   - Configured for all alerts
   - Team distribution lists

2. **Slack**
   - Real-time notifications
   - Dedicated channels per team

3. **OpsGenie**
   - On-call rotations
   - Escalation policies

4. **SMS**
   - Critical alerts only
   - Phone number rotation

## 4. Performance Optimization

### Database Queries
```sql
-- Find slow queries
SELECT query, total_exec_time 
FROM pg_stat_statements 
ORDER BY total_exec_time DESC 
LIMIT 10;
```

### Memory Usage
```bash
# Monitor JVM memory
jstat -gcutil <pid> 1000

# Monitor Python memory
pip install memory_profiler
python -m memory_profiler your_script.py
```

## 5. Troubleshooting

### Common Issues

1. **High Latency**
   - Check database queries
   - Review external API calls
   - Monitor system resources

2. **Connection Issues**
   - Verify network connectivity
   - Check rate limits
   - Review firewall rules

3. **Data Inconsistencies**
   - Validate data pipelines
   - Check for missing data points
   - Verify data sources

## 6. Maintenance

### Daily Tasks
- Review alert history
- Check system metrics
- Validate backups

### Weekly Tasks
- Review and update dashboards
- Clean up old logs
- Update documentation

### Monthly Tasks
- Performance tuning
- Capacity planning
- Security review
