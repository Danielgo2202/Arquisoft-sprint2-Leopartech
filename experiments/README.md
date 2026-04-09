# BITE.co – JMeter Experiments

## Architecture Reference

- **Experiment A (Scalability)** → architecture.md §4.1 — Green elements
- **Experiment B (Latency)**    → architecture.md §4.2 — Blue elements

---

## Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| Apache JMeter | ≥ 5.6 | Test runner |
| Docker + Docker Compose | ≥ 24 | Service stack |
| Java | ≥ 11 | Required by JMeter |

---

## 1. Start Services

```bash
cd /path/to/arquisoft
docker compose up --build -d

# Verify all services are healthy
docker compose ps
curl http://localhost:8001/health   # proyecto_service
curl http://localhost:8002/health   # recurso_service
curl http://localhost:8003/health   # evento_service
```

Wait ~30 seconds for migrations to complete and all health checks to pass.

---

## 2. Seed Required Data

Before running latency tests you need an `Empresa` and two `CuentaCloud` records:

```bash
# Create Empresa (ID matches projects_payload.json)
curl -s -X POST http://localhost:8001/projects \
  -H "Content-Type: application/json" \
  -d '{"nombre":"BITE Demo","descripcion":"Seed empresa"}' || true

# Create ProveedorCloud AWS in recurso_service
curl -s http://localhost:8002/cloud-accounts?proyecto_id=test || true

# Manually seed via Django shell if needed:
docker compose exec proyecto_service python manage.py shell -c "
from projects.models import Empresa
from projects.cache import EmpresaCache
e = Empresa.objects.create(
    id='550e8400-e29b-41d4-a716-446655440001',
    nombre='Empresa BITE Demo',
    nit='900123456-1',
    activa=True
)
EmpresaCache.set(str(e.id), {'activa': True, 'nombre': e.nombre})
print('Empresa created:', e.id)
"

# Seed CuentaCloud in resource_service
docker compose exec recurso_service python manage.py shell -c "
from resources.models import ProveedorCloud, CuentaCloud
aws = ProveedorCloud.objects.get(tipo='AWS')
from resources.cache import CuentaCloudCache
for uid in ['550e8400-e29b-41d4-a716-446655440011', '550e8400-e29b-41d4-a716-446655440012']:
    c = CuentaCloud.objects.create(
        id=uid, nombre=f'Cuenta {uid[-4:]}', proveedor=aws,
        proyecto_id='550e8400-e29b-41d4-a716-446655440099',
        account_external_id=f'aws-{uid[-4:]}', activa=True
    )
    CuentaCloudCache.set_validation(uid, True)
    print('Created:', c.id)
"
```

---

## 3. Run Latency Test (Experiment B)

```bash
cd experiments

# Create results directory
mkdir -p results

# Normal load (10 users)
jmeter -n -t latency_test.jmx \
  -Jjmeter.reportgenerator.overall_granularity=1000 \
  -l results/latency_run.jtl \
  -e -o results/latency_report

# Or with custom host/port
jmeter -n -t latency_test.jmx \
  -JHOST=localhost \
  -JPORT=8001 \
  -l results/latency_run.jtl
```

### Expected Results

| Metric | Target | Architecture Requirement |
|---|---|---|
| Average latency | ≤ 400 ms | architecture.md §6 Performance ≤ 100 ms (report generation) |
| P95 latency | ≤ 500 ms | JMeter assertion |
| Error rate | 0% | All requests must return HTTP 201 |
| Throughput | ≥ 100 req/s | 10 users × 20 loops ÷ 10 s ramp |

---

## 4. Run Scalability Test (Experiment A)

```bash
cd experiments
mkdir -p results

# Ramp test (50 → 500 users, 30s ramp-up)
jmeter -n -t scalability_test.jmx \
  -JHOST=localhost \
  -JPORT=8003 \
  -l results/scalability_run.jtl \
  -e -o results/scalability_report
```

To run the full peak test (5000 users, 10 min sustained) enable the second thread group in `scalability_test.jmx` (set `enabled="true"`) and use a distributed JMeter setup:

```bash
# On JMeter server nodes (repeat per server):
jmeter-server -Djava.rmi.server.hostname=<SERVER_IP>

# On controller:
jmeter -n -t scalability_test.jmx \
  -R <SERVER1_IP>,<SERVER2_IP> \
  -JHOST=<ALB_DNS_OR_IP> \
  -JPORT=80 \
  -l results/peak_run.jtl
```

### Expected Results

| Metric | Target | Architecture Requirement |
|---|---|---|
| Throughput | ≥ 500 events/min | architecture.md §6 Scalability |
| Latency per batch (50 events) | ≤ 1,500 ms | JMeter assertion |
| Error rate | 0% | No failed requests |
| Concurrent users sustained | ≥ 5,000 | architecture.md §5 Scalability |
| Peak burst | 12,000 for 10 min | Worker Pool auto-scaling |

---

## 5. Validate Quality Attributes

### Performance (≤ 100 ms report generation)

The Redis caching strategy ensures report reads return in ≤ 100 ms:

```bash
# Verify Redis hit rate after warm-up
docker compose exec redis redis-cli info stats | grep keyspace_hits
docker compose exec redis redis-cli info stats | grep keyspace_misses
```

### Scalability (≥ 5,000 concurrent users)

Scale Celery workers horizontally:

```bash
docker compose up --scale evento_worker=4 -d
```

Monitor RabbitMQ queue depth:
- Management UI: http://localhost:15672 (user: bite / pass: bite_pass)
- Queue `bite.proyectos` should drain quickly with more workers.

### Event Flow Verification

```bash
# Watch RabbitMQ messages
docker compose logs -f evento_consumer

# Watch Celery task execution
docker compose logs -f evento_worker

# Check processed events in DB
docker compose exec evento_service python manage.py shell -c "
from events.models import EventoEntrante, Analisis
print('Processed events:', EventoEntrante.objects.filter(procesado=True).count())
print('Analyses created:', Analisis.objects.count())
"
```

---

## 6. Interpret JMeter Results

After each test run, open the HTML report:

```bash
open results/latency_report/index.html
open results/scalability_report/index.html
```

Key tabs to check:
- **Statistics** → Average, P90, P95, P99, Error%
- **Over Time** → Latency trend during ramp-up
- **Throughput** → Requests/sec

CSV files in `results/` can be imported into Excel or Grafana for further analysis.

---

## 7. AWS Deployment Notes

### Environment Variables

Replace `.env.example` values:

```bash
# Per service, set in ECS Task Definition or Parameter Store
SECRET_KEY=<long-random-string>
DB_HOST=<rds-endpoint>.rds.amazonaws.com
REDIS_URL=redis://<elasticache-endpoint>:6379/0
RABBITMQ_URL=amqps://bite:<pass>@<mq-broker>.mq.us-east-1.amazonaws.com:5671
RESOURCE_SERVICE_URL=http://<internal-alb-dns>
```

### ECS / EC2 Considerations

1. **proyecto_service**, **recurso_service**, **evento_service** → ECS Fargate tasks behind an ALB
2. **evento_worker** → ECS service with auto-scaling policy based on RabbitMQ queue depth (CloudWatch custom metric via RabbitMQ HTTP API)
3. **evento_consumer** → single ECS task (one consumer per queue) or use SQS as managed alternative
4. **Redis** → AWS ElastiCache (cluster mode disabled for simple setup, enabled for ≥ 5,000 users)
5. **RabbitMQ** → Amazon MQ for RabbitMQ (managed, HA)
6. **PostgreSQL** → Amazon RDS PostgreSQL Multi-AZ per service

### Scaling the Worker Pool (architecture.md §4.1)

```json
{
  "scalingPolicy": {
    "targetValue": 100,
    "customMetricSpec": {
      "metricName": "RabbitMQMessagesReady",
      "namespace": "BITE/RabbitMQ",
      "statistic": "Average"
    }
  }
}
```

### Logging (CloudWatch)

All services use JSON log format compatible with CloudWatch Logs Insights:

```
fields @timestamp, levelname, message, name
| filter levelname = "ERROR"
| sort @timestamp desc
```
