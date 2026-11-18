#!/usr/bin/env python3
"""
Benchmark de índices: SIN índices (de verdad) vs CON índices elegidos por teoría
(= -> Hash, rango/orden -> B+ tree), en 1k / 10k / 100k / 1M.

Para cada escala y variante:
  1. borra todos los índices idx_*
  2. "sin":    además apaga el uso de TODO índice en la sesión, incluidas las PK/UNIQUE
              (SET enable_indexscan/indexonlyscan/bitmapscan = off) -> solo Seq Scan
     "teoria": crea los índices de indices/variantes/teoria.sql (y las PK se pueden usar)
  3. VACUUM ANALYZE
  4. por cada consulta: 1 corrida de calentamiento + N corridas con
     EXPLAIN (ANALYZE, FORMAT JSON) -> tiempo + qué índice/scan usó el plan.
     Si una corrida pasa de --umbral-lento segundos (120 por defecto) no se repite:
     queda como ejecución única (las consultas sin índice en 1M pueden tardar mucho).
  5. (solo en las escalas de --escalas-actualizacion) mide INSERT/UPDATE/DELETE
     N veces, cada uno dentro de una transacción que se deshace (ROLLBACK)

Salida en resultados/benchmark/:
  tiempos.csv, resumen.csv, actualizacion.csv, tamanos.csv,
  graficas PNG y reporte.html (abrir en el navegador).

Uso (desde version_guille/):
  benchmark/.venv/bin/python benchmark/benchmark.py                 # todo, 5 repeticiones
  benchmark/.venv/bin/python benchmark/benchmark.py -n 3 -e 1k      # prueba rápida
  benchmark/.venv/bin/python benchmark/benchmark.py --solo-reporte  # rehace gráficas con el CSV

Conexión: PGHOST/PGPORT/PGUSER/PGPASSWORD (por defecto localhost:5432 postgres/postgres).
"""
import argparse
import csv
import html
import os
import statistics
import time
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent          # version_guille/
SALIDA = RAIZ / "resultados" / "benchmark"

ESCALAS = {"1k": "bd_1k", "10k": "bd_10k", "100k": "bd_100k", "1m": "bd_1m"}
VARIANTES = ["sin", "teoria"]
NOMBRE_VARIANTE = {"sin": "Sin índices", "teoria": "Con índices (teoría)"}
COLOR = {"sin": "#d62728", "teoria": "#2ca02c"}
APAGAR_INDICES = ("SET enable_indexscan = off", "SET enable_indexonlyscan = off",
                  "SET enable_bitmapscan = off")
PRENDER_INDICES = ("RESET enable_indexscan", "RESET enable_indexonlyscan", "RESET enable_bitmapscan")

TITULO_CONSULTA = {
    "C1": "C1 · Lecturas anómalas vs promedio de sus 24 h previas (correlacionada)",
    "C2": "C2 · Sensores sobre el promedio de su parque, últimas 48 h (rango + RANK)",
    "C3": "C3 · Turbinas con rachas de vibración alta (gaps & islands)",
    "C4": "C4 · Tendencia de las 5 lecturas previas a cada alerta grave (LATERAL)",
    "C5": "C5 · Turbinas que se degradan más rápido (correlacionada + NOT EXISTS)",
}

# Operaciones de actualización (cada una se ejecuta y se deshace con ROLLBACK)
ACTUALIZACIONES = {
    "INSERT 1000 lecturas": """
        INSERT INTO LecturaVibracion(id_sensor, fecha_hora, valor_rms, valor_pico, frecuencia_dominante_hz)
        SELECT (i % 800) + 1, TIMESTAMP '2027-01-01' + i * INTERVAL '1 hour', 1.5, 2.5, 120
        FROM generate_series(0, 999) AS i""",
    "UPDATE rms 1 día": """
        UPDATE LecturaVibracion SET valor_rms = valor_rms + 0.0001
        WHERE fecha_hora >= '2026-01-01' AND fecha_hora < '2026-01-02'""",
    "UPDATE estado alertas": """
        UPDATE AlertaMantenimiento SET estado = 'Cerrada' WHERE nivel = 'Baja'""",
    "DELETE 1 día": """
        DELETE FROM LecturaVibracion l
        WHERE l.fecha_hora >= '2026-01-02' AND l.fecha_hora < '2026-01-03'
          AND NOT EXISTS (SELECT 1 FROM AlertaMantenimiento a
                          WHERE a.id_sensor = l.id_sensor AND a.fecha_hora_lectura = l.fecha_hora)""",
}


# ----------------------------------------------------------------------------- utilidades
def leer_consultas():
    """Lee consultas/c1..c5.sql quitando comentarios, EXPLAIN ANALYZE y el ';' final."""
    consultas = {}
    for i in range(1, 6):
        lineas = []
        for ln in (RAIZ / "consultas" / f"c{i}.sql").read_text(encoding="utf-8").splitlines():
            if ln.strip().startswith("--") or ln.strip().upper() == "EXPLAIN ANALYZE":
                continue
            lineas.append(ln)
        consultas[f"C{i}"] = "\n".join(lineas).strip().rstrip(";")
    return consultas


def conectar(bd):
    import psycopg
    return psycopg.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5432"),
        user=os.environ.get("PGUSER", "postgres"),
        password=os.environ.get("PGPASSWORD", "postgres"),
        dbname=bd, autocommit=True,
    )


def sql_sin_comentarios(texto):
    return "\n".join(l for l in texto.splitlines() if not l.strip().startswith("--"))


def aplicar_variante(conn, variante):
    """Borra todos los idx_* y crea los de la variante. Devuelve segundos de creación."""
    with conn.cursor() as cur:
        cur.execute("SELECT indexname FROM pg_indexes WHERE schemaname='public' AND indexname LIKE 'idx\\_%'")
        for (nombre,) in cur.fetchall():
            cur.execute(f'DROP INDEX IF EXISTS "{nombre}"')
        t0 = time.perf_counter()
        ddl = sql_sin_comentarios((RAIZ / "indices" / "variantes" / f"{variante}.sql").read_text(encoding="utf-8"))
        for sentencia in (s.strip() for s in ddl.split(";")):
            if sentencia:
                cur.execute(sentencia)
        t_creacion = time.perf_counter() - t0
        cur.execute("VACUUM ANALYZE")
        for sentencia in (APAGAR_INDICES if variante == "sin" else PRENDER_INDICES):
            cur.execute(sentencia)
    return t_creacion


def tamanos_indices(conn):
    with conn.cursor() as cur:
        cur.execute("""SELECT indexrelname, relname, pg_relation_size(indexrelid)
                       FROM pg_stat_user_indexes WHERE indexrelname LIKE 'idx\\_%'""")
        return cur.fetchall()


def accesos_del_plan(plan):
    """Recorre el plan JSON y devuelve los scans usados, p. ej. 'Index Scan[idx_x]'."""
    vistos = []

    def visitar(nodo):
        tipo = nodo.get("Node Type", "")
        if "Scan" in tipo and tipo not in ("Subquery Scan", "CTE Scan", "Function Scan"):
            etiqueta = tipo
            if "Index Name" in nodo:
                etiqueta += f"[{nodo['Index Name']}]"
            elif "Relation Name" in nodo:
                etiqueta += f"({nodo['Relation Name']})"
            if etiqueta not in vistos:
                vistos.append(etiqueta)
        for hijo in nodo.get("Plans", []):
            visitar(hijo)

    visitar(plan["Plan"])
    # ¿el plan usa ALGÚN índice (también PK/UNIQUE)?
    usa = any("Index" in v or "Bitmap" in v for v in vistos)
    # interesa sobre todo cómo se accede a las tablas grandes
    relevantes = [v for v in vistos if any(t in v for t in
                  ("lectura", "alerta", "orden", "idx_", "Bitmap"))]
    return "; ".join(relevantes or vistos), usa


def explain(cur, sql):
    cur.execute("EXPLAIN (ANALYZE, FORMAT JSON) " + sql)
    plan = cur.fetchone()[0][0]
    acceso, usa = accesos_del_plan(plan)
    return plan["Execution Time"], acceso, usa


# ----------------------------------------------------------------------------- medición
def medir(args):
    import psycopg  # noqa: F401  (falla temprano si no está instalado)
    SALIDA.mkdir(parents=True, exist_ok=True)
    consultas = leer_consultas()
    escalas = [e for e in args.escalas.split(",") if e]
    variantes = [v for v in args.variantes.split(",") if v]
    esc_act = [e for e in args.escalas_actualizacion.split(",") if e]

    f_t = open(SALIDA / "tiempos.csv", "w", newline="", encoding="utf-8")
    f_a = open(SALIDA / "actualizacion.csv", "w", newline="", encoding="utf-8")
    f_s = open(SALIDA / "tamanos.csv", "w", newline="", encoding="utf-8")
    w_t, w_a, w_s = csv.writer(f_t), csv.writer(f_a), csv.writer(f_s)
    w_t.writerow(["escala", "variante", "consulta", "ejecucion", "ms", "usa_indice", "acceso"])
    w_a.writerow(["escala", "variante", "operacion", "ejecucion", "ms"])
    w_s.writerow(["escala", "variante", "indice", "tabla", "bytes", "seg_creacion_variante"])

    for esc in escalas:
        with conectar(ESCALAS[esc]) as conn:
            for var in variantes:
                t_cre = aplicar_variante(conn, var)
                for nombre, tabla, nbytes in tamanos_indices(conn):
                    w_s.writerow([esc, var, nombre, tabla, nbytes, round(t_cre, 3)])
                if var == "sin":
                    w_s.writerow([esc, var, "-", "-", 0, round(t_cre, 3)])
                print(f"\n=== {esc} · {NOMBRE_VARIANTE[var]} (índices creados en {t_cre:.2f} s)", flush=True)
                umbral_ms = args.umbral_lento * 1000
                with conn.cursor() as cur:
                    for cid, sql in consultas.items():
                        ms0, acc0, usa0 = explain(cur, sql)     # calentamiento
                        tiempos = []
                        if ms0 > umbral_ms:
                            # tan lenta que el caché no influye: se usa como ejecución única
                            tiempos.append(ms0)
                            w_t.writerow([esc, var, cid, 1, f"{ms0:.3f}", "si" if usa0 else "no", acc0])
                            acceso = acc0
                        else:
                            for r in range(1, args.repeticiones + 1):
                                ms, acceso, usa = explain(cur, sql)
                                tiempos.append(ms)
                                w_t.writerow([esc, var, cid, r, f"{ms:.3f}", "si" if usa else "no", acceso])
                                f_t.flush()
                                if ms > umbral_ms:
                                    break
                        nota = " (ejecución única)" if len(tiempos) == 1 else ""
                        print(f"  {cid:4} prom {statistics.mean(tiempos):12.3f} ms{nota}   {acceso}", flush=True)
                    if esc in esc_act:
                        for op, sql in ACTUALIZACIONES.items():
                            ts = []
                            for r in range(0, args.repeticiones_actualizacion + 1):
                                with conn.transaction(force_rollback=True):
                                    ms, _, _ = explain(cur, sql)
                                if r == 0 and ms > umbral_ms:   # muy lenta: el calentamiento cuenta como única
                                    ts.append(ms)
                                    w_a.writerow([esc, var, op, 1, f"{ms:.3f}"])
                                    break
                                if r > 0:                       # r = 0 es calentamiento
                                    ts.append(ms)
                                    w_a.writerow([esc, var, op, r, f"{ms:.3f}"])
                                    if ms > umbral_ms:
                                        break
                            print(f"  [act] {op:24} prom {statistics.mean(ts):12.3f} ms", flush=True)
                f_t.flush(); f_a.flush(); f_s.flush()
            aplicar_variante(conn, "sin")                       # deja la BD sin índices extra
    for f in (f_t, f_a, f_s):
        f.close()


# ----------------------------------------------------------------------------- resumen y gráficas
def cargar(nombre):
    ruta = SALIDA / nombre
    if not ruta.exists():
        return []
    with open(ruta, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def veredicto(r, base):
    """Clasifica una medición con índices frente a la de sin índices."""
    if base is None or r is base:
        return ""
    if base["usa"]:
        return "ERROR: el plan 'sin índices' usó un índice"
    if r["n"] == 1 or base["n"] == 1:
        return "Mejora real" if r["prom"] < base["prom"] else "Peor"
    if not r["usa"]:
        return "Empate: el plan no usa índices"
    ruido = 2 * max(r["desv"], base["desv"])
    dif = r["prom"] - base["prom"]
    if dif < -ruido:
        return "Mejora real"
    if dif > ruido:
        return "Peor"
    return "Empate: dentro del ruido"


def resumir():
    filas = cargar("tiempos.csv")
    grupos, accesos, usos = defaultdict(list), {}, {}
    for f in filas:
        k = (f["escala"], f["variante"], f["consulta"])
        grupos[k].append(float(f["ms"]))
        accesos[k] = f["acceso"]
        usos[k] = f.get("usa_indice", "") == "si" or (not f.get("usa_indice") and "idx_" in f["acceso"])
    resumen = {}
    for k, v in grupos.items():
        resumen[k] = dict(prom=statistics.mean(v), desv=statistics.stdev(v) if len(v) > 1 else 0.0,
                          min=min(v), max=max(v), n=len(v), acceso=accesos[k], usa=usos[k])
    with open(SALIDA / "resumen.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["escala", "variante", "consulta", "n", "promedio_ms", "desv_std_ms",
                    "min_ms", "max_ms", "vs_sin_%", "usa_indice", "veredicto", "acceso"])
        for k in sorted(resumen, key=orden_clave):
            r = resumen[k]
            base = resumen.get((k[0], "sin", k[2]))
            var = f"{100 * (r['prom'] - base['prom']) / base['prom']:+.1f}" if base and k[1] != "sin" else ""
            w.writerow([*k, r["n"], f"{r['prom']:.3f}", f"{r['desv']:.3f}", f"{r['min']:.3f}",
                        f"{r['max']:.3f}", var, "si" if r["usa"] else "no",
                        veredicto(r, base) if k[1] != "sin" else "", r["acceso"]])
    return resumen


def orden_clave(k):
    esc, var, c = k
    return (list(TITULO_CONSULTA).index(c), list(ESCALAS).index(esc), VARIANTES.index(var))


def graficar(resumen):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    escalas = [e for e in ESCALAS if any(k[0] == e for k in resumen)]
    variantes = [v for v in VARIANTES if any(k[1] == v for k in resumen)]
    consultas = [c for c in TITULO_CONSULTA if any(k[2] == c for k in resumen)]
    imagenes = {}

    # 1) por consulta: tiempo vs escala, una línea por variante
    for c in consultas:
        fig, ax = plt.subplots(figsize=(7, 4.2))
        for v in variantes:
            xs, ys, es = [], [], []
            for e in escalas:
                r = resumen.get((e, v, c))
                if r:
                    xs.append(e); ys.append(r["prom"]); es.append(r["desv"])
            ax.errorbar(xs, ys, yerr=es, marker="o", capsize=3, label=NOMBRE_VARIANTE[v], color=COLOR[v])
        ax.set_yscale("log")
        ax.set_xlabel("Cantidad de lecturas")
        ax.set_ylabel("Tiempo promedio (ms, escala log)")
        ax.set_title(TITULO_CONSULTA[c])
        ax.grid(True, which="both", alpha=0.3)
        ax.legend()
        fig.tight_layout()
        nombre = f"grafica_{c}.png"
        fig.savefig(SALIDA / nombre, dpi=130)
        plt.close(fig)
        imagenes[c] = nombre

    # 2) barras con la escala más grande disponible
    e_max = escalas[-1]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ancho = 0.8 / max(len(variantes), 1)
    for i, v in enumerate(variantes):
        ys = [resumen.get((e_max, v, c), {}).get("prom", 0) for c in consultas]
        es = [resumen.get((e_max, v, c), {}).get("desv", 0) for c in consultas]
        xs = [j + i * ancho for j in range(len(consultas))]
        ax.bar(xs, ys, ancho, yerr=es, capsize=2, label=NOMBRE_VARIANTE[v], color=COLOR[v])
    ax.set_xticks([j + ancho * (len(variantes) - 1) / 2 for j in range(len(consultas))])
    ax.set_xticklabels(consultas)
    ax.set_yscale("log")
    ax.set_ylabel("Tiempo promedio (ms, escala log)")
    ax.set_title(f"Comparación de tipos de índice con {e_max} lecturas")
    ax.grid(True, axis="y", which="both", alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(SALIDA / "grafica_barras_max.png", dpi=130)
    plt.close(fig)
    imagenes["barras"] = "grafica_barras_max.png"

    # 3) costo de actualización
    act = cargar("actualizacion.csv")
    if act:
        g = defaultdict(list)
        for f in act:
            g[(f["escala"], f["variante"], f["operacion"])].append(float(f["ms"]))
        e_act = max({k[0] for k in g}, key=list(ESCALAS).index)
        ops = list(ACTUALIZACIONES)
        vs = [v for v in VARIANTES if any(k[1] == v for k in g)]
        fig, ax = plt.subplots(figsize=(9, 4.5))
        ancho = 0.8 / len(vs)
        for i, v in enumerate(vs):
            ys = [statistics.mean(g.get((e_act, v, o), [0])) for o in ops]
            es = [statistics.stdev(g[(e_act, v, o)]) if len(g.get((e_act, v, o), [])) > 1 else 0 for o in ops]
            ax.bar([j + i * ancho for j in range(len(ops))], ys, ancho, yerr=es, capsize=2,
                   label=NOMBRE_VARIANTE[v], color=COLOR[v])
        ax.set_xticks([j + ancho * (len(vs) - 1) / 2 for j in range(len(ops))])
        ax.set_xticklabels(ops)
        ax.set_yscale("log")
        ax.set_ylabel("Tiempo promedio (ms, escala log)")
        ax.set_title(f"Costo de actualización por tipo de índice ({e_act} lecturas)")
        ax.grid(True, axis="y", which="both", alpha=0.3)
        ax.legend()
        fig.tight_layout()
        fig.savefig(SALIDA / "grafica_actualizacion.png", dpi=130)
        plt.close(fig)
        imagenes["act"] = "grafica_actualizacion.png"

    # 4) espacio ocupado por los índices
    tam = cargar("tamanos.csv")
    if tam:
        tot = defaultdict(int)
        for f in tam:
            tot[(f["escala"], f["variante"])] += int(f["bytes"])
        vs = [v for v in VARIANTES if any(k[1] == v for k in tot) and v != "sin"]
        fig, ax = plt.subplots(figsize=(7, 4.2))
        for v in vs:
            xs = [e for e in escalas if (e, v) in tot]
            ax.plot(xs, [max(tot[(e, v)], 1) / 1024 for e in xs], marker="o",
                    label=NOMBRE_VARIANTE[v], color=COLOR[v])
        ax.set_yscale("log")
        ax.set_xlabel("Cantidad de lecturas")
        ax.set_ylabel("Tamaño total de índices (KB, log)")
        ax.set_title("Espacio que ocupan los índices de cada variante")
        ax.grid(True, which="both", alpha=0.3)
        ax.legend()
        fig.tight_layout()
        fig.savefig(SALIDA / "grafica_tamanos.png", dpi=130)
        plt.close(fig)
        imagenes["tam"] = "grafica_tamanos.png"
    return imagenes


def reporte_html(resumen, imagenes):
    escalas = [e for e in ESCALAS if any(k[0] == e for k in resumen)]
    variantes = [v for v in VARIANTES if any(k[1] == v for k in resumen)]
    n = next(iter(resumen.values()))["n"] if resumen else 0
    p = []
    p.append(f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Benchmark de índices</title><style>
:root{{--bg:#fff;--fg:#1d1d1f;--mut:#666;--bd:#ddd;--hd:#f4f4f6;--ok:#1a7f37;--bad:#c62828}}
@media (prefers-color-scheme:dark){{:root{{--bg:#16171a;--fg:#e8e8ea;--mut:#9a9aa0;--bd:#33343a;--hd:#202126;--ok:#5fd27c;--bad:#ff7b72}}}}
body{{font-family:system-ui,sans-serif;background:var(--bg);color:var(--fg);max-width:1100px;margin:0 auto;padding:16px;line-height:1.45}}
table{{border-collapse:collapse;width:100%;font-size:13px;margin:8px 0 24px}}
th,td{{border:1px solid var(--bd);padding:4px 6px;text-align:right}} th{{background:var(--hd)}}
td.t{{text-align:left;font-family:monospace;font-size:11px;color:var(--mut)}}
.ok{{color:var(--ok);font-weight:600}} .bad{{color:var(--bad);font-weight:600}}
img{{max-width:100%;background:#fff;border-radius:6px}} .wrap{{overflow-x:auto}}
small{{color:var(--mut)}}</style></head><body>
<h1>Benchmark de índices: sin vs con (elegidos por teoría)</h1>
<p><small>{n} ejecuciones por medición (más 1 de calentamiento) · tiempo = <code>Execution Time</code> de
<code>EXPLAIN (ANALYZE)</code> · generado {time.strftime('%Y-%m-%d %H:%M')}</small></p>
<h2>Resumen con la escala mayor</h2><img src="{imagenes.get('barras', '')}" alt="barras">""")
    for c in TITULO_CONSULTA:
        if c not in imagenes:
            continue
        p.append(f"<h2>{html.escape(TITULO_CONSULTA[c])}</h2><img src='{imagenes[c]}' alt='{c}'>")
        p.append("<div class='wrap'><table><tr><th>Escala</th><th>Variante</th><th>Promedio (ms)</th>"
                 "<th>Desv. est.</th><th>vs sin</th><th>¿Usó índice?</th><th>Veredicto</th>"
                 "<th>Acceso usado en el plan</th></tr>")
        for e in escalas:
            base = resumen.get((e, "sin", c))
            for v in variantes:
                r = resumen.get((e, v, c))
                if not r:
                    continue
                pct, ver = "", ""
                usa = "sí" if r["usa"] else "no"
                if v != "sin":
                    ver = veredicto(r, base)
                    clase = "ok" if ver == "Mejora real" else "bad" if ver == "Peor" else ""
                    ver = f"<span class='{clase}'>{ver}</span>"
                if base and v != "sin":
                    d = 100 * (r["prom"] - base["prom"]) / base["prom"]
                    pct = f"<span class='{'ok' if d < -5 else 'bad' if d > 5 else ''}'>{d:+.1f}%</span>"
                p.append(f"<tr><td>{e}</td><td style='text-align:left'>{NOMBRE_VARIANTE[v]}</td>"
                         f"<td>{r['prom']:.3f}</td><td>{r['desv']:.3f} <small>(n={r['n']})</small></td><td>{pct}</td>"
                         f"<td>{usa}</td><td style='text-align:left'>{ver}</td>"
                         f"<td class='t'>{html.escape(r['acceso'])}</td></tr>")
        p.append("</table></div>")
    if "act" in imagenes:
        p.append("<h2>Costo de actualización (INSERT / UPDATE / DELETE)</h2>"
                 "<p><small>Cada operación se ejecuta y se deshace con ROLLBACK.</small></p>"
                 f"<img src='{imagenes['act']}' alt='actualizacion'>")
        g = defaultdict(list)
        for f in cargar("actualizacion.csv"):
            g[(f["escala"], f["variante"], f["operacion"])].append(float(f["ms"]))
        p.append("<div class='wrap'><table><tr><th>Escala</th><th>Operación</th>" +
                 "".join(f"<th>{NOMBRE_VARIANTE[v]} (ms)</th>" for v in VARIANTES
                         if any(k[1] == v for k in g)) + "</tr>")
        for e in ESCALAS:
            for op in ACTUALIZACIONES:
                if not any((e, v, op) in g for v in VARIANTES):
                    continue
                celdas = "".join(f"<td>{statistics.mean(g[(e, v, op)]):.2f}</td>" if (e, v, op) in g
                                 else "<td>-</td>" for v in VARIANTES if any(k[1] == v for k in g))
                p.append(f"<tr><td>{e}</td><td style='text-align:left'>{op}</td>{celdas}</tr>")
        p.append("</table></div>")
    if "tam" in imagenes:
        p.append(f"<h2>Espacio de los índices</h2><img src='{imagenes['tam']}' alt='tamanos'>")
        p.append("<div class='wrap'><table><tr><th>Escala</th><th>Variante</th><th>Índice</th>"
                 "<th>Tabla</th><th>Tamaño (KB)</th></tr>")
        for f in cargar("tamanos.csv"):
            if f["indice"] != "-":
                p.append(f"<tr><td>{f['escala']}</td><td style='text-align:left'>{NOMBRE_VARIANTE[f['variante']]}</td>"
                         f"<td class='t'>{f['indice']}</td><td class='t'>{f['tabla']}</td>"
                         f"<td>{int(f['bytes']) / 1024:.0f}</td></tr>")
        p.append("</table></div>")
    p.append("</body></html>")
    (SALIDA / "reporte.html").write_text("\n".join(p), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-n", "--repeticiones", type=int, default=5, help="ejecuciones por consulta (default 5)")
    ap.add_argument("--umbral-lento", type=float, default=120,
                    help="si una ejecución pasa de estos segundos, no se repite (default 120)")
    ap.add_argument("-e", "--escalas", default="1k,10k,100k,1m")
    ap.add_argument("-v", "--variantes", default="sin,teoria")
    ap.add_argument("--escalas-actualizacion", default="1m",
                    help="escalas donde se mide INSERT/UPDATE/DELETE (default 1m; '' para omitir)")
    ap.add_argument("--repeticiones-actualizacion", type=int, default=5)
    ap.add_argument("--solo-reporte", action="store_true", help="no mide; rehace resumen/gráficas/HTML")
    args = ap.parse_args()
    if not args.solo_reporte:
        t0 = time.time()
        medir(args)
        print(f"\nMedición terminada en {time.time() - t0:.0f} s")
    resumen = resumir()
    imagenes = graficar(resumen)
    reporte_html(resumen, imagenes)
    print(f"Listo: {SALIDA / 'reporte.html'}")


if __name__ == "__main__":
    main()
