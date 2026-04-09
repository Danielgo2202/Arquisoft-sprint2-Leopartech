# Enunciado del Caso – BITE.co
**Ingeniería de Sistemas y Computación (ISIS) – Arquitectura de Software**
**Universidad de los Andes**

**Presentado por:** Cristhian Camilo Medina Solano
**Contacto:** cristhian.medinas@bitesas.com.co | (319) 702-7893

---

## Presentación General de la Empresa

**Business & IT Transformation Experts – BITE.co** es una firma de consultoría tecnológica especializada en diseñar, optimizar y operar arquitecturas de TI para organizaciones que dependen de plataformas críticas. Atiende la necesidad creciente del mercado de contar con sistemas estables, escalables y eficientes, especialmente en sectores donde los fallos tecnológicos afectan directamente la operación y los ingresos.

Su propuesta de valor se centra en intervenciones prácticas y medibles: diagnósticos rápidos, correcciones focalizadas y acompañamiento operativo. Garantiza continuidad del negocio, reducción de incidentes, mejora de tiempos de respuesta y control del gasto en la nube, mientras transfiere capacidades al equipo del cliente para asegurar autonomía y sostenibilidad tecnológica.

### Pilares del Portafolio de Servicios

1. **Estrategia y madurez**
2. **Optimización y costos en la nube**
3. **IA para el negocio**
4. **Operación y resiliencia**

Los servicios incluyen: diagnóstico de madurez, gestión FinOps, automatización con IA, desarrollo y modernización de aplicaciones, arquitectura corporativa, analítica estratégica, soporte 24/7, continuidad de negocio y procesos de adopción tecnológica.

---

## Problema

Las organizaciones enfrentan un incremento sostenido e ineficiente en los costos de nube debido a la falta de visibilidad, control y gobernanza sobre sus recursos cloud. Indicadores clave del problema:

- Entre el **20 % y el 50 %** del gasto en nube es desperdicio.
- El **84 %** de las empresas tiene dificultades para gestionar el gasto cloud.
- El desperdicio global proyectado para 2025 supera los **US $44.5 mil millones**.

Este problema se agrava en entornos híbridos y multicloud, donde existen:

- Recursos sobredimensionados e instancias inactivas.
- Datos retenidos sin propósito y ausencia de etiquetado.
- Desconexión constante entre equipos técnicos y financieros.

Lo anterior deriva en sobrecostos inesperados, mala planeación presupuestaria y menor retorno de inversión.

---

## Reto

Diseñar y construir una **plataforma centralizada de gestión y optimización del uso de nube** que permita a múltiples empresas visualizar, analizar y controlar sus costos y consumos en tiempo casi real.

### Integraciones requeridas

- **AWS** – obligatorio
- **GCP** – opcional

### Requerimientos de Escalabilidad y Rendimiento

| Atributo | Valor |
|---|---|
| Usuarios concurrentes sostenidos | ≥ 5.000 |
| Picos de usuarios concurrentes | hasta 12.000 (ventanas de hasta 10 min) |
| Tiempo máximo de generación de reportes mensuales | 100 ms |
| Umbral para ejecución en segundo plano | > 2 segundos |

### Capacidades Funcionales

- Visualización, análisis y control de costos y consumos en tiempo casi real.
- Generación de reportes mensuales de gasto por cliente, área o proyecto (≤ 100 ms).
- Consulta y consolidación del consumo de recursos cloud (costos y capacidad de cómputo) por empresa y proyecto.
- Identificación de recursos infrautilizados y patrones de desperdicio económico.
- Ejecución en segundo plano con notificación por correo electrónico cuando el análisis supere los 2 segundos.

### Capacidades No Funcionales y de Arquitectura

- **Extensibilidad:** Mecanismo para extraer información de cualquier nube sin modificar el código existente.
- **Seguridad:** Detección y bloqueo del **100 %** de los accesos no autorizados, con registro de evidencia para auditoría y alertas a los responsables de cada empresa.


