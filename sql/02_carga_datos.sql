-- =====================================================================
-- 02 - Carga de datos sintéticos (sección 4.2)
-- Fuente: bd_proyecto_drive/"carga de datos.sql" (script ORIGINAL del grupo,
-- el mismo con el que se midieron los tiempos del informe).
--
-- Único cambio: la cantidad de lecturas ya no se edita a mano, se pasa
-- como variable de psql:
--   psql -d bd_1k -v n=1000 -f sql/02_carga_datos.sql
--   (n = 1000 | 10000 | 100000 | 1000000)
-- Ejecutar sobre una base recién creada (01_tablas.sql) y ANTES de 06_triggers.sql.
-- =====================================================================

\if :{?n}
\else
  \echo 'Falta la variable n. Ejemplo: psql -d bd_1k -v n=1000 -f sql/02_carga_datos.sql'
  \quit
\endif
DROP TABLE IF EXISTS cfg;
CREATE TEMP TABLE cfg AS SELECT :n AS n;   -- cantidad de lecturas (variable psql -v n=...)

-- ===== DATOS MAESTROS =====
INSERT INTO ParqueEolico(nombre, ubicacion, capacidad_mw, fecha_operacion)
SELECT 'Parque ' || g, (ARRAY['Piura','Ica','Lambayeque','Arequipa','La Libertad'])[g],
       50 + g*10, DATE '2015-01-01' + g*200
FROM generate_series(1,5) g;

INSERT INTO Turbina(id_parque, codigo, fabricante, modelo, capacidad_kw,
                    fecha_instalacion, estado)
SELECT 1 + (g-1)/20, 'TUR-' || lpad(g::text,3,'0'),
       (ARRAY['Vestas','Siemens Gamesa','GE'])[1 + g%3], 'Modelo-' || (1 + g%4),
       2000 + (g%4)*500, DATE '2016-01-01' + g*20,
       (ARRAY['Operativa','Operativa','Operativa','Detenida','Mantenimiento'])[1 + g%5]
FROM generate_series(1,100) g;

INSERT INTO ComponenteTurbina(id_turbina, nombre, tipo, ubicacion_interna, estado)
SELECT t, c.nombre, 'Mecanico', c.ubic, 'Operativo'
FROM generate_series(1,100) t,
     (VALUES ('Generador','Gondola'),('Caja multiplicadora','Gondola'),
             ('Rodamiento principal','Eje principal'),
             ('Rodamiento de rotor','Buje')) AS c(nombre, ubic);

INSERT INTO SensorVibracion(id_componente, codigo, modelo, unidad_medida,
                            frecuencia_muestreo_hz, fecha_instalacion, estado)
SELECT c, 'SEN-' || lpad(((c-1)*2 + s)::text,4,'0'), 'ACC-' || (100 + s), 'mm/s',
       (ARRAY[1000,2000,5000])[1 + (c+s)%3], DATE '2020-01-01' + c, 'Activo'
FROM generate_series(1,400) c, generate_series(1,2) s;

INSERT INTO Tecnico(nombres, especialidad, correo, telefono)
SELECT 'Tecnico ' || g, (ARRAY['Mecanica','Electrica','Vibraciones'])[1 + g%3],
       'tecnico' || g || '@empresa.com', '9' || (10000000 + g*7919)::text
FROM generate_series(1,30) g;

-- ===== LECTURAS, ALERTAS, ORDENES Y VINCULOS =====
-- Lecturas: reparto uniforme entre los 800 sensores, una por hora
WITH base AS (
  SELECT g,
         (1 + ((g-1) % 800))::int AS s,
         ((g-1) / 800)::int       AS k,
         CASE WHEN random() < 0.005 THEN 4 + random()*2
              ELSE 0.5 + random()*2.5 END AS rms
  FROM generate_series(1, (SELECT n FROM cfg)) g
)
INSERT INTO LecturaVibracion
SELECT s, TIMESTAMP '2026-01-01' + k * INTERVAL '1 hour',
       round(rms::numeric, 4),
       round((rms * (1.5 + random()*1.5))::numeric, 4),
       round((20 + random()*480)::numeric, 4)
FROM base;

-- Alertas por regla de umbral (RMS >= 4), enlazadas a la lectura de origen
INSERT INTO AlertaMantenimiento(id_sensor, fecha_hora_lectura, fecha_hora, nivel,
        tipo_alerta, valor_detectado, descripcion, estado)
SELECT id_sensor, fecha_hora, fecha_hora + INTERVAL '1 minute',
       CASE WHEN valor_rms >= 5.5 THEN 'Critica' WHEN valor_rms >= 5 THEN 'Alta'
            WHEN valor_rms >= 4.5 THEN 'Media' ELSE 'Baja' END,
       'Umbral RMS', valor_rms, 'Vibracion RMS fuera de umbral',
       (ARRAY['Abierta','En revision','Cerrada'])[1 + floor(random()*3)::int]
FROM LecturaVibracion
WHERE valor_rms >= 4;

-- Ordenes de trabajo (proporcional a N, minimo 10), coherentes con los CHECK
INSERT INTO OrdenTrabajo(id_turbina, id_tecnico, fecha_creacion, fecha_programada,
        fecha_cierre, prioridad, tipo_mantenimiento, descripcion, estado)
SELECT t,
       CASE WHEN e = 'Pendiente' AND random() < 0.5 THEN NULL ELSE tec END,
       fc, fc + INTERVAL '3 days',
       CASE WHEN e = 'Finalizada' THEN fc + INTERVAL '5 days' END,
       p, tm, 'Orden de ' || lower(tm) || ' sintetica', e
FROM (
  SELECT 1 + floor(random()*100)::int AS t, 1 + floor(random()*30)::int AS tec,
         TIMESTAMP '2026-01-01' + random() * INTERVAL '40 days' AS fc,
         (ARRAY['Pendiente','En proceso','Finalizada','Cancelada'])[1+floor(random()*4)::int] AS e,
         (ARRAY['Baja','Media','Alta','Critica'])[1+floor(random()*4)::int] AS p,
         (ARRAY['Inspeccion','Preventivo','Correctivo'])[1+floor(random()*3)::int] AS tm
  FROM generate_series(1, GREATEST(10, (SELECT n FROM cfg)/500))
) s;

-- Vinculo alerta-orden: hasta 2 alertas de la MISMA turbina por orden correctiva
INSERT INTO AlertaOrden(id_alerta, id_orden)
SELECT x.id_alerta, o.id_orden
FROM OrdenTrabajo o
JOIN LATERAL (
  SELECT a.id_alerta
  FROM AlertaMantenimiento a
  JOIN SensorVibracion s ON s.id_sensor = a.id_sensor
  JOIN ComponenteTurbina c ON c.id_componente = s.id_componente
  WHERE c.id_turbina = o.id_turbina
  ORDER BY random() LIMIT 2
) x ON TRUE
WHERE o.tipo_mantenimiento = 'Correctivo';

ANALYZE;

-- Resumen de filas por tabla (para la tabla de "Carga de datos" del informe)
SELECT 'ParqueEolico' AS tabla, count(*) FROM ParqueEolico
UNION ALL SELECT 'Turbina', count(*) FROM Turbina
UNION ALL SELECT 'ComponenteTurbina', count(*) FROM ComponenteTurbina
UNION ALL SELECT 'SensorVibracion', count(*) FROM SensorVibracion
UNION ALL SELECT 'Tecnico', count(*) FROM Tecnico
UNION ALL SELECT 'LecturaVibracion', count(*) FROM LecturaVibracion
UNION ALL SELECT 'AlertaMantenimiento', count(*) FROM AlertaMantenimiento
UNION ALL SELECT 'OrdenTrabajo', count(*) FROM OrdenTrabajo
UNION ALL SELECT 'AlertaOrden', count(*) FROM AlertaOrden;
