#!/usr/bin/env bash
# =====================================================================
# Crea las 4 bases (1k, 10k, 100k, 1M lecturas), las llena y genera los dumps.
#
# Uso (desde la carpeta version_guille):
#   bash crear_todo.sh              # las 4 bases
#   bash crear_todo.sh 1000         # solo bd_1k (para probar rápido)
#
# Conexión: PGHOST, PGPORT, PGUSER, PGPASSWORD (ej. export PGUSER=postgres)
# =====================================================================
set -euo pipefail
export PGOPTIONS="${PGOPTIONS:--c client_min_messages=warning}"   # oculta los NOTICE
cd "$(dirname "$0")"

declare -A NOMBRE=([1000]=bd_1k [10000]=bd_10k [100000]=bd_100k [1000000]=bd_1m)
ESCALAS=("${@:-1000 10000 100000 1000000}")
ESCALAS=(${ESCALAS[*]})
PSQL="psql -X -q -v ON_ERROR_STOP=1"

mkdir -p dumps
for n in "${ESCALAS[@]}"; do
  bd=${NOMBRE[$n]}
  echo "=========== $bd ($n lecturas) ==========="
  dropdb --if-exists "$bd"
  createdb "$bd"
  $PSQL -d "$bd" -f sql/01_tablas.sql
  $PSQL -d "$bd" -v n="$n" -f sql/02_carga_datos.sql
  $PSQL -d "$bd" -f sql/03_datos_faltantes.sql
  $PSQL -d "$bd" -f sql/04_vistas.sql
  $PSQL -d "$bd" -f sql/05_procedimientos.sql
  $PSQL -d "$bd" -f sql/06_triggers.sql      # después de la carga (ver 06_triggers.sql)
  pg_dump -Fc -d "$bd" -f "dumps/$bd.dump"
  echo "Dump: dumps/$bd.dump"
done
echo "Listo. Restaurar un dump con: pg_restore -d <bd_vacia> dumps/bd_1m.dump"
