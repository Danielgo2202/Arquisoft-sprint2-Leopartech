# Architecture Document – BITE.co Cloud Cost Management Platform
**Ingeniería de Sistemas y Computación (ISIS) – Arquitectura de Software**
**Universidad de los Andes**

---

## 1. Overview

This document describes the software architecture of the centralized cloud cost management and optimization platform developed for BITE.co. The architecture is organized in three levels: **Component Architecture**, **Deployment Architecture**, and **Domain Model**. The system follows a **microservices** architectural style, complemented by an event-driven messaging layer for asynchronous processing.

---

## 2. Level 1 – Component Architecture

### 2.1 Architectural Style

The platform is built as a **microservices** system. Each manager (manejador) is an independently deployable service with a well-defined responsibility. Services communicate through explicit interfaces (Linkage connectors) and shared infrastructure components such as cache and message queues.

### 2.2 Components

#### User-Facing

| Component | Description |
|---|---|
| **UI** | Frontend interface. Entry point for all user interactions. Connects to all backend managers via Linkage interfaces. |

#### Core Microservices

| Component | Color | Description |
|---|---|---|
| **Manejador de Cloud** | Blue | Integrates with cloud provider APIs (AWS mandatory, GCP optional). Responsible for collecting cost and resource consumption data. Reads from Cache and delegates events to the Event Processor. |
| **Manejador de Reportes** | Green | Generates monthly spending reports per client, area, or project. Enforces the ≤ 100 ms response requirement. Delegates long-running analyses (> 2 s) to the Event Processor via the message queue. |
| **Manejador de Seguridad** | Blue | Enforces access control policies. Detects and blocks 100% of unauthorized accesses, logs audit evidence, and alerts company administrators. |
| **Manejador de Usuarios** | Blue | Manages user accounts, roles, and company/project assignments. Integrates with an external Identity Provider API. |
| **Procesador de Eventos** | Green | Consumes messages from the AMQP queue. Handles background processing for analyses that exceed the 2-second threshold, triggering email notifications upon completion. |

#### Infrastructure Components

| Component | Description |
|---|---|
| **Cache** | Shared caching layer. Accessed via `Cache read` and `Cache access` interfaces. Used by the Cloud Manager and Report Manager to optimize response times. |
| **Cola de Mensajes AMQP** | RabbitMQ message broker. Decouples long-running tasks from synchronous request handling. Connected to the Event Processor via AMQP protocol. |

#### External APIs

| Component | Description |
|---|---|
| **API Proveedores Cloud (AWS/GCP)** | External cloud provider APIs. Connected to the Cloud Manager via Linkage. Must be extendable without modifying existing code (plugin/adapter pattern). |
| **API Email Provider** | External email service. Used by the Cloud Manager (and indirectly by the Event Processor) to send notifications to users. |
| **API Identity Provider** | External identity and authentication provider. Connected to the User Manager for authentication and authorization. |

### 2.3 Key Architectural Decisions

- **Linkage connectors** are used consistently between all components, making interfaces explicit and supporting independent deployability.
- The **Cache** is a cross-cutting infrastructure component accessed by multiple services to meet the latency SLA.
- The **AMQP queue** provides the decoupling needed for the background processing requirement (analyses > 2 seconds).
- The cloud provider integration is designed to be **extensible without code changes**, supporting the addition of new cloud providers via an adapter/plugin mechanism.

---

## 3. Level 2 – Deployment Architecture

### 3.1 Infrastructure Overview

All components are deployed within **AWS Cloud Infrastructure**. The client accesses the system from a user device (browser) running a React UI, served from a dedicated Frontend Server. Traffic is routed through an **AWS Application Load Balancer** using HTTPS.

### 3.2 Frontend

| Node | Stack | Specs |
|---|---|---|
| Servidor Frontend | React – Componente UI | Ubuntu 22.04 / 4 vCPU / 8GB RAM |

### 3.3 Backend Application Servers

All backend servers run **Django** on Ubuntu 22.04 and communicate with the Load Balancer over HTTPS.

| Server | Component | Specs |
|---|---|---|
| Servidor Usuarios | Manejador de Usuarios | 4 vCPU / 4GB RAM |
| Servidor Seguridad | Manejador de Seguridad + Manejador de Autenticación | 4 vCPU / 8GB RAM |
| Servidor Reportes | Manejador de Reportes | 4 vCPU / 8GB RAM |
| Servidor Cloud | Manejador de Cloud | 4 vCPU / 8GB RAM |

### 3.4 Databases

Each service has its own dedicated database, maintaining data isolation across microservices.

| Database | Owner Service | Specs |
|---|---|---|
| Información de empresa (proyectos, empleados, presupuestos) | Servidor Usuarios | Ubuntu 22.04 / 2 vCPU / 4GB RAM |
| Base de datos de Autenticación y Autorización (Usuarios) | Servidor Seguridad | Ubuntu 22.04 / 2 vCPU / 4GB RAM |
| Base de datos de Auditorías de Seguridad | Servidor Seguridad | Ubuntu 22.04 / 2 vCPU / 4GB RAM |
| Base de datos de Reportes | Servidor Reportes | Ubuntu 22.04 / 2 vCPU / 4GB RAM |
| Base de datos de Proyectos y Recursos Cloud | Servidor Cloud | Ubuntu 22.04 / 2 vCPU / 4GB RAM |

### 3.5 Shared Infrastructure

| Component | Technology | Specs | Protocol |
|---|---|---|---|
| Redis Cluster (Elasticache) | Redis | Ubuntu 22.04 / 2 vCPU / 4GB RAM | TCP |
| RabbitMQ (AMQP) – Reportes demorados (> 2 segundos) | RabbitMQ | Ubuntu 22.04 / 4 vCPU / 4GB RAM | AMQP |

---

## 4. Experimental Scenarios

The deployment architecture includes two independent experimental scenarios, each targeting a specific quality attribute. They are run as **separate test scenarios**, not simultaneously.

### 4.1 Experiment A – Scalability (Green Elements)

**Goal:** Validate that the platform sustains ≥ 5,000 concurrent users and handles peaks of up to 12,000 concurrent users for windows of up to 10 minutes without degradation.

**Elements involved:**
- Servidor Reportes (Manejador de Reportes) – Green
- RabbitMQ / AMQP messaging server – Green
- Worker Pool (Auto-scaling) – Green
  - Stack: Django – Manejador de Reportes
  - Specs: Ubuntu 22.04 / 4 vCPU / 8GB RAM
  - Connected via AMQP to RabbitMQ and TCP to the Reports Database

**Mechanism:** Long-running report analyses are offloaded to the auto-scaling Worker Pool via RabbitMQ. The pool scales horizontally to absorb traffic peaks, keeping the synchronous request path responsive.

### 4.2 Experiment B – Latency (Blue Elements)

**Goal:** Validate that monthly spending reports are generated in ≤ 100 milliseconds.

**Elements involved:**
- Servidor Usuarios (Manejador de Usuarios) – Blue
- Servidor Seguridad (Manejador de Seguridad + Manejador de Autenticación) – Blue
- Manejador de Usuarios – Blue

**Mechanism:** The latency experiment measures the end-to-end response time for report generation requests, validating the caching strategy (Redis Elasticache) and the optimized query path from the Report Manager to its dedicated database.

---

## 5. Level 3 – Domain Model

The domain is organized into four bounded contexts. This model serves as the reference for both **code generation** and **team documentation**.

### 5.1 Bounded Context: Gestión de Usuarios

**Purpose:** Manages companies, users, roles, projects, and budgets.

| Entity | Description | Key Relationships |
|---|---|---|
| `Empresa` | A client company registered on the platform. | Has 1 `Usuarios` composition, has 1 `Proyecto` |
| `Usuarios` | A user belonging to a company. | Belongs to 1 `Empresa`, has 1 `Rol`, associated with many `Proyecto` |
| `Rol` | A role assigned to a user within the system. | Has many `PermisoRol` |
| `PermisoRol` | A specific permission tied to a role. | Belongs to 1 `Rol` |
| `Proyecto` | A project within a company, linked to cloud accounts and budgets. | Belongs to 1 `Empresa`, has 1..* `CuentaCloud`, has 1 `Presupuesto` |
| `Presupuesto` | The budget defined for a project. | Belongs to 1 `Proyecto` |

### 5.2 Bounded Context: Seguridad

**Purpose:** Tracks access events, enforces policies, and stores audit evidence.

| Entity | Description | Key Relationships |
|---|---|---|
| `EventoSeguridad` | A security event (authorized or unauthorized access attempt). | Has 0..* `RegistroAuditoria`, composed of `PoliticaAcceso`, composed of 0..* `EvidenciaAcceso` |
| `RegistroAuditoria` | An audit log entry associated with a security event. | Belongs to 1 `EventoSeguridad` |
| `PoliticaAcceso` | The access policy evaluated during a security event. | Part of `EventoSeguridad` |
| `EvidenciaAcceso` | Evidence captured for unauthorized access, used for audit trails. | Linked to `EventoSeguridad` and `Usuarios` |

### 5.3 Bounded Context: Cloud

**Purpose:** Represents cloud infrastructure resources, providers, and consumption metrics.

| Entity | Description | Key Relationships |
|---|---|---|
| `ProveedorCloud` | A cloud provider (e.g. AWS, GCP). | Associated with 1 `CuentaCloud` |
| `CuentaCloud` | A cloud account linked to a project and provider. | Belongs to 1 `Proyecto`, has * `RecursoCloud`, linked to 1 `ProveedorCloud` |
| `RecursoCloud` | A specific cloud resource (instance, storage, etc.) within an account. | Belongs to 1 `CuentaCloud`, has * `MetricaConsumo` |
| `MetricaConsumo` | A consumption metric (cost, compute capacity) recorded for a resource. | Belongs to 1 `RecursoCloud` |

### 5.4 Bounded Context: Análisis y Reportes

**Purpose:** Handles cost analysis execution, report generation, savings opportunities, alerts, and notifications.

| Entity | Description | Key Relationships |
|---|---|---|
| `Analisis` | A cost analysis scoped to a project or resource. | Has * `EjecucionAnalisis`, has 0..* `Alerta`, linked to `Proyecto` |
| `EjecucionAnalisis` | A single execution instance of an analysis (sync or async). | Belongs to 1 `Analisis` |
| `Reporte` | A generated report (e.g. monthly spending by client/area/project). | Associated with 0..* `Alerta` |
| `Alerta` | An alert triggered when thresholds or anomalies are detected. | Belongs to 1 `Analisis`, associated with 0..* `Reporte` |
| `OportunidadAhorro` | An identified waste pattern or underutilized resource opportunity. | Associated with * `Notificacion`, linked to `Analisis` |
| `Notificacion` | A notification sent to users (e.g. email on async analysis completion). | Associated with `OportunidadAhorro` and `Usuarios` |

---

## 6. Quality Attribute Summary

| Quality Attribute | Requirement | Architectural Mechanism |
|---|---|---|
| **Scalability** | ≥ 5,000 concurrent users sustained; peaks up to 12,000 for 10 min | Auto-scaling Worker Pool + RabbitMQ AMQP queue |
| **Performance** | Monthly reports ≤ 100 ms | Redis Elasticache + dedicated Report DB + optimized query path |
| **Availability** | No degradation during peak windows | AWS Load Balancer + horizontally scalable services |
| **Security** | 100% unauthorized access detected, blocked, and audited | Manejador de Seguridad + EvidenciaAcceso + RegistroAuditoria domain entities |
| **Extensibility** | Add new cloud providers without modifying existing code | Adapter/plugin pattern in Manejador de Cloud |
| **Async Processing** | Analyses > 2 s run in background with email notification | AMQP queue + Procesador de Eventos + API Email Provider |

---

## 7. Technology Stack Summary

| Layer | Technology |
|---|---|
| Frontend | React |
| Backend (all services) | Django (Python) |
| Database | Relational DB (per service) |
| Cache | Redis (AWS Elasticache) |
| Message Broker | RabbitMQ (AMQP) |
| Cloud Infrastructure | AWS |
| Identity | External Identity Provider API |
| Email | External Email Provider API |
| Cloud Providers | AWS (mandatory), GCP (optional) |
