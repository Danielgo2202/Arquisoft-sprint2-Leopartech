-- 1. Crear Analisis
INSERT INTO analisis (id, nombre, proyecto_id, empresa_id, tipo, estado, creado_en, actualizado_en)
SELECT
    gen_random_uuid(),
    'Analisis ' || s,
    gen_random_uuid(), -- Logical FK
    gen_random_uuid(), -- Logical FK
    CASE
        WHEN random() < 0.4 THEN 'COSTO'
        WHEN random() < 0.7 THEN 'CAPACIDAD'
        ELSE 'OPTIMIZACION'
    END,
    CASE
        WHEN random() < 0.5 THEN 'COMPLETADO'
        ELSE 'PENDIENTE'
    END,
    NOW(),
    NOW()
FROM generate_series(1,1000) s;

-- 2. Crear Reportes
INSERT INTO reportes (id, nombre, tipo, proyecto_id, empresa_id, periodo_inicio, periodo_fin, datos, generado_en)
SELECT
    gen_random_uuid(),
    'Reporte ' || s,
    CASE
        WHEN random() < 0.3 THEN 'MENSUAL'
        WHEN random() < 0.6 THEN 'PROYECTO'
        ELSE 'AREA'
    END,
    gen_random_uuid(), -- Logical FK
    gen_random_uuid(), -- Logical FK
    CURRENT_DATE - INTERVAL '30 days',
    CURRENT_DATE,
    '{}'::jsonb,
    NOW()
FROM generate_series(1,1000) s;

-- 3. Crear 5000 Ejecuciones de Analisis (simulando report_jobs)
INSERT INTO ejecuciones_analisis (id, analisis_id, estado, celery_task_id, iniciado_en, completado_en, duracion_ms, resultado, error)
SELECT
    gen_random_uuid(),
    (SELECT id FROM analisis ORDER BY random() LIMIT 1),
    CASE
        WHEN random() < 0.6 THEN 'COMPLETADO'
        WHEN random() < 0.8 THEN 'EN_PROCESO'
        ELSE 'PENDIENTE'
    END,
    'task-' || floor(random()*10000),
    NOW(),
    CASE WHEN random() < 0.6 THEN NOW() ELSE NULL END,
    floor(random()*5000),
    '{}'::jsonb,
    ''
FROM generate_series(1,5000);

-- 4. Crear 10000 Eventos Entrantes (simulando report_events)
INSERT INTO eventos_entrantes (id, evento_id, tipo_evento, payload, procesado, procesado_en, recibido_en)
SELECT
    gen_random_uuid(),
    'evt-' || gen_random_uuid(),
    CASE
        WHEN random() < 0.5 THEN 'proyecto.creado'
        ELSE 'infra.actualizada'
    END,
    jsonb_build_object(
        'source', 'rabbitmq',
        'timestamp', NOW(),
        'batch_size', floor(random()*50 + 1)
    ),
    (random() < 0.5),
    CASE WHEN random() < 0.5 THEN NOW() ELSE NULL END,
    NOW()
FROM generate_series(1,10000);