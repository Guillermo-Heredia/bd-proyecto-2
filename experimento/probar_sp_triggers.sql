-- =====================================================================
-- Prueba de vistas, procedimientos y triggers (evidencia para 4.4–4.6).
-- Todo corre dentro de BEGIN ... ROLLBACK: la base NO queda modificada.
-- Uso:  psql -X -d bd_1m -f experimento/probar_sp_triggers.sql
-- =====================================================================
BEGIN;
\echo '--- Vistas'
SELECT count(*) AS filas_v_alertas_criticas_abiertas FROM v_alertas_criticas_abiertas;
SELECT count(*) AS filas_v_estadisticas_sensor_mes FROM v_estadisticas_sensor_mes;
SELECT * FROM v_carga_tecnico ORDER BY id_tecnico LIMIT 3;

\echo '--- SP1: crear orden desde la alerta 1 (técnico 3)'
CALL sp_crear_orden_desde_alerta(1, 3, 'Correctivo', NULL);
SELECT id_orden, id_turbina, estado, prioridad FROM OrdenTrabajo ORDER BY id_orden DESC LIMIT 1;
SELECT id_alerta, estado AS estado_alerta FROM AlertaMantenimiento WHERE id_alerta = 1;

\echo '--- SP2: cerrar esa orden (la orden y su alerta pasan a Finalizada/Cerrada)'
DO $$ DECLARE v BIGINT; BEGIN SELECT max(id_orden) INTO v FROM OrdenTrabajo; CALL sp_cerrar_orden(v); END $$;
SELECT o.id_orden, o.estado, o.fecha_cierre IS NOT NULL AS tiene_cierre, a.estado AS estado_alerta
FROM OrdenTrabajo o JOIN AlertaOrden ao USING (id_orden) JOIN AlertaMantenimiento a USING (id_alerta)
WHERE o.id_orden = (SELECT max(id_orden) FROM OrdenTrabajo);

\echo '--- F1: historial de la turbina 7'
SELECT origen, count(*) FROM fn_historial_turbina(7, '2026-01-01', '2026-12-31') GROUP BY origen;

\echo '--- T2: lectura con RMS 5.8 -> alerta Critica automática'
INSERT INTO LecturaVibracion VALUES (1, '2027-06-01 10:00', 5.8, 9.1, 140);
SELECT id_alerta, id_sensor, nivel, estado, valor_detectado
FROM AlertaMantenimiento ORDER BY id_alerta DESC LIMIT 1;

\echo '--- T3: finalizar una orden sin fecha_cierre -> se completa sola'
UPDATE OrdenTrabajo SET estado = 'Finalizada', id_tecnico = COALESCE(id_tecnico, 1), fecha_cierre = NULL
WHERE id_orden = (SELECT min(id_orden) FROM OrdenTrabajo WHERE estado = 'Pendiente')
RETURNING id_orden, fecha_cierre IS NOT NULL AS cierre_automatico;

\echo '--- T1: vincular una alerta de OTRA turbina debe dar ERROR (esperado)'
SAVEPOINT t1;
INSERT INTO AlertaOrden
SELECT a.id_alerta, o.id_orden
FROM OrdenTrabajo o, AlertaMantenimiento a
JOIN SensorVibracion s   ON s.id_sensor = a.id_sensor
JOIN ComponenteTurbina c ON c.id_componente = s.id_componente
WHERE c.id_turbina <> o.id_turbina
LIMIT 1;
ROLLBACK TO t1;

\echo '--- Caso borde: cerrar una orden Pendiente SIN técnico (viola un CHECK)'
SAVEPOINT sp2;
DO $$ DECLARE v BIGINT; BEGIN
  SELECT min(id_orden) INTO v FROM OrdenTrabajo WHERE estado = 'Pendiente' AND id_tecnico IS NULL;
  CALL sp_cerrar_orden(v);
END $$;
ROLLBACK TO sp2;

ROLLBACK;
