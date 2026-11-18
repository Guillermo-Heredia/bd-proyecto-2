-- =====================================================================
-- Consulta 2: Estadísticas de vibración por sensor en un mes
-- Fuente: main.tex sección 5.1.2 (líneas 1736-1743)
-- =====================================================================

EXPLAIN ANALYZE
SELECT s.codigo, AVG(l.valor_rms) AS rms_prom, MAX(l.valor_rms) AS rms_max,
       MAX(l.valor_pico) AS pico_max
FROM LecturaVibracion l
JOIN SensorVibracion s ON s.id_sensor = l.id_sensor
WHERE l.fecha_hora >= '2026-01-01' AND l.fecha_hora < '2026-02-01'
GROUP BY s.id_sensor, s.codigo
ORDER BY rms_max DESC;
