# Guía de Pruebas ASR2 – Seguridad (Integridad) con BurpSuite

## Contexto

Este experimento valida que el **100% de las comunicaciones externas** se realizan
mediante HTTPS (TLS) y que los datos transmitidos entre componentes son protegidos
con mecanismos de validación de integridad (HMAC-SHA256).

**Endpoints ASR2 implementados:**
- `GET  /security/tls-status`        → detecta HTTP vs HTTPS y registra el resultado
- `POST /security/integrity-check`   → verifica HMAC-SHA256 del payload
- `GET  /security/integrity-log`     → consulta el log de auditoría ASR2 (requiere token)

---

## Configuración en BurpSuite

- **Target Host:** `<TU_ALB_DNS>` (ej. `bite2-alb-XXXXX.us-east-1.elb.amazonaws.com`)
- **Port HTTP:** `80`
- **Port HTTPS:** `443`

---

## PRUEBA 1 – Solicitud HTTP es rechazada (resultado esperado: 400)

*Demuestra que el sistema discrimina tráfico no cifrado.*

```
GET /security/tls-status HTTP/1.1
Host: <TU_ALB_DNS>
```

**Resultado esperado:**
```json
HTTP/1.1 400 Bad Request
{
  "asr": "ASR2 - Seguridad (Integridad)",
  "resultado": "RECHAZADO",
  "protocolo": "HTTP",
  "mensaje": "Solicitud HTTP rechazada. El sistema requiere HTTPS...",
  "accion_requerida": "Use HTTPS en lugar de HTTP."
}
```
📸 *Captura de pantalla obligatoria — evidencia de rechazo HTTP.*

---

## PRUEBA 2 – Solicitud HTTPS es aceptada (resultado esperado: 200)

*Demuestra que el tráfico cifrado es procesado correctamente.*

Para esto en BurpSuite:
1. Cambia el Target al puerto `443` y activa HTTPS.
2. Envía la misma petición:

```
GET /security/tls-status HTTP/1.1
Host: <TU_ALB_DNS>
```

**Resultado esperado:**
```json
HTTP/1.1 200 OK
{
  "asr": "ASR2 - Seguridad (Integridad)",
  "resultado": "ACEPTADO",
  "protocolo": "HTTPS",
  "tls_version": "TLSv1.3",
  "cipher_suite": "ECDHE-RSA-AES128-GCM-SHA256",
  "mensaje": "Comunicacion cifrada. El 100% de las solicitudes externas se realizan mediante HTTPS (TLS)."
}
```
📸 *Captura de pantalla obligatoria — evidencia de aceptación HTTPS con versión TLS.*

---

## PRUEBA 3 – Verificación de integridad HMAC válida (resultado esperado: 200)

*Demuestra que el sistema puede verificar que los datos no fueron alterados en tránsito.*

Primero genera el HMAC en tu terminal local:
```bash
echo -n "datos-financieros-empresa-a" | openssl dgst -sha256 -hmac "bite-integrity-hmac-secret-change-in-production"
```
Copia el hash y úsalo en BurpSuite (puerto 443, HTTPS):

```
POST /security/integrity-check HTTP/1.1
Host: <TU_ALB_DNS>
Content-Type: application/json

{
  "payload": "datos-financieros-empresa-a",
  "hmac_sha256": "<HASH_GENERADO_ARRIBA>"
}
```

**Resultado esperado:**
```json
HTTP/1.1 200 OK
{
  "asr": "ASR2 - Seguridad (Integridad)",
  "resultado": "INTEGRIDAD_OK",
  "mensaje": "El hash HMAC-SHA256 coincide. Los datos no han sido alterados en transito."
}
```
📸 *Captura de pantalla obligatoria.*

---

## PRUEBA 4 – Intento de manipulación de datos (resultado esperado: 422)

*Simula un ataque Man-in-the-Middle donde el atacante altera el payload en tránsito.*

Envía el mismo endpoint pero con un HMAC incorrecto (simula datos alterados):

```
POST /security/integrity-check HTTP/1.1
Host: <TU_ALB_DNS>
Content-Type: application/json

{
  "payload": "datos-financieros-empresa-a-ALTERADOS-POR-ATACANTE",
  "hmac_sha256": "<HASH_DEL_PAYLOAD_ORIGINAL>"
}
```

**Resultado esperado:**
```json
HTTP/1.1 422 Unprocessable Entity
{
  "asr": "ASR2 - Seguridad (Integridad)",
  "resultado": "INTEGRIDAD_FALLO",
  "mensaje": "El hash HMAC-SHA256 NO coincide. Los datos pueden haber sido alterados en transito.",
  "alerta": "Posible manipulacion de datos detectada."
}
```
📸 *Captura de pantalla obligatoria — evidencia de detección de manipulación.*

---

## PRUEBA 5 – Log de auditoría ASR2 (resultado esperado: 200 con registros)

*Demuestra trazabilidad del 100% de verificaciones TLS/integridad.*

Primero obtén un token (ver guía ASR3), luego:

```
GET /security/integrity-log HTTP/1.1
Host: <TU_ALB_DNS>
Authorization: Bearer <TU_ID_TOKEN>
```

**Resultado esperado:**
```json
HTTP/1.1 200 OK
{
  "asr": "ASR2 - Seguridad (Integridad)",
  "total_registros": 4,
  "registros": [
    {
      "protocolo": "HTTP",
      "resultado": "rechazado",
      "endpoint": "/security/tls-status",
      ...
    },
    {
      "protocolo": "HTTPS",
      "resultado": "aceptado",
      ...
    }
  ]
}
```
📸 *Captura de pantalla obligatoria — evidencia de auditoría completa.*

---

## Resumen de Evidencias Requeridas

| # | Prueba | HTTP Status | Evidencia |
|---|--------|-------------|-----------|
| 1 | HTTP rechazado | `400 Bad Request` | `"resultado": "RECHAZADO"` |
| 2 | HTTPS aceptado | `200 OK` | `"tls_version": "TLSv1.3"` |
| 3 | HMAC válido | `200 OK` | `"resultado": "INTEGRIDAD_OK"` |
| 4 | HMAC inválido (ataque) | `422 Unprocessable Entity` | `"resultado": "INTEGRIDAD_FALLO"` |
| 5 | Log de auditoría | `200 OK` | registros de pruebas 1-4 |
