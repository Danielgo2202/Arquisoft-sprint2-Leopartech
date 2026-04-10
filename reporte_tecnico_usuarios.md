# Reporte Técnico: Manejador de Usuarios

Este documento describe la arquitectura, lógica de negocio y detalles de configuración del **Manejador de Usuarios**, componente central de la plataforma de BITE.co. Está diseñado para nuevos desarrolladores y para referencias operacionales.

---

## 1. Arquitectura del Componente

El **Manejador de Usuarios** es un microservicio construido sobre Django (Python) que actúa como el entrypoint principal para las operaciones de gestión de clientes (empresas), proyectos, presupuestos y empleados.

### Patrón Arquitectónico
Sigue una arquitectura basada en capas tradicional dentro del marco de Django (Model-View-Controller / Model-View-Template, ajustado a APIs REST con Django Rest Framework):
1. **Capa de Transporte (Views):** Expone los endpoints RESTFul (`POST /projects`, etc.).
2. **Capa de Negocio (Services):** Contiene las reglas estrictas, como `ProyectoService` (en `projects/services.py`). Extrae la lógica compleja de las vistas para permitir su reutilización y testabilidad.
3. **Capa de Integración Cliente (Clients):** Implementa el patrón _Adapter/HTTP Client_ (e.g. `ResourceServiceClient`) para interactuar con otros microservicios.
4. **Capa Asíncrona (Publishers):** Aisla y maneja la publicación de mensajes hacia brokers (RabbitMQ).

### Soporte a Escenarios Arquitectónicos
El sistema está optimizado para soportar el Experimento de Latencia (ASR16). Para cumplir el SLA de ≤ 100 ms:
- Interpone una caché **Redis** para evitar consultas sincrónicas penalizantes a través de HTTP.
- Utiliza **RabbitMQ** en un esquema de *Fire-and-Forget* para desacoplar el procesamiento pesado de reportes o la generación de metadatos subsiguientes.

---

## 2. Conexiones, Dependencias y Flujos de Comunicación

El Manejador de Usuarios tiene tres dependencias estructurales principales:

1. **Base de Datos Dedicada (PostgreSQL `usuarios_db`):** 
   - Mantiene un contexto acotado (Bounded Context) sobre la gestión de identidad corporativa y financiera del proyecto. Aislada de consumos de nube o facturación.
   
2. **Manejador Cloud (Vía HTTP y Caché):**
   - **Flujo Principal (Caché - Redis `db/1`):** Cuando se crea un proyecto, se requiere validar si la cuenta cloud vinculada (ej. un account de AWS) existe y es válida. Para evitar un salto de red HTTP que penalice la latencia, el servicio revisa primero la caché compartida de Redis (`cloud_acct_<id>`).
   - **Flujo de Respaldo (Síncrono - HTTP `8002`):** Si hay un _cache miss_, se realiza un request HTTP directo a `manejador_cloud` a través de la red interna de la VPC (`http://manejador-cloud:8002/cloud-resources/accounts/...`).

3. **Manejador de Reportes (Vía AMQP - RabbitMQ):**
   - **Flujo Asíncrono:** Una vez el proyecto es creado y existosamente persistido en PostgreSQL, se debe notificar al subsistema de Reportes. El `ProyectoEventPublisher` (en `projects/publisher.py`) inyecta un mensaje JSON en el exchange `bite_events` con la _routing key_ `proyecto.creado`.

---

## 3. Análisis Profundo de la Lógica de Negocio

El centro operativo de este microservicio es la **Creación de Proyectos**, el cual impacta directamente en el presupuesto y la medición de costos a futuro.

### 3.1. Flujo de `crear_proyecto` (`ProyectoService`)

Cuando entra un `POST /projects` con el payload de creación, se ejecuta la siguiente cadena de responsabilidades:

1. **Recuperación de la Entidad `Empresa`:**  
   Se valida en PostgreSQL (`usuarios_db`) que la empresa proporcionada exista (`empresa_id`). Las empresas son objetos fundamentales que agrupan los recursos financieros de un inquilino (Tenant). Si no existe, se lanza `EmpresaNoEncontrada`.

2. **Validación de Cuentas Cloud (`ResourceServiceClient`):**
   Antes de aceptar un proyecto, la plataforma asegura que las instancias de la nube que se van a monitorear existan en el Manejador Cloud.
   - Iterativamente revisa las cuentas cloud pasadas en el payload.
   - Aplica el patrón **Fail-Closed**: Si el Manejador Cloud da timeout o rechaza la conexión, y no hay caché, la creación del proyecto falla, devolviendo `CloudServiceUnavailable`. **Decisión de Diseño:** Consistencia sobre disponibilidad; la plataforma no permite enlazar cuentas subyacentes 'fantasma'.

3. **Persistencia Transaccional (ACID):**
   - Se emplea el bloque `transaction.atomic()` de Django.
   - Esto garantiza que tanto el modelo de `Proyecto`, las relaciones locales `CuentaCloudRef` y el `Presupuesto` se guarden como una única operación fundamental. Si el presupuesto falla, ni el proyecto ni la referencia a la cuenta son confirmados (rollback).

4. **Publicación del Evento y Compleción:**
   - Una vez el commit se da en la base de datos, llama al event publisher a RabbitMQ.
   - **Decisión de Diseño Crítica:** Si falla el broker de RabbitMQ y no se puede hacer ACK del mensaje publicado, el sistema **no revierte** el proyecto. Prefiere lanzar un _soft error_ interno, manteniendo la respuesta 201 Created al frontend o usuario (debido al compromiso de latencia).

---

## 4. Estructura de Datos (Modelos)

Los modelos (`projects/models.py`) implementan la arquitectura de la base de datos (Bounded Context: Gestión de Usuarios):

- **`Empresa`:** Modelo raíz que representa un tenant.
- **`Empleado`:** Representa un usuario autorizado con un rol dentro de una empresa.
- **`Proyecto`:** Unidad lógica que agrupa los gastos cloud. Asociado a 1 `Empresa` y 1 `Presupuesto`.
- **`CuentaCloudRef`:** Mapeo relacional de IDs (UUIDs) que apuntan virtualmente al Bounded Context de infraestructura, manejado en su respectiva base de datos remota (`cloud_db`).
- **`Presupuesto`:** Modelo financiero que define el monto (`monto_mensual`) y moneda. Guarda el porcentaje de alerta para notificaciones activadas por triggers de costo (`alerta_porcentaje`).

---

## 5. Consideraciones Técnicas y Operativas

- **Supuesto de Migraciones Temporales (Seeds):** Dada la dependencia arquitectónica exigente del ID de la Empresa, es mandatorio que la entidad exista *previamente*. En entornos limpios o experimentos de JMeter, se inyectan `UUIDs` fijos usando semillas SQL (`user_data` en Terraform - `seed_users_company.sql`). Sin esto, las peticiones HTTP reportarán error lógico y no de capa.
- **Evitación de Acoplamiento de Red Limitante:** Se optó por una abstracción mediante `CuentaCloudRef`. Físicamente, el manejador de usuarios *nunca* mantiene el estado de qué máquinas EC2 existen en realidad. Solo posee un puntero lógico que indica "Este Proyecto agrupa los costos de la Cuenta Cloud XYZ", lo cual simplifica la limpieza y orquestación de datos si una cuenta cloud es terminada en AWS independientemente.
- **Retos de Observabilidad:** Al ser asíncrono hacia métricas, un fracaso del RabbitMQ se convierte en un _silent failure_ para el registro de auditoría de reportes si no se expone debidamente a herramientas de monitoreabilidad o si ocurren problemas de red. Recomendable para integraciones en CI/CD el chequeo del path `/health` que incluye el status del broker local.
