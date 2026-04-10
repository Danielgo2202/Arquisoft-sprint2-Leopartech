# Reporte Técnico: Manejador de Reportes

Este documento formaliza la descripción técnica, arquitectónica y operativa del **Manejador de Reportes**. Este es el componente más complejo en cuanto a flujos de trabajo en segundo plano y actúa como la capa demostrativa principal para el Atributo de Calidad de **Escalabilidad (Experimento ASR17)**.

---

## 1. Arquitectura del Componente

A diferencia de un microservicio CRUD estándar, el Manejador de Reportes utiliza una arquitectura basada en eventos (Event-Driven Architecture) complementada con sistemas de orquestación de tareas en segundo plano.

### Componentes Internos Relevantes
1. **API Gateway (Gunicorn/Django):** Expone endpoints como `/events/batch` y `/reports`. Diseñado para estar libre de estado (stateless) para permitir escalabilidad horizontal elástica bajo un Load Balancer.
2. **Cola de Mensajería (Celery via RabbitMQ):** El corazón de la comunicación asincrónico. 
3. **Workers Node Pool (Autoscaling de Celery):** Conjunto de máquinas EC2 aprovisionadas (las instancias de recursos tipo `worker`) cuya única labor es estar suscritas silenciosamente a los _exchanges_ y consumir la carga pesada. Totalmente escalables mediante el parámetro `celery_worker_concurrency`.

Esta topología resuelve el requerimiento del SLA, que dicte que tareas lentas (más de 2s) deben ser desacopladas para mantener los sub-1.5s de latencia por batch en los endpoints del cliente, permitiendo picos masivos temporales de concurrencia (>500 requests/min).

---

## 2. Flujos de Comunicación y Dependencias

- **RabbitMQ (`amqp://`)**: Actúa como Broker. Intervienen ambos el exchange y las diferentes colas (`bite.eventos`, `bite.analisis`).
- **PostgreSQL (`reportes_db`)**: Almacena el histórico y estado de las analíticas generadas. 
- **Redis (`db/2` y `db/3`)**: `db/2` se usa para _Task Caching_ y `db/3` es empleado por Celery como *Result Backend* para rastrear qué tareas asíncronas han sido culminadas con éxito o error de forma ultrarrápida.
- **Provider SMTP (Notificaciones de Alerta):** Comunicación unidireccional por _email_ cuando una analítica ha sobrepasado los 2000 ms.

---

## 3. Análisis Profundo de la Lógica de Negocio

El componente crítico opera en la ingesta por lotes (`EventoBatchView`) y la correlación y generación estructurada de informes.

### 3.1. Recepción y Asignación de Idempotencia (API HTTP)
La ruta `POST /events/batch` recibe arreglos masivos de eventos (hasta 200 items por payload).
1. El sistema mapea cada evento dentro del payload a un `UUID` base de trazabilidad.
2. Llama a `procesar_evento_batch.apply_async(...)` dentro del _loop_ nativo sin hacer await en backend. Esto envía inmediatamente descriptores JSON (Celery Canvas) a RabbitMQ.
3. Se retorna un código HTTP dinámico (`202 Accepted` total, o `207 Multi-Status` parcial). Esto toma fracciones de milisegundos independientemente de si los eventos toman minutos en completarse por detrás.

### 3.2. Idempotencia del Worker (`IdempotencyService`)
Cuando el `Worker` reanuda la tarea enviada:
1. Lee su registro cruzado en el modelo `EventoEntrante`.
2. Como RabbitMQ solo garantiza entrega "At Least Once", pueden haber mensajes duplicados por reconexiones de la red. Si el método `is_already_processed()` devuelve `True`, el worker aborta gentilmente (Graceful Dropout). **Decisión de diseño**: Evita polución agresiva de la BD y previene re-lanzar flujos muy pesados de analítica si AWS hace un reintento de ALB pasivo.

### 3.3. Orquestación del Árbol de Ejecución Analítica
1. **Analisis -> EjecucionAnalisis -> Reporte -> Alerta -> Notificacíón.**
El Worker procesa esta cadena estrictamente secuencial y transaccional:
   - Se crea el contenedor base de los metadatos (`Analisis`).
   - Se abre un semáforo de tiempo (`EjecucionAnalisis`) en estado PENDIENTE.
   - El Worker se comunica teóricamente con la capa `manejador_cloud` (mediante API) para obtener las métricas y simula la agregación.
   - Todo lo computado se convierte en el JSON consolidado del modelo `Reporte`.
   - Si se supera el límite físico de costo, se dispara una `Alerta`.
2. **Evaluación Final de SLA Crítico:**
   Si la sustracción `(time.monotonic() - start_time) * 1000` > 2000 milisegundos, el sistema automáticamente comitea una tarea anidada para el Exchange `evento.notificacion` a través de un Publisher, provocando un correo de retraso administrado (cumplimiento mandatorio de la arquitectura de negocio).

---

## 4. Estructura de Datos (Modelos Base)

Los modelos que maneja están definidos en `events/models.py`.

- **`EventoEntrante`**: Tabla de transacciones con UUIDs inmutables para gestionar deduplicaciones.
- **`Analisis` & `EjecucionAnalisis`**: Modelos Relacionales. Una analítica puede tener múltiples ejecuciones si han ocurrido errores, es importante poder ver la línea de tiempo.
- **`Reporte`**: Archivo optimizado para JSON (Postgres JSONb Storage). **Decisión de Diseño Crítica:** Esto es necesario para que consultas del endpoint analíticas consuman menos de 100 ms bajo el índice cruzado de Proyectos. No normalizar este valor mantiene altos los _Read IOPS_ disminuyendo _Disk Time_.
- **`OportunidadAhorro` y `Alerta`**: Reglas desencadenantes de costo y desviaciones.
- **`Notificacion`**: Histórico auditado para comprobar que el Service Level Agreement con el cliente ha sido compensado debidamente, si correos asíncronos fallan o proceden.

---

## 5. Consideraciones Técnicas y Operativas

- **Tolerancia a Fallos Estricta (Acks Late):** Un aspecto vital en el código (`@shared_task(acks_late=True)`) dictamina que el sistema *nunca* removerá un mensaje de la cola de RabbitMQ hasta que el registro completo en PostgreSQL sea confirmado sin excepciones. Si un pod EC2 del Worker se destruye justo en medio de un computo, otro worker recogerá el evento en lugar de perderse por siempre.
- **Auto Scale de Threads & Concurrencia:** La escalabilidad horizontal viene de dictar el paralelismo prefijado. Dependiendo del ambiente, el contenedor pasará la directiva de Celery `concurrency`. Si la CPU alcanza > 85%, el esquema de AWS en un clúster de producción real instanciaría nuevas réplicas EC2 con las mismas credenciales al broker y drenarían la carga linealmente, una habilidad ausente en sistemas atados directamente (1-to-1).
