-- =====================================================================
-- 06 - Triggers (sección 4.6)
-- Fuente: main.tex (líneas 1609-1665)
-- =====================================================================

-- IMPORTANTE: se crean DESPUÉS de la carga masiva (02_carga_datos.sql).
-- Si trg_lectura_alerta existiera durante la carga, cada lectura anómala
-- generaría una alerta duplicada (la carga ya crea las alertas por umbral).

-- T1: la alerta debe pertenecer a la misma turbina de la orden
CREATE OR REPLACE FUNCTION fn_validar_alerta_orden() RETURNS TRIGGER
LANGUAGE plpgsql AS $$
DECLARE v_turbina_alerta INT; v_turbina_orden INT;
BEGIN
  SELECT c.id_turbina INTO v_turbina_alerta
  FROM AlertaMantenimiento a
  JOIN SensorVibracion s   ON s.id_sensor = a.id_sensor
  JOIN ComponenteTurbina c ON c.id_componente = s.id_componente
  WHERE a.id_alerta = NEW.id_alerta;

  SELECT id_turbina INTO v_turbina_orden FROM OrdenTrabajo WHERE id_orden = NEW.id_orden;

  IF v_turbina_alerta IS DISTINCT FROM v_turbina_orden THEN
    RAISE EXCEPTION 'La alerta % no pertenece a la turbina de la orden %',
                    NEW.id_alerta, NEW.id_orden;
  END IF;
  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_alerta_orden_consistencia ON AlertaOrden;
CREATE TRIGGER trg_alerta_orden_consistencia
BEFORE INSERT OR UPDATE ON AlertaOrden
FOR EACH ROW EXECUTE FUNCTION fn_validar_alerta_orden();

-- T2: genera una alerta cuando llega una lectura sobre el umbral
CREATE OR REPLACE FUNCTION fn_alerta_automatica() RETURNS TRIGGER
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.valor_rms >= 4 THEN
    INSERT INTO AlertaMantenimiento(id_sensor, fecha_hora_lectura, fecha_hora, nivel,
           tipo_alerta, valor_detectado, descripcion, estado)
    VALUES (NEW.id_sensor, NEW.fecha_hora, now(),
            CASE WHEN NEW.valor_rms >= 5.5 THEN 'Critica' WHEN NEW.valor_rms >= 5 THEN 'Alta'
                 WHEN NEW.valor_rms >= 4.5 THEN 'Media' ELSE 'Baja' END,
            'Umbral RMS', NEW.valor_rms, 'Vibracion RMS fuera de umbral', 'Abierta');
  END IF;
  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_lectura_alerta ON LecturaVibracion;
CREATE TRIGGER trg_lectura_alerta
AFTER INSERT ON LecturaVibracion
FOR EACH ROW EXECUTE FUNCTION fn_alerta_automatica();

-- T3: completa la fecha de cierre al finalizar una orden
CREATE OR REPLACE FUNCTION fn_fecha_cierre_auto() RETURNS TRIGGER
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.estado = 'Finalizada' AND NEW.fecha_cierre IS NULL THEN
    NEW.fecha_cierre := GREATEST(now(), NEW.fecha_creacion);
  END IF;
  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_orden_fecha_cierre ON OrdenTrabajo;
CREATE TRIGGER trg_orden_fecha_cierre
BEFORE INSERT OR UPDATE ON OrdenTrabajo
FOR EACH ROW EXECUTE FUNCTION fn_fecha_cierre_auto();
