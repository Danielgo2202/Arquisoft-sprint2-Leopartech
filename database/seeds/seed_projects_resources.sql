-- 1. Semillas de Proveedores
INSERT INTO proveedores_cloud (id, nombre, tipo, activo, configuracion, creado_en)
VALUES 
    (gen_random_uuid(), 'Amazon Web Services', 'AWS', true, '{}', NOW()),
    (gen_random_uuid(), 'Google Cloud', 'GCP', true, '{}', NOW());

-- 2. Semillas de Cuentas Cloud
INSERT INTO cuentas_cloud (id, nombre, proveedor_id, proyecto_id, account_external_id, region, activa, creada_en, actualizada_en)
SELECT
    gen_random_uuid(),
    'Cuenta AWS ' || s,
    (SELECT id FROM proveedores_cloud WHERE tipo='AWS' LIMIT 1),
    gen_random_uuid(), -- FK logica a tabla proyectos (no enforces DB-cross FK)
    'aws-acc-' || (1000000 + s),
    'us-east-1',
    TRUE,
    NOW(),
    NOW()
FROM generate_series(1, 100) s;

-- 3. Semillas de Recursos Cloud
INSERT INTO recursos_cloud (id, cuenta_id, nombre, tipo, region, resource_external_id, etiquetas, activo, creado_en, actualizado_en)
SELECT
    gen_random_uuid(),
    (SELECT id FROM cuentas_cloud ORDER BY random() LIMIT 1),
    'Recurso ' || s,
    CASE 
        WHEN s % 3 = 1 THEN 'EC2'
        WHEN s % 3 = 2 THEN 'S3'
        ELSE 'RDS'
    END,
    'us-east-1',
    'arn:aws:recurso:' || s,
    '{}'::jsonb,
    TRUE,
    NOW(),
    NOW()
FROM generate_series(1, 10000) s;