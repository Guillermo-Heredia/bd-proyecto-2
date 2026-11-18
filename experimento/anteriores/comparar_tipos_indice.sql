-- =====================================================================
-- "UN ÍNDICE U OTRO" (OPCIONAL, FALTA EN EL INFORME)
--
-- Compara B+ tree (simple y cubriente) contra Hash sobre LecturaVibracion.fecha_hora para la
-- Consulta 2 y una variante MÁS SELECTIVA (1 semana), donde el índice sí
-- debería usarse. En el informe actual la C2 filtra todo enero, que es
-- el 60–100 % de la tabla, por eso PostgreSQL ignora el índice.
--
-- Uso:  psql -X -d bd_1m -f experimento/comparar_tipos_indice.sql
-- =====================================================================

\i indices/borrar_indices.sql

\echo '===== A) Sin índice ====='
EXPLAIN ANALYZE
SELECT s.codigo, AVG(l.valor_rms), MAX(l.valor_rms), MAX(l.valor_pico)
FROM LecturaVibracion l JOIN SensorVibracion s ON s.id_sensor = l.id_sensor
WHERE l.fecha_hora >= '2026-01-08' AND l.fecha_hora < '2026-01-15'
GROUP BY s.id_sensor, s.codigo ORDER BY 3 DESC;

\echo '===== B) B-tree simple sobre fecha_hora ====='
CREATE INDEX idx_lectura_fecha_btree ON LecturaVibracion(fecha_hora);
ANALYZE LecturaVibracion;
EXPLAIN ANALYZE
SELECT s.codigo, AVG(l.valor_rms), MAX(l.valor_rms), MAX(l.valor_pico)
FROM LecturaVibracion l JOIN SensorVibracion s ON s.id_sensor = l.id_sensor
WHERE l.fecha_hora >= '2026-01-08' AND l.fecha_hora < '2026-01-15'
GROUP BY s.id_sensor, s.codigo ORDER BY 3 DESC;
DROP INDEX idx_lectura_fecha_btree;

\echo '===== C) B-tree cubriente (el del informe) ====='
CREATE INDEX idx_lectura_fecha_cubriente
  ON LecturaVibracion(fecha_hora) INCLUDE (valor_rms, valor_pico);
VACUUM ANALYZE LecturaVibracion;   -- necesario para Index Only Scan
EXPLAIN ANALYZE
SELECT s.codigo, AVG(l.valor_rms), MAX(l.valor_rms), MAX(l.valor_pico)
FROM LecturaVibracion l JOIN SensorVibracion s ON s.id_sensor = l.id_sensor
WHERE l.fecha_hora >= '2026-01-08' AND l.fecha_hora < '2026-01-15'
GROUP BY s.id_sensor, s.codigo ORDER BY 3 DESC;
DROP INDEX idx_lectura_fecha_cubriente;

\echo '===== D) HASH sobre fecha_hora (no sirve para rangos: PostgreSQL lo ignora) ====='
CREATE INDEX idx_lectura_fecha_hash ON LecturaVibracion USING hash(fecha_hora);
ANALYZE LecturaVibracion;
EXPLAIN ANALYZE
SELECT s.codigo, AVG(l.valor_rms), MAX(l.valor_rms), MAX(l.valor_pico)
FROM LecturaVibracion l JOIN SensorVibracion s ON s.id_sensor = l.id_sensor
WHERE l.fecha_hora >= '2026-01-08' AND l.fecha_hora < '2026-01-15'
GROUP BY s.id_sensor, s.codigo ORDER BY 3 DESC;

\echo '===== Tamaño de cada tipo de índice ====='
CREATE INDEX idx_lectura_fecha_btree ON LecturaVibracion(fecha_hora);
SELECT indexrelname, pg_size_pretty(pg_relation_size(indexrelid)) AS tamano
FROM pg_stat_user_indexes
WHERE indexrelname IN ('idx_lectura_fecha_btree','idx_lectura_fecha_hash');
DROP INDEX idx_lectura_fecha_btree;
DROP INDEX idx_lectura_fecha_hash;
