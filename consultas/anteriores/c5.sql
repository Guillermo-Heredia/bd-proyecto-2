-- =====================================================================
-- Consulta 5: Trazabilidad de una turbina
-- Fuente: main.tex sección 5.1.2 (líneas 1784-1794)
-- =====================================================================

EXPLAIN ANALYZE
SELECT o.id_orden, o.estado, o.prioridad, tc.nombres AS tecnico,
       a.id_alerta, a.nivel, l.fecha_hora AS lectura, l.valor_rms
FROM OrdenTrabajo o
JOIN AlertaOrden ao          ON ao.id_orden = o.id_orden
JOIN AlertaMantenimiento a   ON a.id_alerta = ao.id_alerta
LEFT JOIN LecturaVibracion l ON l.id_sensor = a.id_sensor
                            AND l.fecha_hora = a.fecha_hora_lectura
LEFT JOIN Tecnico tc         ON tc.id_tecnico = o.id_tecnico
WHERE o.id_turbina = 7
ORDER BY o.fecha_creacion;
