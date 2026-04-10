# Reporte Técnico: Infraestructura (Terraform)

El archivo maestro de infraestructura `main.tf` define, de manera declarativa, el ecosistema Cloud completo donde se ejecutan y orquestan los microservicios de BITE.co. Este documento provee una guía integral y el razonamiento bajo el cual se determinaron las políticas operativas del sistema en AWS.

---

## 1. Topología de Red y Componentes (VPC & Subnets)

El aprovisionamiento inicia referenciando la infraestructura as-a-service preexistente y disponible sin incurrir en colisiones dentro de AWS Academy.

- **VPC & Subnets:** Se emplea la Virtual Private Cloud predeterminada (`default`) con inyección multizona (`us-east-1a`, `us-east-1b`). 
  - **Decisión de Diseño Crítica (Limitación por AWS Academy):** Las zonas de disponibilidad están artificialmente recortadas dentro del entorno por motivos de costo. El despliegue inyecta filtros y _tags_ condicionales para abstraer esta limitación al provisionamiento cruzado, evitando errores comunes de "_Subnet not found / Not available for ec2-type_".
- **Balanceo (Application Load Balancer):** Ubicado en los bordes de la topología pública, canaliza a todos los usuarios/APIs hacia los servicios. Actúa de firewall reverso, mitigando ataques directos.

---

## 2. Flujos de Comunicación y Security Groups (Firewalls)

La filosofía en red empleada es de "Confianza Cero en el Interior pero con Enlaces Permitidos" (_Zero Trust with Allowed Peering_). Existen Múltiples matrices de Security Groups para desacoplar e interceptar dependencias.

1. **`alb_sg`** (Application Load Balancer): Único componente con visibilidad a la IPv4 Global (0.0.0.0/0). Acepta el puerto estricto del requerimiento a nivel API (RESTFul Puerto 80).
2. **`app_sg`** (`Manejadores`): Ningún `Manejador` expone un puerto público. Escuchan puertos `8001`, `8002`, `8003` provenientes en forma exclusiva desde la IP lógica o subred del ALB (`alb_sg`).
3. **`db_sg` & `cache_sg`** (Capa de Persistencia Red/Bases de Datos): Las máquinas subyacentes de PostgreSQL (puerto `5432`) y de Redis (puerto `6379`) tienen _Ingress_ configurado para admitir solamente requests dentro del anillo `app_sg` o del Worker. Bloquean todo el demás acceso en la subred.
4. **`broker_sg`** (AMQP Messaging): RabbitMQ permite los puertos `5672` (Comunicación de Clusters Broker) y `15672` (Panel Administrativo de Salud) y solo los workers de Celery/Manejadores pueden suscribir o publicar suscriptores hacia el mismo.
5. **`ssh_sg`**: Regla independiente exclusiva del Puerto `22`, únicamente autorizada para las interfaces administrativas, inyectando un capa temporal si ocurriere un desastre operativo (Operatoria de debugging manual en _AWS Learner Labs_).

Esta estructura de defensa en profundidad asegura que, si una capa vulnerable fuera remotamente penetrada, el asaltante se limite a los puertos asignados de ese componente. 

---

## 3. Despliegue Configurable e Idempotente de Instancias

Se levantaron instancias virtuales (EC2 - `t2.medium` / `t2.micro` dictaminadas por las variables) divididas en infraestructura (bases de datos/brokers/caches), los *AppServers*, y *Workers Asíncronos*.

### 3.1. Proceso de Arranque por Inyección (`user_data` Automático) 
Dada la restricción severa de un ambiente gestionado como el de Labs/Academy en el cual no es posible automatizar el copiado iterativo de llaves `ssh`, la estrategia global descansa en _Cloud-Init_ con Bash inyectado durante la instanciación de Terraform.
   - **Módulos Bootstrapping:** Instala el stack completo (`git`, `docker`, `python`, `gunicorn`, drivers de Postgres `psycopg2`). Clona el repositorio `Arquisoft-sprint2-Leopartech` automáticamente en crudo basándose en la llave referencial del repositorio personal autorizado.
   - **Comportamiento Asíncrono Resiliente (Sync Locks):** Los App Servers están atados lógicamente entre dependencias, lo cual provoca problemas de tiempos si la Base de Datos todavía no está lista en `boot`. Se utiliza un bucle con la invocación transaccional: `until nc -z $DB_IP 5432; do sleep 5; done` para bloquear la ejecución localmente hasta que la confirmación de la capa más profunda esté verificada exitosamente.

### 3.2. Orquestación del Limitador de AWS (Workers Scale-Down)
La limitante física interpuesta es un tope estricto de **9 instancias concurrentes**. Para maximizar este requerimiento de _budget_, Terraform utiliza el bloque paramétrico dinámico `worker_pool` donde la cantidad de réplicas preconfiguradas (`WorkerNode-Celery-Asincrono-${each.key}`) se calibró restrictivamente para alojar solo una (1) unidad asíncrona, maximizando la coexistencia de los demás servicios de alta prioridad.

### 3.3 Base de Datos, Seeds (Población de Datos) y Experimentos

Los `user_data` de Django instancian transacciones cruzadas ejecutables. Se implementaron inyecciones SQL que leen directamente los `seeds` en el momento en el cual el contendor Postgres levanta la conexión, llenando con **UUIDs** estáticos los catálogos.  
**Decisión Crítica:** Con el fin de viabilizar los requerimientos experimentales de carga sintética _(ASR16 y ASR17)_, Terraform se encarga proactivamente de que `seed_users_company.sql` impacte `usuarios_db` antes que cualquier test JMeter cometa un POST al ALB, previniendo cascadas de excepciones lógicas (e.g. `Empresa no encontrada -> Falló la creación -> HTTP 500/404`).

---

## 4. Requerimientos Operativos Posteriores (Para DevOps/Backend Admins)

- En caso de destruirse el entorno, ejecutar `terraform init && terraform plan && terraform apply -auto-approve` provisionará los servidores de vuelta y configurará el Load Balancer re-asociando correctamente la infraestructura como código. Las instancias ya poseen los tags semánticos descriptivos ajustados en la última refactorización.
- Utilice siempre el **Output `alb_dns_name`** o **`alb_reportes_url`** emitido al concluir el comando apply de Terraform para alimentar los endpoints del frontend, variables locales para entornos, o Postman. Nunca conectarse directamente a las IPs de los AppServers, a fín de preservar la correcta resolución de Load Balancers y monitoreo métrico transaccional interno.
