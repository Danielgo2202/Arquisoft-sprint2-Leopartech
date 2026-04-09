# BITE.co – Cloud Cost Management Platform

> Business & IT Transformation Experts – Centralized Cloud Cost Management and Optimization Platform  
> Architecture reference: `architecture.md` | Business context: `context.md`

---

## Architecture Overview

Three Django microservices following the architecture defined in `architecture.md §2-3`:

| Service | Port | Component (architecture.md) | Database |
|---|---|---|---|
| `manejador_usuarios` | 8001 | Gestión de Usuarios (Empresa, Proyecto, Presupuesto) | `usuarios_db` |
| `manejador_cloud` | 8002 | Manejador de Cloud (ProveedorCloud, CuentaCloud, RecursoCloud, MetricaConsumo) | `cloud_db` |
| `manejador_reportes` | 8003 | Procesador de Eventos + Análisis y Reportes | `reportes_db` |

### Supporting Infrastructure

| Component | Technology | Port |
|---|---|---|
| PostgreSQL (×3) | postgres:15 | 5432 (internal) |
| Redis (ElastiCache) | redis:7 | 6379 (internal) |
| RabbitMQ (AMQP) | rabbitmq:3.12 | 5672 + 15672 (mgmt) |
| Celery Worker Pool | `reportes_worker` × 2 | — |
| pika Consumer | `reportes_consumer` | — |

---

## Quality Attribute Targets (architecture.md §6)

| Attribute | Requirement | Mechanism |
|---|---|---|
| Performance | Reports ≤ 100 ms | Redis cache (ElastiCache) + indexed queries |
| Scalability | ≥ 5,000 concurrent users; peaks 12,000 × 10 min | RabbitMQ + auto-scaling Celery worker pool |
| Availability | No degradation during peaks | AWS ALB + stateless services |
| Async Processing | Analyses > 2 s → background + email | AMQP queue + Procesador de Eventos |
| Security | 100% unauthorized access blocked | Manejador de Seguridad (not implemented in MVP) |
| Extensibility | New cloud providers without code changes | Adapter pattern in `ProveedorCloud.tipo` |

---

## Event Flow

### Project Creation (`POST /projects`)

```
Client → manejador_usuarios (8001)
  1. Validate Empresa     → Redis cache → PostgreSQL fallback
  2. Validate CuentaCloud → Redis cache → manejador_cloud HTTP fallback
  3. INSERT Proyecto + CuentaCloudRef + Presupuesto  (DB transaction)
  4. Background thread publishes proyecto.creado → RabbitMQ bite_events
  5. HTTP 201 returned to client  ← non-blocking (≤100 ms target)

RabbitMQ → reportes_consumer → Celery task: procesar_proyecto_creado
  → Creates Analisis
  → Schedules ejecutar_analisis task
  → If duration > 2 s: queues enviar_notificacion (email)
```

### Batch Events (`POST /events/batch`)

```
Client → manejador_reportes (8003)
  1. Validate JSON (1–200 events)
  2. For each event: procesar_evento_batch.apply_async() → Celery
  3. HTTP 202 Accepted returned immediately

reportes_worker routes each event:
  - proyecto_creado     → procesar_proyecto_creado task
  - reporte_solicitado  → generar_reporte task (queue: reportes)
  - others              → logged and skipped
```

### Event Schema

```json
{
  "evento": "proyecto_creado",
  "version": "1.0",
  "source": "manejador_usuarios",
  "data": {
    "proyecto_id": "uuid",
    "nombre": "string",
    "empresa_id": "uuid",
    "estado": "ACTIVO",
    "cuentas_cloud": ["uuid", "uuid"],
    "creado_en": "ISO 8601"
  }
}
```

**Idempotency**: `EventoEntrante.evento_id` (UNIQUE index). Duplicate events are detected and skipped.

---

## Local Setup

### Prerequisites

- Docker ≥ 24
- Docker Compose ≥ 2.20

### Start All Services

```bash
cd arquisoft

# Copy environment files
cp manejador_usuarios/.env.example manejador_usuarios/.env
cp manejador_cloud/.env.example manejador_cloud/.env
cp manejador_reportes/.env.example manejador_reportes/.env

# Build and start everything
docker compose up --build

# Verify health
curl http://localhost:8001/health   # manejador_usuarios
curl http://localhost:8002/health   # manejador_cloud
curl http://localhost:8003/health   # manejador_reportes
```

RabbitMQ Management: http://localhost:15672 (user: `bite`, pass: `bite_pass`)

### Seed Test Data

```bash
# Create Empresa
docker compose exec manejador_usuarios python manage.py shell -c "
from projects.models import Empresa
from projects.cache import EmpresaCache
e = Empresa.objects.create(
    id='550e8400-e29b-41d4-a716-446655440001',
    nombre='Empresa BITE Demo', nit='900123456-1', activa=True
)
EmpresaCache.set(str(e.id), {'activa': True, 'nombre': e.nombre})
print('Created:', e.id)
"

# Create CuentaCloud records in manejador_cloud
docker compose exec manejador_cloud python manage.py shell -c "
from resources.models import ProveedorCloud, CuentaCloud
from resources.cache import CuentaCloudCache
aws = ProveedorCloud.objects.get(tipo='AWS')
ids = ['550e8400-e29b-41d4-a716-446655440011', '550e8400-e29b-41d4-a716-446655440012']
for uid in ids:
    c = CuentaCloud.objects.create(
        id=uid, nombre=f'Cuenta AWS Demo {uid[-4:]}', proveedor=aws,
        proyecto_id='550e8400-e29b-41d4-a716-446655440099',
        account_external_id=f'123456789{uid[-3:]}', activa=True
    )
    CuentaCloudCache.set_validation(uid, True)
    print('Created:', c.id)
"
```

### Quick Test

```bash
# Create a project
curl -s -X POST http://localhost:8001/projects \
  -H "Content-Type: application/json" \
  -d @experiments/data/projects_payload.json | python -m json.tool

# Submit event batch
curl -s -X POST http://localhost:8003/events/batch \
  -H "Content-Type: application/json" \
  -d @experiments/data/events_batch.json | python -m json.tool
```

---

## Running JMeter Tests

```bash
cd experiments
mkdir -p results

# Latency test (Experiment B – architecture.md §4.2)
# Tests POST /projects on manejador_usuarios (port 8001)
jmeter -n -t latency_test.jmx -l results/latency.jtl -e -o results/latency_html

# Scalability test (Experiment A – architecture.md §4.1)
# Tests POST /events/batch on manejador_reportes (port 8003)
jmeter -n -t scalability_test.jmx -l results/scalability.jtl -e -o results/scalability_html
```

See `experiments/README.md` for full details including distributed testing and AWS deployment.

---

## API Reference

### manejador_usuarios (port 8001)

| Method | Path | Description |
|---|---|---|
| `POST` | `/projects` | Create Proyecto (validates Empresa + CuentaCloud, publishes evento) |
| `GET` | `/health` | Health check (DB + Redis) |

### manejador_cloud (port 8002)

| Method | Path | Description |
|---|---|---|
| `GET` | `/cloud-accounts` | List CuentaCloud |
| `POST` | `/cloud-accounts` | Create CuentaCloud |
| `GET` | `/cloud-accounts/{id}` | Get CuentaCloud detail |
| `GET` | `/cloud-accounts/{id}/validate` | Validate account is active (called by manejador_usuarios) |
| `DELETE` | `/cloud-accounts/{id}` | Deactivate CuentaCloud |
| `GET` | `/resources?cuenta_id=<uuid>` | List RecursoCloud (Redis-cached) |
| `POST` | `/resources` | Create RecursoCloud |
| `GET` | `/resources/{id}` | Get RecursoCloud detail (Redis-cached) |
| `POST` | `/metrics` | Record MetricaConsumo |
| `GET` | `/health` | Health check (DB + Redis) |

### manejador_reportes (port 8003)

| Method | Path | Description |
|---|---|---|
| `POST` | `/events/batch` | Submit 1–200 events (async, HTTP 202) |
| `GET` | `/analytics?proyecto_id=<uuid>` | List Analisis |
| `GET` | `/reports?proyecto_id=<uuid>` | List Reportes |
| `GET` | `/health` | Health check (DB + Redis + RabbitMQ) |

---

## Domain Model (architecture.md §5)

```
Gestión de Usuarios     → manejador_usuarios:   Empresa, Proyecto, CuentaCloudRef, Presupuesto
Cloud                   → manejador_cloud:       ProveedorCloud, CuentaCloud, RecursoCloud, MetricaConsumo
Análisis y Reportes     → manejador_reportes:    Analisis, EjecucionAnalisis, Reporte, Alerta,
                                                 OportunidadAhorro, Notificacion, EventoEntrante
Seguridad               → (future service):      EventoSeguridad, RegistroAuditoria,
                                                 PoliticaAcceso, EvidenciaAcceso
```

---

## AWS Deployment

1. **Container Registry**: Push images to ECR
   ```bash
   docker tag manejador_usuarios:latest <account>.dkr.ecr.us-east-1.amazonaws.com/bite/manejador_usuarios:latest
   docker tag manejador_cloud:latest <account>.dkr.ecr.us-east-1.amazonaws.com/bite/manejador_cloud:latest
   docker tag manejador_reportes:latest <account>.dkr.ecr.us-east-1.amazonaws.com/bite/manejador_reportes:latest
   ```

2. **Databases**: RDS PostgreSQL Multi-AZ
   - `usuarios_db` → manejador_usuarios
   - `cloud_db` → manejador_cloud
   - `reportes_db` → manejador_reportes

3. **Cache**: ElastiCache Redis (cluster mode for ≥ 5,000 users)

4. **Message Broker**: Amazon MQ for RabbitMQ

5. **Services**: ECS Fargate with ALB
   - `manejador_usuarios`, `manejador_cloud`, `manejador_reportes` → target group per service
   - `reportes_worker` → auto-scaling ECS service (scale on RabbitMQ queue depth)
   - `reportes_consumer` → single ECS task

6. **Secrets**: AWS Parameter Store / Secrets Manager (replace `.env.example` values)

7. **Logging**: CloudWatch Logs (JSON format already configured)

8. **Scaling the Worker Pool (architecture.md §4.1)**:
   Scale `reportes_worker` replicas based on `bite.proyectos` queue depth via CloudWatch custom metric.

---

## Assumptions Made

1. Security service (Manejador de Seguridad) is out of scope for this MVP.
2. `CuentaCloudRef` in `manejador_usuarios` is a cross-service reference by UUID — standard microservices approach.
3. `ResourceServiceClient` uses **fail-open** policy (if `manejador_cloud` is down, validation passes) to prioritize availability.
4. Email uses `console` backend in development. Set `EMAIL_HOST_PASSWORD` for SendGrid/SES in production.
5. `initial_providers.json` fixture seeds AWS and GCP `ProveedorCloud` records on first deploy.
