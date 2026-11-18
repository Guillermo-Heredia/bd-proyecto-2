-- =====================================================================
-- 05 - Procedimientos almacenados y función (sección 4.5)
-- Fuente: main.tex (líneas 1542-1600)
-- =====================================================================

-- Crea una orden a partir de una alerta y la vincula
CREATE OR REPLACE PROCEDURE sp_crear_orden_desde_alerta(
    p_id_alerta BIGINT, p_id_tecnico INT, p_tipo VARCHAR, INOUT p_id_orden BIGINT)
LANGUAGE plpgsql AS $$
DECLARE v_turbina INT; v_nivel VARCHAR;
BEGIN
  SELECT c.id_turbina, a.nivel INTO v_turbina, v_nivel
  FROM AlertaMantenimiento a
  JOIN SensorVibracion s   ON s.id_sensor = a.id_sensor
  JOIN ComponenteTurbina c ON c.id_componente = s.id_componente
  WHERE a.id_alerta = p_id_alerta;

  IF v_turbina IS NULL THEN
    RAISE EXCEPTION 'La alerta % no existe', p_id_alerta;
  END IF;

  INSERT INTO OrdenTrabajo(id_turbina, id_tecnico, fecha_creacion, fecha_programada,
                           prioridad, tipo_mantenimiento, descripcion, estado)
  VALUES (v_turbina, p_id_tecnico, now(), now() + INTERVAL '2 days', v_nivel,
          p_tipo, 'Orden generada desde alerta ' || p_id_alerta, 'Pendiente')
  RETURNING id_orden INTO p_id_orden;

  INSERT INTO AlertaOrden(id_alerta, id_orden) VALUES (p_id_alerta, p_id_orden);
  UPDATE AlertaMantenimiento SET estado = 'En revision' WHERE id_alerta = p_id_alerta;
END $$;

-- Cierra una orden y las alertas que atendia
CREATE OR REPLACE PROCEDURE sp_cerrar_orden(p_id_orden BIGINT)
LANGUAGE plpgsql AS $$
BEGIN
  UPDATE OrdenTrabajo SET estado = 'Finalizada', fecha_cierre = now()
  WHERE id_orden = p_id_orden;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'La orden % no existe', p_id_orden;
  END IF;
  UPDATE AlertaMantenimiento SET estado = 'Cerrada'
  WHERE id_alerta IN (SELECT id_alerta FROM AlertaOrden WHERE id_orden = p_id_orden);
END $$;

-- Historial de alertas y ordenes de una turbina en un periodo
CREATE OR REPLACE FUNCTION fn_historial_turbina(
    p_turbina INT, p_desde TIMESTAMP, p_hasta TIMESTAMP)
RETURNS TABLE(origen TEXT, ref_id BIGINT, fecha_evento TIMESTAMP,
              detalle TEXT, estado_reg VARCHAR)
LANGUAGE sql AS $$
  SELECT 'Alerta'::text, a.id_alerta, a.fecha_hora,
         (a.nivel || ' - ' || a.descripcion)::text, a.estado
  FROM AlertaMantenimiento a
  JOIN SensorVibracion s   ON s.id_sensor = a.id_sensor
  JOIN ComponenteTurbina c ON c.id_componente = s.id_componente
  WHERE c.id_turbina = p_turbina AND a.fecha_hora BETWEEN p_desde AND p_hasta
  UNION ALL
  SELECT 'Orden'::text, o.id_orden, o.fecha_creacion,
         (o.prioridad || ' - ' || o.descripcion)::text, o.estado
  FROM OrdenTrabajo o
  WHERE o.id_turbina = p_turbina AND o.fecha_creacion BETWEEN p_desde AND p_hasta
  ORDER BY 3;
$$;
