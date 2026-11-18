# Guía para las 80 capturas de pgAdmin

El informe espera **80 imágenes** con nombres exactos en `informe_hito2/imagenes/`.
El macro `\captura` las busca ahí; si falta una, el PDF muestra un recuadro
"Insertar captura".

## 0. Preparación (una vez)

```bash
# PostgreSQL con las 4 bases
docker start pg-turbinas
docker ps --format '{{.Names}} {{.Status}}' | grep pg-turbinas

# pgAdmin (Flatpak instalado)
flatpak run org.pgadmin.pgadmin4
```

En pgAdmin: clic derecho en *Servers* → **Register → Server**:

| Campo | Valor |
|---|---|
| Name | `pg-turbinas` |
| Host name/address | `localhost` |
| Port | `5432` |
| Maintenance database | `postgres` |
| Username | `postgres` |
| Password | `postgres` |

Marca *Save password*. Luego expande `pg-turbinas → Databases` y verifica
`bd_1k`, `bd_10k`, `bd_100k`, `bd_1m`.

Opcional, para que las capturas se vean como las anteriores:
*File → Preferences → Miscellaneous → Theme → Dark*.

## 1. Reglas de la variante "sin índices"

En pgAdmin, cada pestaña *Query Tool* es una sesión distinta. En **la misma
pestaña**, antes de la consulta:

```sql
SET enable_indexscan = off;
SET enable_indexonlyscan = off;
SET enable_bitmapscan = off;
```

Y además hay que quitar los índices `idx_*` (una vez por base):

```sql
DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT indexname FROM pg_indexes
           WHERE schemaname = 'public' AND indexname LIKE 'idx\_%'
  LOOP EXECUTE format('DROP INDEX IF EXISTS %I', r.indexname); END LOOP;
END $$;
ANALYZE;
```

*(Es el contenido de `../indices/borrar_indices.sql`.)*

## 2. Reglas de la variante "con índices"

En la base correspondiente, ejecuta una vez:

```
../indices/crear_indices.sql
```

(cópialo y pégalo en el Query Tool, o usa el botón *Open File*).

## 3. Flujo por cada consulta y escala

Para `q` en `1..5` y `escala` en `1k, 10k, 100k, 1m`:

1. Abre *Query Tool* sobre `bd_<escala>`.
2. **Sin índices**:
   - Ejecuta las 3 líneas `SET ...` (y el bloque `DO` si aún hay `idx_*`).
   - Abre `../consultas/c<q>.sql` y ejecútalo (F5). El archivo ya trae
     `EXPLAIN ANALYZE`.
   - Pestaña **Data Output** → captura el texto `QUERY PLAN` →
     guarda `imagenes/c<q>_<escala>_sin_plan.png`.
   - Botón **Explain** (F7) con *Analyze* y *Buffers* activados → pestaña del
     **árbol** → guarda `imagenes/c<q>_<escala>_sin_tree.png`.
3. **Con índices**:
   - Si es la primera consulta de esa base, ejecuta `crear_indices.sql`.
   - Abre `../consultas/c<q>.sql`, ejecútalo y repite las dos capturas →
     `c<q>_<escala>_con_plan.png` y `c<q>_<escala>_con_tree.png`.
4. Recorta cada captura al panel del plan (sin barras laterales ni escritorio).

> Si el panel *Explain* de pgAdmin te muestra también la pestaña de texto,
> puedes sacar `plan` y `tree` de la **misma** corrida. Si no, ejecuta el
> archivo para el texto y F7 para el árbol.

## 4. Nombres exactos (los 80)

Para cada `q` en `1..5` y cada escala:

```
c<q>_1k_sin_plan.png      c<q>_1k_con_plan.png
c<q>_1k_sin_tree.png      c<q>_1k_con_tree.png
c<q>_10k_sin_plan.png     c<q>_10k_con_plan.png
c<q>_10k_sin_tree.png     c<q>_10k_con_tree.png
c<q>_100k_sin_plan.png    c<q>_100k_con_plan.png
c<q>_100k_sin_tree.png    c<q>_100k_con_tree.png
c<q>_1m_sin_plan.png      c<q>_1m_con_plan.png
c<q>_1m_sin_tree.png      c<q>_1m_con_tree.png
```

## 5. Orden recomendado (por lotes)

1. **1k y 10k**: rápidas, sirven para practicar el flujo.
2. **100k**: todas tardan segundos.
3. **1M con índices**: segundos.
4. **1M sin índices**: al final, porque C1 tarda ~3.3 min y C5 ~9.6 min por
   corrida. Si haces texto y árbol en corridas separadas, C5 puede tardar
   ~20 min.

## 6. Verificación

```bash
ls informe_hito2/imagenes/*.png | wc -l          # debe dar 80
cd informe_hito2 && latexmk -pdf main.tex        # regenera el PDF
```

Si faltan imágenes, el PDF compila igual pero deja recuadros
"Insertar captura" en su lugar.
