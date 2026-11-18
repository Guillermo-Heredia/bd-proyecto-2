# Versión de Guille: Hito 2 en PostgreSQL, ordenado y medido

En esta carpeta está todo el código PostgreSQL del proyecto, separado en archivos, más un programa que mide las consultas **sin índices (de verdad)** contra **con índices elegidos por teoría** en las 4 escalas y genera tablas y gráficas.

> **Cambios importantes respecto al `main.tex` actual** (detalle en las secciones 3 y 4):
> 1. El "sin índices" del informe **no era real**: quedaban activos los índices de las llaves primarias y PostgreSQL los usaba.
> 2. **Se reemplazaron las 5 consultas** por versiones no triviales donde el índice es decisivo. Las anteriores están en `consultas/anteriores/`.
> 3. Los índices se eligieron **por teoría**: Hash para igualdad (`=`), B+ tree para rango y orden.
>
> Por eso hay que actualizar en el informe las secciones 5.1 a 5.7 (ver la sección 7, "Qué falta").

---

## 1. Estructura

```
version_guille/
├── README.md
├── crear_todo.sh                    ← crea bd_1k, bd_10k, bd_100k, bd_1m y sus dumps
├── sql/                             ← en ESTE orden
│   ├── 01_tablas.sql                (4.1 – main.tex 1344-1441)
│   ├── 02_carga_datos.sql           (4.2 – script ORIGINAL del Drive; n se pasa con -v n=)
│   ├── 03_datos_faltantes.sql       (4.3)
│   ├── 04_vistas.sql                (4.4)
│   ├── 05_procedimientos.sql        (4.5)
│   └── 06_triggers.sql              (4.6 – se crean DESPUÉS de la carga)
├── consultas/                       ← las 5 consultas FINALES (con EXPLAIN ANALYZE)
│   ├── c1.sql … c5.sql
│   └── anteriores/                  ← las 5 del main.tex actual (ya no se usan)
├── indices/
│   ├── crear_indices.sql            ← índices finales (= variantes/teoria.sql)
│   ├── borrar_indices.sql           ← borra todos los idx_*
│   └── variantes/sin.sql, teoria.sql
├── benchmark/
│   ├── benchmark.py                 ← el programa de medición (sin vs con, N repeticiones, gráficas)
│   └── requirements.txt
├── experimento/
│   ├── medir_consultas.sh           ← alternativa solo con psql (sin vs con)
│   ├── costo_actualizacion.sql      ← INSERT/UPDATE/DELETE sin vs con, a mano
│   ├── probar_sp_triggers.sql       ← prueba de vistas, SP y triggers (con ROLLBACK)
│   └── anteriores/                  ← scripts de la versión anterior
├── dumps/                           ← bd_1k/10k/100k/1m.dump (pg_restore)
└── resultados/
    ├── benchmark/                   ← RESULTADOS FINALES: reporte.html, CSV, gráficas PNG
    ├── benchmark_corrida1_c2c3_anteriores/  ← corrida previa (C2/C3 anteriores)
    ├── prueba_sp_triggers.txt
    └── anteriores/                  ← mediciones con las consultas anteriores
├── informe_hito2/                   ← INFORME DEL HITO 2
│   ├── main.tex                     ← copia de ../main.tex (secciones 1–4 del Hito 1)
│   ├── seccion5.tex                 ← sección 5 generada desde los CSV
│   ├── generar_seccion5.py          ← regenera tablas y texto de la sección 5
│   ├── consultas/c1…c5.sql          ← copia de las consultas finales
│   ├── imagenes/                    ← aquí van las 80 capturas de pgAdmin
│   └── GUIA_CAPTURAS.md             ← paso a paso para las capturas
```

---

## 2. Las 5 consultas finales

Las 5 trabajan sobre `LecturaVibracion`, que es la tabla que crece con la escala, y responden preguntas de mantenimiento predictivo.

| C | Pregunta de negocio | Construcción SQL | Predicado clave | Índice por teoría |
|---|---|---|---|---|
| **1** | ¿Qué lecturas anómalas (RMS ≥ 4) superan en 1.5 veces o más el promedio de las 24 h previas de su sensor? | CTE MATERIALIZED + **subconsulta correlacionada** + 4 JOIN | `id_sensor =` y `fecha_hora` en rango de 24 h; `valor_rms >= 4` | B+ tree `(id_sensor, fecha_hora)`; B+ tree `(valor_rms)` |
| **2** | En las últimas 48 h, ¿qué sensores vibran más que el promedio de su parque? (top 5 por parque) | `MAX` escalar + 3 CTE + **percentil 95** + 4 JOIN + **RANK() OVER (PARTITION BY parque)** | `fecha_hora >= MAX − 48 h` (rango) | B+ tree `(fecha_hora)` cubriente |
| **3** | ¿Qué turbinas tienen más rachas de ≥3 lecturas consecutivas con RMS > 2.5? (top 10) | 3 CTE + **2 ROW_NUMBER() (gaps & islands)** + HAVING + 4 JOIN + **DENSE_RANK** | `PARTITION BY id_sensor ORDER BY fecha_hora` (orden) | B+ tree `(id_sensor, fecha_hora)` |
| **4** | ¿Cómo venía la vibración en las 5 lecturas previas a cada alerta grave? (por parque y componente) | 2 CTE + **JOIN LATERAL … ORDER BY DESC LIMIT 5** + **regr_slope** + 4 JOIN | `id_sensor =`, `fecha_hora <` + orden; `nivel IN (…)` | B+ tree `(id_sensor, fecha_hora)`; Hash `(nivel)` |
| **5** | ¿Qué turbinas pasan más rápido de "normal" a "alerta"? (top 10, con alertas sin orden) | CTE + **correlacionada con MAX** + **NOT EXISTS** + FILTER + 4 JOIN | `id_sensor =`, `fecha_hora <`; `ao.id_alerta =` | B+ tree `(id_sensor, fecha_hora)`; Hash `AlertaOrden(id_alerta)` |

Además, por teoría, van **Hash** en las FK de los joins (`SensorVibracion(id_componente)`, `ComponenteTurbina(id_turbina)` y `Turbina(id_parque)`). Todo está en `indices/crear_indices.sql`.

**Regla teórica:** la igualdad (`=`, `IN`, join por llave) va con **Hash**. El rango, la desigualdad y el orden (`<`, `>`, `>=`, `ORDER BY`, `PARTITION BY … ORDER BY`) van con **B+ tree**. Si son varias columnas con igualdad + rango, también **B+ tree**, porque Hash solo admite una columna y solo sirve para `=`. En PostgreSQL, `CREATE INDEX` sin `USING` crea un B-tree, que es un B+ tree.

### Tamaño y complejidad frente a Bodega Jessica

| Consulta | Líneas | Tablas | SELECT anidados | Técnicas |
|---|---:|---:|---:|---|
| Jessica C1 | 16 | 10 | 6 | IN (subconsulta), tablas derivadas, AVG escalar, GROUP BY, EXTRACT |
| Jessica C2 | 31 | 8 | 11 | UNION de 2 bloques casi iguales, IN anidado, LIKE, LIMIT |
| Jessica C3 | 33 | 13 | 6 | 4 JOIN, 2 IN (subconsulta), tablas derivadas |
| **Nuestra C1** | 21 | 6 | 3 | CTE, correlacionada por rango, 4 JOIN |
| **Nuestra C2** | 40 | 10 | 6 | 3 CTE, percentil, RANK por parque |
| **Nuestra C3** | 33 | 6 | 4 | 3 CTE, 2 ventanas, DENSE_RANK |
| **Nuestra C4** | 31 | 8 | 4 | 2 CTE, LATERAL + LIMIT, regr_slope |
| **Nuestra C5** | 25 | 8 | 4 | CTE, correlacionada, NOT EXISTS, FILTER |

Las de Jessica se ven grandes, pero buena parte es **repetición**: en C2 el mismo bloque aparece dos veces por el UNION, y en C1 y C3 la misma suma se calcula dos veces. Nuestras consultas son de tamaño similar, con técnicas más avanzadas (correlación, LATERAL, ventanas, percentiles, anti-join).

---

## 3. ¿Por qué antes "sin índices" salía igual o mejor? (lo que notó el profesor)

1. **No era "sin índices".** En el informe (sección 5.2) y en el Drive solo se borraban los índices propios. Quedaban **12 índices B+ tree automáticos** (PK y UNIQUE) y PostgreSQL los usaba en la prueba "sin". Por ejemplo, la C3 anterior hacía `Index Scan using lecturavibracion_pkey`, porque esa PK es justo `(id_sensor, fecha_hora)`.
   **Corrección:** las PK no se pueden borrar sin romper las FK, así que en la prueba "sin" se apaga su uso en la sesión:
   ```sql
   SET enable_indexscan = off;  SET enable_indexonlyscan = off;  SET enable_bitmapscan = off;
   ```
   El programa verifica en cada plan que "sin" use solo Seq Scan. En los 20 casos dio **"no usa índice"**.
2. **Las consultas anteriores eran baratas por naturaleza.** Eran joins por igualdad sobre tablas chicas (alertas, órdenes), y PostgreSQL los resuelve con Hash Join sin necesitar índices. Las nuevas hacen **una búsqueda por cada alerta o lectura anómala** dentro de la tabla grande. Sin índice, cada búsqueda lee la tabla completa, así que el costo crece como **N²**. Con índice es un salto directo en el B+ tree. Así pasan las consultas "de 48 horas" de otros grupos.

---

## 4. Resultados finales (`resultados/benchmark/`)

Medidos en esta PC (sección 5) el 16/11/2026. Cada valor es el **promedio de 5 ejecuciones**, después de 1 de calentamiento. Si una ejecución pasa de 120 s se mide **una sola vez** (n=1). Abrir `resultados/benchmark/reporte.html` para ver todas las tablas, planes y gráficas.

### Tiempo promedio (ms)

| C | Escala | Sin índices | Con índices | Variación | Veredicto |
|---|---|---:|---:|---:|---|
| 1 | 1k | 0.35 | 0.06 | −82 % | Mejora real |
| 1 | 10k | 24.2 | 0.53 | −97.8 % | Mejora real |
| 1 | 100k | 2 028 | 4.99 | −99.8 % | Mejora real |
| 1 | **1M** | **197 558 (3.3 min, n=1)** | **56.0** | **≈3 500× más rápido** | Mejora real |
| 2 | 1k | 3.50 | 3.46 | −1 % | Empate (ruido) |
| 2 | 10k | 14.4 | 13.6 | −5 % | Empate (ruido) |
| 2 | 100k | 60.0 | 48.0 | −20 % | Mejora real |
| 2 | **1M** | **166.0** | **50.5** | **−69.5 %** | Mejora real |
| 3 | 1k | 1.42 | 1.40 | −2 % | Empate (el plan no usa índice) |
| 3 | 10k | 13.2 | 13.6 | +3.5 % | Empate (ruido) |
| 3 | 100k | 148.4 | 144.6 | −2.6 % | Mejora real |
| 3 | **1M** | **1 646** | **1 444** | **−12.3 %** | Mejora real |
| 4 | 1k | 0.38 | 0.25 | −33 % | Mejora real |
| 4 | 10k | 10.7 | 0.45 | −95.8 % | Mejora real |
| 4 | 100k | 1 115 | 3.55 | −99.7 % | Mejora real |
| 4 | **1M** | **92 573 (1.5 min)** | **36.3** | **≈2 500×** | Mejora real |
| 5 | 1k | 0.46 | 0.06 | −87 % | Mejora real |
| 5 | 10k | 74.8 | 0.78 | −99 % | Mejora real |
| 5 | 100k | 5 933 | 5.61 | −99.9 % | Mejora real |
| 5 | **1M** | **575 110 (9.6 min, n=1)** | **71.8** | **≈8 000×** | Mejora real |

### Cómo leerlo

- **C1, C4 y C5 (búsqueda por cada alerta o lectura):** sin índices, el tiempo se multiplica por **~100** cada vez que los datos crecen 10 veces (cuadrático). Con índices, solo por ~10 (lineal). La gráfica en escala log muestra dos rectas que se separan.
- **C2 (rango de 48 h):** con pocos datos, 48 h abarcan toda la tabla y el índice no ayuda. Con 1M son ~4 % de las filas y el índice reduce el tiempo un 70 %. **La ganancia crece con el volumen.**
- **C3 (rachas, recorre toda la tabla):** el índice solo evita ordenar, porque entrega las lecturas ya ordenadas por `(id_sensor, fecha_hora)`. Pero hay que procesar el millón de filas igual, así que la mejora es pequeña (−12 % con 1M). Es el ejemplo de **cuándo un índice ayuda poco**: consultas que necesitan todas las filas.
- Con 1k casi todo está por debajo de 1 ms y las diferencias son ruido. Por eso importan las escalas grandes.

### Costo de actualización con 1M (ms, cada operación con ROLLBACK)

| Operación | Sin índices | Con índices | Comentario |
|---|---:|---:|---|
| INSERT 1 000 lecturas | 25.0 | 16.7 | Sin índices, hasta la verificación de las FK y el trigger tienen que buscar con Seq Scan |
| UPDATE `valor_rms` de 1 día | 170.3 | **271.6** | **Los índices encarecen**: hay que actualizar también los B+ tree que incluyen `valor_rms` |
| UPDATE estado de alertas | 7.3 | 8.0 | Igual (tabla chica) |
| DELETE de 1 día (con NOT EXISTS) | **958 585 (16 min, n=1)** | **5 956** | El anti-join necesita buscar; sin índice es N² |

Espacio: los índices por teoría ocupan **105.7 MB** con 1M; la tabla de lecturas ocupa ~65 MB.

### Corrida anterior

`resultados/benchmark_corrida1_c2c3_anteriores/` tiene la misma medición con las C2 y C3 anteriores. C1, C4 y C5 dieron prácticamente lo mismo (182 s / 95 s / 557 s sin índices con 1M), lo que confirma que los resultados son reproducibles.

---

## 5. Plataforma de pruebas (esta PC)

| Componente | Descripción |
|---|---|
| Procesador | Intel Core i5-1035G4 @ 1.10 GHz (4 núcleos / 8 hilos) |
| Memoria RAM | 12 GB (11.4 GiB utilizables) |
| Almacenamiento | SSD NVMe SK Hynix 512 GB |
| Sistema operativo | Fedora Linux 44 Workstation (kernel 7.3.3) |
| PostgreSQL | 16.15, en Docker (imagen `postgres:16`, contenedor `pg-turbinas`, `shared_buffers` 128 MB) |
| Cliente | `psql` 16.15 y `benchmark.py` (Python 3.14 + psycopg 3.3), sin pgAdmin |

---

## 6. Cómo correr todo

```bash
# 1) PostgreSQL en Docker (una vez)
docker run -d --name pg-turbinas -e POSTGRES_PASSWORD=postgres -p 5432:5432 \
  -v "$PWD":/work:Z -w /work postgres:16
docker start pg-turbinas                       # las siguientes veces

# 2) Crear las 4 bases y los dumps (~30 s)
docker exec -e PGUSER=postgres pg-turbinas bash -c 'cd /work && bash crear_todo.sh'

# 3) Programa de medición (una vez: crear el entorno de Python)
python3 -m venv benchmark/.venv && benchmark/.venv/bin/pip install -r benchmark/requirements.txt
benchmark/.venv/bin/python benchmark/benchmark.py -n 2 -e 1k,10k   # prueba rápida (segundos)
benchmark/.venv/bin/python benchmark/benchmark.py                  # completo: 5 repeticiones, 4 escalas (~40 min)
benchmark/.venv/bin/python benchmark/benchmark.py --solo-reporte   # rehace gráficas y HTML sin medir
xdg-open resultados/benchmark/reporte.html

# 4) Ver a mano un plan sin índices y con índices (consola psql)
docker exec -it -e PGUSER=postgres pg-turbinas psql -d bd_1m
#   \i /work/indices/crear_indices.sql
#   \i /work/consultas/c5.sql                                   -- con índices
#   SET enable_indexscan=off; SET enable_indexonlyscan=off; SET enable_bitmapscan=off;
#   \i /work/consultas/c5.sql                                   -- sin índices (~10 min con 1M)

# 5) Probar vistas, SP y triggers
docker exec -e PGUSER=postgres pg-turbinas psql -X -d bd_1m -f /work/experimento/probar_sp_triggers.sql
```
Opciones de `benchmark.py`:
- `-n` repeticiones (5 por defecto)
- `-e` escalas (`1k,10k,100k,1m`)
- `--umbral-lento` segundos a partir de los cuales una ejecución no se repite (120)
- `--escalas-actualizacion` dónde se mide INSERT/UPDATE/DELETE (`1m`)

Si los archivos generados desde Docker quedan como root: `docker exec pg-turbinas chown -R $(id -u):$(id -g) /work/resultados /work/dumps`.

---

## 7. Qué falta en `main.tex` (comparado con `Proyecto Final-1.pdf`)

> **Hito 2:** el informe ya está armado en `informe_hito2/`. Las tablas y el
> texto de la sección 5 se generan desde `resultados/benchmark/` con
> `python3 informe_hito2/generar_seccion5.py`; solo faltan las 80 capturas de
> pgAdmin (ver `informe_hito2/GUIA_CAPTURAS.md`). Compilar con
> `cd informe_hito2 && latexmk -pdf main.tex`.

Leyenda: ✅ listo · ⚠️ hay que actualizarlo · ❌ falta

| Sección | Estado | Qué hacer |
|---|---|---|
| 4.1–4.6 (tablas, carga, faltantes, vistas, SP, triggers) | ✅ | Agregar a 4.2 la tabla de filas por dump (abajo) y un extracto del `generate_series`. En 4.6, decir que los triggers se crean después de la carga |
| 5.1 Descripción e implementación de las 5 consultas | ⚠️ | **Reemplazar** por las de `consultas/c1…c5.sql`. La tabla de la sección 2 sirve para describirlas |
| 5.2 Metodología | ⚠️ | Explicar `SET enable_*scan = off` en "sin", el calentamiento, las 5 repeticiones, el corte de 120 s (n=1) y que todo se mide en una sola sesión con `benchmark.py` |
| 5.3 Índices por consulta | ⚠️ | Usar `indices/crear_indices.sql` y justificar cada uno con la regla teórica (Hash para `=`, B+ tree para rango y orden) |
| 5.4 Plataforma de pruebas | ❌ | La tabla sigue con los espacios en rojo. Copiar la sección 5 |
| 5.5 Medición de tiempos | ⚠️ | Rehacer con `resultados/benchmark/tiempos.csv` (cada ejecución) y `resumen.csv` (promedio y desviación) |
| 5.6 Resultados | ⚠️ | Rehacer las capturas de los planes de las 5 consultas nuevas y agregar las gráficas `resultados/benchmark/grafica_C*.png` |
| Costo de actualización | ❌ | El PDF lo pide ("tiempos de actualización"). Agregar la tabla de la sección 4 |
| 5.7 Análisis | ⚠️ | Reescribir con la sección 4: cuadrático vs lineal, cuándo el índice ayuda poco (C3) y el costo en escrituras |
| Pregunta extra (más de 1M) | ⚠️ | Ahora hay datos concretos: C5 sin índices pasa de 6 s (100k) a 9.6 min (1M), así que con 10M serían ~16 h. Con índices, ~0.7 s |
| 7 Anexos | ⚠️ | Links separados al video de 1M sin y con índices, a los dumps y a los scripts |
| MVP web (+2) | ❌ | Opcional |

### Filas por dump (para la sección 4.2)

| Tabla | 1k | 10k | 100k | 1M |
|---|---:|---:|---:|---:|
| ParqueEolico / Turbina / Componente / Sensor / Técnico | 5 / 100 / 400 / 800 / 30 | igual | igual | igual |
| LecturaVibracion | 1 000 | 10 000 | 100 000 | 1 000 000 |
| AlertaMantenimiento | 5 | 54 | 519 | 5 019 |
| OrdenTrabajo | 10 | 20 | 200 | 2 000 |
| AlertaOrden | 0 | 4 | 122 | 1 260 |

La carga no fija semilla aleatoria, así que estos conteos cambian un poco cada vez que se regeneran las bases. Para el informe, usen los dumps de `dumps/`.

### Vistas, procedimientos y triggers (`resultados/prueba_sp_triggers.txt`)

| Objeto | Resultado |
|---|---|
| 3 vistas | ✅ Devuelven datos |
| `sp_crear_orden_desde_alerta` | ✅ Crea la orden, la vincula y deja la alerta "En revision" |
| `sp_cerrar_orden` | ✅ La orden pasa a "Finalizada" y su alerta a "Cerrada" |
| `fn_historial_turbina` | ✅ |
| T1 consistencia de turbina | ✅ Rechaza vincular una alerta de otra turbina |
| T2 alerta automática | ✅ Una lectura con RMS 5.8 crea una alerta "Critica" |
| T3 fecha de cierre | ✅ Completa `fecha_cierre` al finalizar |
| ⚠️ Caso borde | `sp_cerrar_orden` sobre una orden **Pendiente sin técnico** falla con un error genérico de CHECK. Conviene validarlo con un mensaje claro |

---

## 8. Origen del código (Drive vs `main.tex`)

| Archivo del Drive (`bd_proyecto_drive/`) | ¿Igual al .tex? | Dónde quedó |
|---|---|---|
| `tablas.sql` | ✅ | `sql/01_tablas.sql` |
| `carga de datos.sql` | (no está en el .tex) | `sql/02_carga_datos.sql`, original; solo se parametrizó `n` |
| `Datos faltantes, vistas, procedimientos y triggers.sql` | ✅ | `sql/03…06` |
| `consultas.sql` | ✅ | `consultas/anteriores/` (reemplazadas) |
| `Los índices de la optimización.sql` | ✅ | Reemplazados por `indices/crear_indices.sql` (por teoría) |
| `script que mide los tiempos….sql` | (no está en el .tex) | `experimento/anteriores/medir_tiempos_en_sql.sql` |
