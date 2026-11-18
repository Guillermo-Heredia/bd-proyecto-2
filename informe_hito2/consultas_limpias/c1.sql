EXPLAIN ANALYZE
WITH anomalas AS MATERIALIZED (
  SELECT l.id_sensor, l.fecha_hora, l.valor_rms,
         (SELECT AVG(l2.valor_rms)
          FROM LecturaVibracion l2
          WHERE l2.id_sensor  = l.id_sensor
            AND l2.fecha_hora >= l.fecha_hora - INTERVAL '24 hours'
            AND l2.fecha_hora <  l.fecha_hora) AS rms_prom_24h
  FROM LecturaVibracion l
  WHERE l.valor_rms >= 4
)
SELECT p.nombre AS parque, t.codigo AS turbina, s.codigo AS sensor,
       x.fecha_hora, x.valor_rms,
       ROUND(x.rms_prom_24h, 4)                 AS rms_prom_24h_previas,
       ROUND(x.valor_rms / x.rms_prom_24h, 2)   AS veces_sobre_promedio
FROM anomalas x
JOIN SensorVibracion s   ON s.id_sensor = x.id_sensor
JOIN ComponenteTurbina c ON c.id_componente = s.id_componente
JOIN Turbina t           ON t.id_turbina = c.id_turbina
JOIN ParqueEolico p      ON p.id_parque = t.id_parque
WHERE x.valor_rms >= 1.5 * x.rms_prom_24h
ORDER BY veces_sobre_promedio DESC;
