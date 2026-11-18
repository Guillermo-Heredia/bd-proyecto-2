-- =====================================================================
-- 04 - Vistas (sección 4.4)
-- Fuente: main.tex (líneas 1504-1533)
-- =====================================================================

-- Supervisor: turbinas con alertas Alta/Critica no cerradas
CREATE OR REPLACE VIEW v_alertas_criticas_abiertas AS
SELECT p.nombre AS parque, t.id_turbina, t.codigo AS turbina,
       COUNT(*) AS alertas_abiertas, MAX(a.fecha_hora) AS ultima_alerta
FROM AlertaMantenimiento a
JOIN SensorVibracion s    ON s.id_sensor = a.id_sensor
JOIN ComponenteTurbina c  ON c.id_componente = s.id_componente
JOIN Turbina t            ON t.id_turbina = c.id_turbina
JOIN ParqueEolico p       ON p.id_parque = t.id_parque
WHERE a.nivel IN ('Alta','Critica') AND a.estado <> 'Cerrada'
GROUP BY p.nombre, t.id_turbina, t.codigo;

-- Analista: estadisticas mensuales de vibracion por sensor
CREATE OR REPLACE VIEW v_estadisticas_sensor_mes AS
SELECT s.id_sensor, s.codigo, date_trunc('month', l.fecha_hora) AS mes,
       AVG(l.valor_rms) AS rms_promedio, MAX(l.valor_rms) AS rms_maximo,
       MAX(l.valor_pico) AS pico_maximo, COUNT(*) AS n_lecturas
FROM LecturaVibracion l
JOIN SensorVibracion s ON s.id_sensor = l.id_sensor
GROUP BY s.id_sensor, s.codigo, date_trunc('month', l.fecha_hora);

-- Supervisor: carga de trabajo por tecnico
CREATE OR REPLACE VIEW v_carga_tecnico AS
SELECT tc.id_tecnico, tc.nombres, tc.especialidad,
       COUNT(*) FILTER (WHERE o.estado = 'Pendiente')  AS pendientes,
       COUNT(*) FILTER (WHERE o.estado = 'En proceso') AS en_proceso
FROM Tecnico tc
LEFT JOIN OrdenTrabajo o ON o.id_tecnico = tc.id_tecnico
GROUP BY tc.id_tecnico, tc.nombres, tc.especialidad;
