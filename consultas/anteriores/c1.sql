-- =====================================================================
-- Consulta 1: Alertas críticas abiertas por turbina
-- Fuente: main.tex sección 5.1.2 (líneas 1722-1731)
-- =====================================================================

EXPLAIN ANALYZE
SELECT p.nombre AS parque, t.codigo, COUNT(*) AS alertas_abiertas
FROM AlertaMantenimiento a
JOIN SensorVibracion s   ON s.id_sensor = a.id_sensor
JOIN ComponenteTurbina c ON c.id_componente = s.id_componente
JOIN Turbina t           ON t.id_turbina = c.id_turbina
JOIN ParqueEolico p      ON p.id_parque = t.id_parque
WHERE a.nivel IN ('Alta','Critica') AND a.estado <> 'Cerrada'
GROUP BY p.nombre, t.codigo
ORDER BY alertas_abiertas DESC;
