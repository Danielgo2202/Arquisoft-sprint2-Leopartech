#!/bin/bash
echo "=== 1. Rebuild ==="
docker compose down -v
docker compose up --build -d

echo "=== 2. Wait 30s ==="
sleep 30
docker compose ps

echo "=== 3. Health checks ==="
curl -s http://localhost:8001/health
echo ""
curl -s http://localhost:8002/health
echo ""
curl -s http://localhost:8003/health
echo ""

echo "=== 4. Verify seed data ==="
docker compose exec manejador_cloud python3 manage.py shell -c "from resources.models import CuentaCloud; print(list(CuentaCloud.objects.values('id','activa')))"

echo "=== 5. Verify the validate endpoint ==="
curl -s http://localhost:8002/cloud-accounts/550e8400-e29b-41d4-a716-446655440011/validate
echo ""

echo "=== 6. Test ASR16 ==="
curl -s -w "\nHTTP_STATUS:%{http_code}\n" -X POST http://localhost:8001/projects \
  -H "Content-Type: application/json" \
  -d @experiments/data/projects_payload.json

echo "=== 7. Check manejador_usuarios logs ==="
docker compose logs manejador_usuarios | tail -50

echo "=== 8. Test ASR17 ==="
curl -s -w "\nHTTP_STATUS:%{http_code}\n" -X POST http://localhost:8003/events/batch \
  -H "Content-Type: application/json" \
  -d @experiments/data/events_batch.json

echo "=== 9. Verify Celery worker ==="
docker compose logs reportes_worker | grep -A10 "queues"

echo "=== 10. Check reportes logs ==="
docker compose logs manejador_reportes | tail -30
