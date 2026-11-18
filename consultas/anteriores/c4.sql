-- =====================================================================
-- Consulta 4: Componentes con más alertas por parque
-- Fuente: main.tex sección 5.1.2 (líneas 1766-1779)
-- =====================================================================

EXPLAIN ANALYZE
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
ORDER BY parque, rk;
