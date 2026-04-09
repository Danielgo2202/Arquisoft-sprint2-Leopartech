# Integración de Base de Datos y Semillas (Seeds) en Arquitectura BITE.co

Esta documentación detalla cómo la infraestructura de datos independiente fue unificada con los microservicios Django para garantizar compatibilidad estructural, cumplir con las dependencias del Docker Compose y preparar el sistema para los ASR 16 (Latencia) y ASR 17 (Escalabilidad).

## 1. Cambios Arquitectónicos Implementados

Al analizar la infraestructura independiente (`database/docker-compose-db.yml` y los scripts SQL `01_...sql`), se determinó que **el ORM de Django debe fungir como única fuente de la verdad para el esquema**.

La inicialización paralela de tablas en la carpeta `/docker-entrypoint-initdb.d/` chocaría directamente con las migraciones nativas de Django (`django_migrations`), las restricciones referenciales complejas cruzadas y el ciclo de vida del contenedor. 

Por esto, tomamos las siguientes decisiones:

1.  **Mapeo Exhaustivo al ORM**: Los nombres de tablas SQL manuales como `companies`, `projects`, `cloud_accounts` se rediseñaron a `empresas`, `proyectos`, `cuentas_cloud`, respetando el Bounded Context estructurado del `manejador_usuarios`, `manejador_cloud` y `manejador_reportes`.
2.  **Modelo Faltante Inyectado**: El modelo original del proyecto carecía del modelo Django para mapear con tu concepto de `employees`. He inyectado la clase `Empleado` dentro del `manejador_usuarios/projects/models.py`.
3.  **Conversión a Seeds Puros**: Todos los archivos dentro de `database/seeds` ahora son sentencias de volumen (DML, puros `INSERT INTO` masivos usando generadores) adaptados a la metadata y constraints de Django UUID y ForeignKeys.

## 2. Inyección Cíclica en Docker Compose

Se prescindió de utilizar un Compose externo (`database/docker-compose-db.yml`). La estrategia de inyección adoptada ahora es inyectar en el Entrypoint:

1. El orquestador `docker-compose.yml` monta la carpeta `./database/seeds` como un volumen de Solo-Lectura (`:ro`) en los tres servicios principales de Django:
   - `manejador_usuarios`
   - `manejador_cloud`
   - `manejador_reportes`

2. Los archivos `entrypoint.sh` de cada microservicio fueron modificados. Posterior a que el ORM complete un exitoso `python manage.py migrate --noinput` (garantizando así que la base de datos está formada), se verifica e inyecta la semilla:
   ```bash
   python manage.py dbshell < /seeds/seed_users_company.sql || true
   ```

## 3. Pruebas y Escalabilidad (ASR 16 y 17)

Gracias a esta configuración:
- Al desplegar (incluso en pipelines CI/CD o vía Terraform), siempre la DB iniciará con el esquema robusto de Django y opcionalmente cargará tu metadata simulada de carga alta (10,000 incidentes o 5,000 dependencias) para cumplir con las validaciones del **ASR 16**.
- Los nombres internos dentro de la red Docker predeterminados en `docker-compose.yml` actúan correctamente (`postgres_cloud`, `postgres_usuarios`).

## Pasos para probar localmente

1. Borrar cualquier estado anómalo previo:
   ```bash
   docker compose down -v
   ```
2. Reconstruir e instanciar:
   ```bash
   docker compose up --build -d
   ```
3. Validar:
   ```bash
   # Puedes entrar a la base de postgres de usuarios
   docker exec -it arquisoft-sprint2-leopartech-postgres_usuarios-1 psql -U postgres -d usuarios_db
   
   # Validar que los 5,000 proyectos y 1,000 empleados cargaron
   SELECT count(*) FROM proyectos;
   SELECT count(*) FROM empleados;
   ```
