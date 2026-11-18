-- =====================================================================
-- Consulta 3: Lecturas consecutivas sobre el umbral
-- Fuente: main.tex sección 5.1.2 (líneas 1748-1761)
-- =====================================================================

EXPLAIN ANALYZE
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
ORDER BY n DESC;
