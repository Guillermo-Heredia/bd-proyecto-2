EXPLAIN ANALYZE
WITH ultima_normal AS (
  SELECT a.id_alerta, a.id_sensor, a.fecha_hora,
         (SELECT MAX(l.fecha_hora)
          FROM LecturaVibracion l
          WHERE l.id_sensor  = a.id_sensor
            AND l.fecha_hora < a.fecha_hora
            AND l.valor_rms  < 3) AS fecha_ultima_normal,
         NOT EXISTS (SELECT 1 FROM AlertaOrden ao
                     WHERE ao.id_alerta = a.id_alerta) AS sin_orden
  FROM AlertaMantenimiento a
)
SELECT t.codigo AS turbina, p.nombre AS parque,
       COUNT(*) AS alertas,
       ROUND(AVG(EXTRACT(EPOCH FROM (u.fecha_hora - u.fecha_ultima_normal)) / 3600), 2)
             AS horas_prom_desde_ultima_normal,
       COUNT(*) FILTER (WHERE u.sin_orden) AS alertas_sin_orden
FROM ultima_normal u
JOIN SensorVibracion s   ON s.id_sensor = u.id_sensor
JOIN ComponenteTurbina c ON c.id_componente = s.id_componente
JOIN Turbina t           ON t.id_turbina = c.id_turbina
JOIN ParqueEolico p      ON p.id_parque = t.id_parque
WHERE u.fecha_ultima_normal IS NOT NULL
GROUP BY t.codigo, p.nombre
ORDER BY horas_prom_desde_ultima_normal ASC, alertas DESC
LIMIT 10;
