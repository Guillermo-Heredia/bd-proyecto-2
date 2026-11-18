-- =====================================================================
-- Alternativa al .sh: mide las 5 consultas x 5 ejecuciones DESDE SQL.
-- Fuente: bd_proyecto_drive/"script que mide los tiempos (5 ejecuciones por consulta).sql"
-- (script ORIGINAL del grupo, sin cambios). Funciona en psql o pgAdmin:
--   psql -X -d bd_1m -f experimento/medir_tiempos_en_sql.sql
-- Limitación: no tiene corrida de calentamiento; correrlo sin y con índices
-- en la MISMA sesión (borrar_indices.sql -> medir -> crear_indices.sql -> medir).
-- =====================================================================
-- ejecuta las 5 consultas 5 veces cada una y devuelve los tiempos.


DROP TABLE IF EXISTS resultados;
CREATE TEMP TABLE resultados (consulta INT, ejecucion INT, ms NUMERIC);

DO $do$
DECLARE
  qs TEXT[] := ARRAY[
-- Consulta 1
$q$
SELECT p.nombre AS parque, t.codigo, COUNT(*) AS alertas_abiertas
FROM AlertaMantenimiento a
JOIN SensorVibracion s   ON s.id_sensor = a.id_sensor
JOIN ComponenteTurbina c ON c.id_componente = s.id_componente
JOIN Turbina t           ON t.id_turbina = c.id_turbina
JOIN ParqueEolico p      ON p.id_parque = t.id_parque
WHERE a.nivel IN ('Alta','Critica') AND a.estado <> 'Cerrada'
GROUP BY p.nombre, t.codigo
ORDER BY alertas_abiertas DESC
$q$,
-- Consulta 2
$q$
SELECT s.codigo, AVG(l.valor_rms) AS rms_prom, MAX(l.valor_rms) AS rms_max,
       MAX(l.valor_pico) AS pico_max
FROM LecturaVibracion l
JOIN SensorVibracion s ON s.id_sensor = l.id_sensor
WHERE l.fecha_hora >= '2026-01-01' AND l.fecha_hora < '2026-02-01'
GROUP BY s.id_sensor, s.codigo
ORDER BY rms_max DESC
$q$,
-- Consulta 3
$q$
WITH marcadas AS (
  SELECT id_sensor, fecha_hora, valor_rms > 2.5 AS sobre,
         ROW_NUMBER() OVER (PARTITION BY id_sensor ORDER BY fecha_hora)
       - ROW_NUMBER() OVER (PARTITION BY id_sensor, (valor_rms > 2.5)
                            ORDER BY fecha_hora) AS grp
  FROM LecturaVibracion
)
SELECT id_sensor, MIN(fecha_hora) AS inicio, MAX(fecha_hora) AS fin, COUNT(*) AS n
FROM marcadas
WHERE sobre
GROUP BY id_sensor, grp
HAVING COUNT(*) >= 3
ORDER BY n DESC
$q$,
-- Consulta 4
$q$
SELECT parque, componente, total_alertas
FROM (
  SELECT p.nombre AS parque, c.nombre AS componente, COUNT(*) AS total_alertas,
         RANK() OVER (PARTITION BY p.id_parque ORDER BY COUNT(*) DESC) AS rk
  FROM AlertaMantenimiento a
  JOIN SensorVibracion s   ON s.id_sensor = a.id_sensor
  JOIN ComponenteTurbina c ON c.id_componente = s.id_componente
  JOIN Turbina t           ON t.id_turbina = c.id_turbina
  JOIN ParqueEolico p      ON p.id_parque = t.id_parque
  GROUP BY p.id_parque, p.nombre, c.nombre
) x
WHERE rk <= 3
ORDER BY parque, rk
$q$,
-- Consulta 5
$q$
SELECT o.id_orden, o.estado, o.prioridad, tc.nombres AS tecnico,
       a.id_alerta, a.nivel, l.fecha_hora AS lectura, l.valor_rms
FROM OrdenTrabajo o
JOIN AlertaOrden ao          ON ao.id_orden = o.id_orden
JOIN AlertaMantenimiento a   ON a.id_alerta = ao.id_alerta
LEFT JOIN LecturaVibracion l ON l.id_sensor = a.id_sensor
                            AND l.fecha_hora = a.fecha_hora_lectura
LEFT JOIN Tecnico tc         ON tc.id_tecnico = o.id_tecnico
WHERE o.id_turbina = 7
ORDER BY o.fecha_creacion
$q$
  ];
  j JSON;
BEGIN
  FOR i IN 1..5 LOOP
    FOR r IN 1..5 LOOP
      EXECUTE 'EXPLAIN (ANALYZE, FORMAT JSON) ' || qs[i] INTO j;
      INSERT INTO resultados VALUES (i, r, (j->0->>'Execution Time')::numeric);
    END LOOP;
  END LOOP;
END $do$;

SELECT consulta,
       ROUND(MAX(ms) FILTER (WHERE ejecucion = 1), 2) AS ejec_1,
       ROUND(MAX(ms) FILTER (WHERE ejecucion = 2), 2) AS ejec_2,
       ROUND(MAX(ms) FILTER (WHERE ejecucion = 3), 2) AS ejec_3,
       ROUND(MAX(ms) FILTER (WHERE ejecucion = 4), 2) AS ejec_4,
       ROUND(MAX(ms) FILTER (WHERE ejecucion = 5), 2) AS ejec_5,
       ROUND(AVG(ms), 2)         AS promedio,
       ROUND(STDDEV_SAMP(ms), 2) AS desv_estandar
FROM resultados
GROUP BY consulta
ORDER BY consulta;
