-- 0. Crear empresas con UUIDs específicos usados por JMeter (projects_payload.json y events_batch.json)
INSERT INTO empresas (id, nombre, nit, activa, creada_en, actualizada_en)
VALUES
    ('550e8400-e29b-41d4-a716-446655440001', 'BITE Empresa Principal', 'NIT-9000000001', TRUE, NOW(), NOW()),
    ('550e8400-e29b-41d4-a716-446655440002', 'BITE Empresa Secundaria', 'NIT-9000000002', TRUE, NOW(), NOW()),
    ('550e8400-e29b-41d4-a716-446655440003', 'BITE Empresa Terciaria', 'NIT-9000000003', TRUE, NOW(), NOW())
ON CONFLICT (id) DO NOTHING;

-- 1. Crear 50 empresas adicionales con UUIDs aleatorios
INSERT INTO empresas (id, nombre, nit, activa, creada_en, actualizada_en)
SELECT
    gen_random_uuid(),
    'Empresa ' || gs,
    'NIT-' || (1000000000 + gs),
    TRUE,
    NOW(),
    NOW()
FROM generate_series(1,50) gs;

-- 2. Crear 1000 empleados
INSERT INTO empleados (id, empresa_id, nombre_completo, email, rol, creado_en)
SELECT
    gen_random_uuid(),
    (SELECT id FROM empresas ORDER BY random() LIMIT 1),
    'Empleado ' || gs,
    'empleado' || gs || '@empresa' || (gs % 50) || '.com',
    CASE
        WHEN random() < 0.2 THEN 'ADMIN'
        WHEN random() < 0.6 THEN 'MANAGER'
        ELSE 'ANALYST'
    END,
    NOW()
FROM generate_series(1,1000) gs;

-- 3. Crear 5000 proyectos en base de datos de usuarios
INSERT INTO proyectos (id, nombre, descripcion, empresa_id, estado, creado_en, actualizado_en)
SELECT 
    gen_random_uuid(),
    'Proyecto ' || s,
    'Proyecto para experimento ASR latencia',
    (SELECT id FROM empresas ORDER BY random() LIMIT 1), 
    'ACTIVO',
    NOW(),
    NOW()
FROM generate_series(1, 5000) s;

-- 4. Crear 500 presupuestos asociados a proyectos (Relación 1 a 1)
INSERT INTO presupuestos (id, proyecto_id, monto_mensual, moneda, alerta_porcentaje, creado_en, actualizado_en)
SELECT
    gen_random_uuid(),
    id,
    round((random()*10000)::numeric, 2),
    'USD',
    80,
    NOW(),
    NOW()
FROM proyectos
LIMIT 500;