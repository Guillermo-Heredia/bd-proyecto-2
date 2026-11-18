EXPLAIN ANALYZE
WITH ventana AS (
  SELECT l.id_sensor, l.valor_rms, l.valor_pico
  FROM LecturaVibracion l
  WHERE l.fecha_hora >= (SELECT MAX(fecha_hora) FROM LecturaVibracion) - INTERVAL '48 hours'
),
por_sensor AS (
  SELECT v.id_sensor, t.id_parque,
         AVG(v.valor_rms)  AS rms_prom,
         MAX(v.valor_rms)  AS rms_max,
         MAX(v.valor_pico) AS pico_max,
         percentile_cont(0.95) WITHIN GROUP (ORDER BY v.valor_rms) AS rms_p95,
         COUNT(*)          AS n_lecturas
  FROM ventana v
  JOIN SensorVibracion s   ON s.id_sensor = v.id_sensor
  JOIN ComponenteTurbina c ON c.id_componente = s.id_componente
  JOIN Turbina t           ON t.id_turbina = c.id_turbina
  GROUP BY v.id_sensor, t.id_parque
),
por_parque AS (
  SELECT id_parque, AVG(rms_prom) AS rms_prom_parque
  FROM por_sensor
  GROUP BY id_parque
)
SELECT parque, sensor, n_lecturas, rms_prom, rms_prom_parque, pct_sobre_parque,
       rms_max, pico_max, rms_p95, puesto
FROM (
  SELECT p.nombre AS parque, s.codigo AS sensor, ps.n_lecturas,
         ROUND(ps.rms_prom, 3)                                    AS rms_prom,
         ROUND(pp.rms_prom_parque, 3)                             AS rms_prom_parque,
         ROUND(100 * (ps.rms_prom / pp.rms_prom_parque - 1), 1)   AS pct_sobre_parque,
         ps.rms_max, ps.pico_max, ROUND(ps.rms_p95::numeric, 3)   AS rms_p95,
         RANK() OVER (PARTITION BY p.id_parque ORDER BY ps.rms_prom DESC) AS puesto
  FROM por_sensor ps
  JOIN por_parque pp      ON pp.id_parque = ps.id_parque
  JOIN ParqueEolico p     ON p.id_parque = ps.id_parque
  JOIN SensorVibracion s  ON s.id_sensor = ps.id_sensor
  WHERE ps.rms_prom > pp.rms_prom_parque
) r
WHERE puesto <= 5
ORDER BY parque, puesto;
