# Reporte Técnico: Manejador Cloud (Resource Service)

Este documento detalla la estructura, funcionalidad y lógica operativa subyacente del microservicio **Manejador Cloud**, el sistema responsable de vincular y unificar los datos métricos de infraestructura virtual provisionada a través de distintos proveedores.

---

## 1. Arquitectura del Componente

En el marco de nuestra arquitectura de microservicios, el Manejador Cloud es el componente estructural que aborda el **Bounded Context de Integración de Nube y Recursos Físicos.** Su diseño difiere de los otros manejadores ya que es un sistema con patrones centrados en lectura pesada y extensibilidad.

### Principios Fundamentales
1. **Punto Único de Verdad (Single Point of Truth):** Consolida en una sola base de datos (PostgreSQL `cloud_db`) todas las Cuentas Cloud, independientemente del proveedor de donde se extraigan.
2. **Read-Heavy Architecture con Resiliencia:** Como las rutas críticas del `manejador_usuarios` dependen de él para crear o enlazar proyectos, se expone un endpoint intermedio que es muy rápido de consultar o altamente dependiente de Redis (Caché).
3. **Pluggable & Extensible:** Mediante patrones de inyección de adaptadores, se orquesta el soporte de múltiples proveedores de Cloud (AWS configurado por defecto, Google Cloud Platform (GCP) opcional) sin modificar la capa modelo ni de vistas base.

---

## 2. Conexiones, Dependencias y Flujos de Comunicación

- **Redis (Caché - `db/1`):** El servicio exporta un API para la integración, pero a su vez proactiva y pasivamente alimenta la caché compartida de Redis para que otros servicios no bloqueen colapsando la base de datos principal de Cloud con queries validadores. El Redis asociado está configurado para _eviction policy allkeys-lru_.
- **Base de Datos (`cloud_db`):** Base de datos relacional para guardar proveedores, recursos individuales (como instancias, volúmenes) y el histórico de sus métricas de consumo en bruto.
- **Proveedores Públicos de Nube (APIs Externas como AWS CloudWatch/Cost Explorer):** A través de cron jobs nativos a nivel sistema operativo, o _Celery Beats_ (si está habilitado), el sistema hace requests asincrónicas a las APIs autorizadas para jalar datos actualizados sobre el consumo real de cada cuenta. Ninguna de estas integraciones ocurre en los endpoints síncronos HTTP.

---

## 3. Análisis Profundo de la Lógica de Negocio

La principal lógica de este sistema se concentra en las siguientes áreas de dominio:

### 3.1. Abstracción del Proveedor Multidominio (Adapter Pattern)

- **El Problema:** La métrica de CPU y tráfico de red en AWS se reportan de forma drásticamente distinta a GCP. Mantener ese control en la vista de consumo causaría código *Spaghetti*.
- **La Solución:** Se define una interfaz genérica `ICloudAdapter`. Las implementaciones concretas de este componente traducen los JSON específicos de cada proveedor a entidades normalizadas (`MetricaConsumo` o `RecursoCloud`). Esto permite a un desarrollador agregar un nuevo proveedor sin reescribir un solo controlador. 

### 3.2. Manejo de Consumos y Recolección (Data Ingestion)

Un flujo interno crítico recaba las métricas temporales de costo/consumo:
1. Puntero Histórico: Revisa la última marca de agua (timestamp) procesada en `cloud_db`.
2. _Pulling_: Descarga fragmentos de las APIs del proveedor.
3. Tratamiento Transaccional: Empuja los registros al modelo `MetricaConsumo`.
   
Este modelo es lo que usa posteriormente el **Manejador de Reportes** para sus analíticas simuladas, permitiendo que la persistencia pesada (los miles de data points puros de una sola instancia EC2) resida aquí en el backend del dominio de Cloud, y no sobrecargue la base de Reportes que es agregativa.

### 3.3. Validación Externa Resiliente (Síncrono para `manejador_usuarios`)

El endpoint `GET /cloud-resources/accounts/:uuid/validate` se debe mantener altamente disponible (ASR16). 
- Si un request solicita validar, el servicio evalúa la entidad en la base de datos.
- A diferencia de arquitecturas acopladas de base de datos directas, se protege a través del framework de Django usando el patrón de consulta rápida (Index Scan primario) ya que el `uuid` se utiliza estratégicamente en índices compuestos.

---

## 4. Estructura de Datos (Modelos)

- **`ProveedorCloud`**: Constantes semánticas (AWS, GCP, AZURE).
- **`CuentaCloud`**: Agrupa y representa un entorno o VPC real vinculado y autenticado al proveedor. Se usa en el payload JSON durante pruebas de rendimiento para generar la asociación cruzada.
- **`RecursoCloud`**: El recurso específico facturado (Ej. i-0abcd1234, vol-ffff987). Contiene descripciones vitales del _hardware_ o servicio paas real desplegado.
- **`MetricaConsumo`**: Registro de serie de tiempo (Timeseries Data). Maneja datos volumétricos masivos (costos de horas, capacidades porcentuales usadas). 

---

## 5. Consideraciones Técnicas y Operativas

1. **Cuello de Botella de Ingestión:** Al depender de integraciones externas, las APIs de los proveedores de la nube aplican Throttling fuerte (RATE LIMITS). La recolección de los datos de metricas (`MetricaConsumo`) **debe** manejarse asíncronamente con manejos robustos y colas exponenciales. 
2. **Separación de Responsabilidades Estricta:** Este servicio recaba la data bruta y dice "A las 12 PM de hoy, se usaron $5 USD de este servidor". **No hace estimaciones matemáticas complejas ni identifica picos de desperdicio.** Eso es tarea del **Manejador de Reportes**, logrando un control desacoplado (Clean Architecture).
3. **Privacidad de Subred Virtual (VPC):** Este manejador no está visible públicamente en el ALB principal (`aws_lb_listener_rule`). Solo puede enrutarse de forma indirecta, limitando su superficie de ataque significativamente lo que satisface atributos arquitectónicos de seguridad profunda.
