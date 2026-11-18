-- =====================================================================
-- 03 - Simulación de datos faltantes (sección 4.3)
-- Fuente: main.tex (líneas 1483-1497)
-- =====================================================================

-- 2% de alertas registradas manualmente (sin lectura de origen)
UPDATE AlertaMantenimiento SET fecha_hora_lectura = NULL
WHERE random() < 0.02;

-- 5% de sensores fuera de servicio
UPDATE SensorVibracion SET estado = 'Inactivo' WHERE random() < 0.05;

-- Periodo sin lecturas en los sensores inactivos
DELETE FROM LecturaVibracion l
USING SensorVibracion s
WHERE s.id_sensor = l.id_sensor AND s.estado = 'Inactivo'
  AND l.fecha_hora BETWEEN '2026-01-10' AND '2026-01-20'
  AND NOT EXISTS (SELECT 1 FROM AlertaMantenimiento a
                  WHERE a.id_sensor = l.id_sensor
                    AND a.fecha_hora_lectura = l.fecha_hora);

ANALYZE;
