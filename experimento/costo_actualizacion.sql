-- =====================================================================
-- COSTO DE ACTUALIZACIÓN CON Y SIN ÍNDICES  (FALTA EN EL INFORME)
--
-- El PDF pide: "Analizar y estudiar los tiempos de actualización y de
-- consulta cuando uno usa un índice u otro". El informe solo mide consultas
-- (SELECT). Este script mide INSERT/UPDATE/DELETE sin y con índices.
--
-- Uso (desde version_guille, idealmente en bd_1m):
--   psql -X -d bd_1m -f experimento/costo_actualizacion.sql > resultados/costo_actualizacion.txt
--
-- Cada operación se hace dentro de BEGIN ... ROLLBACK: se mide y se deshace,
-- así la base no cambia y se puede repetir las veces que quieran.
-- Anotar el "Execution Time" de cada bloque (repetir 5 veces para promedio).
-- =====================================================================

\echo '################ 1) SIN ÍNDICES ################'
\i indices/borrar_indices.sql
-- Las PK/UNIQUE también son índices: se apaga su uso para que sea "sin índices" de verdad.
-- (En escrituras las PK igual se mantienen; esto afecta a las búsquedas del UPDATE/DELETE.)
SET enable_indexscan = off; SET enable_indexonlyscan = off; SET enable_bitmapscan = off;

\echo '--- INSERT de 1 000 lecturas nuevas (incluye trigger trg_lectura_alerta) ---'
BEGIN;
EXPLAIN (ANALYZE, BUFFERS)
INSERT INTO LecturaVibracion(id_sensor, fecha_hora, valor_rms, valor_pico, frecuencia_dominante_hz)
SELECT (i % 800) + 1, TIMESTAMP '2027-01-01' + i * INTERVAL '1 hour',
       1.5, 2.5, 120
FROM generate_series(0, 999) AS i;
ROLLBACK;

\echo '--- UPDATE de valor_rms en un día de lecturas ---'
BEGIN;
EXPLAIN (ANALYZE, BUFFERS)
UPDATE LecturaVibracion SET valor_rms = valor_rms + 0.0001
WHERE fecha_hora >= '2026-01-01' AND fecha_hora < '2026-01-02';
ROLLBACK;

\echo '--- UPDATE de estado de alertas (cierre masivo de alertas Baja) ---'
BEGIN;
EXPLAIN (ANALYZE, BUFFERS)
UPDATE AlertaMantenimiento SET estado = 'Cerrada' WHERE nivel = 'Baja';
ROLLBACK;

\echo '--- DELETE de un día de lecturas sin alerta asociada ---'
BEGIN;
EXPLAIN (ANALYZE, BUFFERS)
DELETE FROM LecturaVibracion l
WHERE l.fecha_hora >= '2026-01-02' AND l.fecha_hora < '2026-01-03'
  AND NOT EXISTS (SELECT 1 FROM AlertaMantenimiento a
                  WHERE a.id_sensor = l.id_sensor AND a.fecha_hora_lectura = l.fecha_hora);
ROLLBACK;


\echo '################ 2) CON ÍNDICES ################'
RESET enable_indexscan; RESET enable_indexonlyscan; RESET enable_bitmapscan;
\i indices/crear_indices.sql

\echo '--- INSERT de 1 000 lecturas nuevas ---'
BEGIN;
EXPLAIN (ANALYZE, BUFFERS)
INSERT INTO LecturaVibracion(id_sensor, fecha_hora, valor_rms, valor_pico, frecuencia_dominante_hz)
SELECT (i % 800) + 1, TIMESTAMP '2027-01-01' + i * INTERVAL '1 hour',
       1.5, 2.5, 120
FROM generate_series(0, 999) AS i;
ROLLBACK;

\echo '--- UPDATE de valor_rms en un día de lecturas ---'
-- Ojo: idx_lectura_fecha_cubriente e idx_lectura_sensor_fecha_rms incluyen
-- valor_rms, así que este UPDATE ya no puede ser HOT y debe tocar los índices.
BEGIN;
EXPLAIN (ANALYZE, BUFFERS)
UPDATE LecturaVibracion SET valor_rms = valor_rms + 0.0001
WHERE fecha_hora >= '2026-01-01' AND fecha_hora < '2026-01-02';
ROLLBACK;

\echo '--- UPDATE de estado de alertas ---'
-- estado está en el WHERE del índice parcial idx_alerta_criticas_abiertas.
BEGIN;
EXPLAIN (ANALYZE, BUFFERS)
UPDATE AlertaMantenimiento SET estado = 'Cerrada' WHERE nivel = 'Baja';
ROLLBACK;

\echo '--- DELETE de un día de lecturas sin alerta asociada ---'
BEGIN;
EXPLAIN (ANALYZE, BUFFERS)
DELETE FROM LecturaVibracion l
WHERE l.fecha_hora >= '2026-01-02' AND l.fecha_hora < '2026-01-03'
  AND NOT EXISTS (SELECT 1 FROM AlertaMantenimiento a
                  WHERE a.id_sensor = l.id_sensor AND a.fecha_hora_lectura = l.fecha_hora);
ROLLBACK;


\echo '################ 3) ESPACIO QUE OCUPAN ################'
SELECT relname AS tabla,
       pg_size_pretty(pg_table_size(relid))   AS datos,
       pg_size_pretty(pg_indexes_size(relid)) AS indices
FROM pg_stat_user_tables
ORDER BY pg_table_size(relid) DESC;

SELECT indexrelname AS indice, relname AS tabla,
       pg_size_pretty(pg_relation_size(indexrelid)) AS tamano
FROM pg_stat_user_indexes
ORDER BY pg_relation_size(indexrelid) DESC;
