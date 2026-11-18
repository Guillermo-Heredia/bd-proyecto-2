#!/usr/bin/env bash
# =====================================================================
# Mide las 5 consultas, 5 veces cada una, en las 4 bases, SIN y CON índices.
# Solo usa psql (no hace falta pgAdmin).
#
# Uso (desde la carpeta version_guille):
#   bash experimento/medir_consultas.sh
#
# Conexión: usa las variables estándar de PostgreSQL si están definidas
#   PGHOST, PGPORT, PGUSER, PGPASSWORD   (ej. export PGUSER=postgres)
#
# Salida:
#   resultados/tiempos.csv          modo,bd,consulta,ejecucion,ms
#   resultados/resumen.csv          promedio y desviación estándar
#   resultados/planes/cN_<bd>_<modo>.txt   plan completo (texto) de la 1ª ejecución
# =====================================================================
set -euo pipefail
export PGOPTIONS="${PGOPTIONS:--c client_min_messages=warning}"   # oculta los NOTICE
cd "$(dirname "$0")/.."

BASES=(bd_1k bd_10k bd_100k bd_1m)
REPETICIONES=5
PSQL="psql -X -q -v ON_ERROR_STOP=1"

mkdir -p resultados/planes
echo "modo,bd,consulta,ejecucion,ms" > resultados/tiempos.csv

medir() {   # $1 = sin|con
  local modo=$1
  for bd in "${BASES[@]}"; do
    if [ "$modo" = "sin" ]; then
      $PSQL -d "$bd" -f indices/borrar_indices.sql
      # Borrar los idx_* NO basta: las PK/UNIQUE también son índices B+ tree.
      # Se apaga el uso de cualquier índice en la sesión -> solo Seq Scan.
      export PGOPTIONS="-c client_min_messages=warning -c enable_indexscan=off -c enable_indexonlyscan=off -c enable_bitmapscan=off"
    else
      export PGOPTIONS="-c client_min_messages=warning"
      $PSQL -d "$bd" -f indices/crear_indices.sql
    fi
    $PSQL -d "$bd" -c "VACUUM ANALYZE;"
    for c in 1 2 3 4 5; do
      # 1 ejecución de calentamiento (no se cuenta) para que todas partan con caché caliente
      $PSQL -d "$bd" -f "consultas/c$c.sql" > /dev/null
      for r in $(seq 1 "$REPETICIONES"); do
        salida=$($PSQL -d "$bd" -f "consultas/c$c.sql")
        [ "$r" -eq 1 ] && echo "$salida" > "resultados/planes/c${c}_${bd}_${modo}.txt"
        ms=$(echo "$salida" | grep -oP 'Execution Time: \K[0-9.]+')
        echo "$modo,$bd,$c,$r,$ms" >> resultados/tiempos.csv
        echo "  [$modo] $bd  C$c  ejecución $r: $ms ms"
      done
    done
  done
}

echo "== Prueba SIN índices =="; medir sin
echo "== Prueba CON índices =="; medir con

# Promedio y desviación estándar muestral por (modo, bd, consulta)
awk -F, 'NR>1 { k=$1","$2","$3; n[k]++; s[k]+=$5; q[k]+=$5*$5 }
  END { for (k in n) { m=s[k]/n[k]; v=(q[k]-n[k]*m*m)/(n[k]-1); if (v<0) v=0;
                       printf "%s,%.2f,%.2f\n", k, m, sqrt(v) } }' \
  resultados/tiempos.csv | sort -t, -k1,1r -k2,2V -k3,3n > resultados/resumen.tmp
{ echo "modo,bd,consulta,promedio_ms,desv_std_ms"; cat resultados/resumen.tmp; } > resultados/resumen.csv
rm resultados/resumen.tmp

echo
echo "Listo. Ver resultados/resumen.csv"
if command -v column >/dev/null; then column -s, -t resultados/resumen.csv; else cat resultados/resumen.csv; fi
