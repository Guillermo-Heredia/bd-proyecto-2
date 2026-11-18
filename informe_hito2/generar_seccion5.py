#!/usr/bin/env python3
"""Genera seccion5.tex a partir de resultados/benchmark/{tiempos,resumen,actualizacion,tamanos}.csv.

Uso:
    python3 generar_seccion5.py
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
RES = BASE / "resultados" / "benchmark"

ESCALAS = ["1k", "10k", "100k", "1m"]
ESCALA_TXT = {"1k": "1k", "10k": "10k", "100k": "100k", "1m": "1M"}
VARIANTES = ["sin", "teoria"]
VAR_TXT = {"sin": "Sin índices", "teoria": "Con índices"}


def leer(nombre):
    with open(RES / nombre, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


tiempos_rows = leer("tiempos.csv")
resumen_rows = leer("resumen.csv")
act_rows = leer("actualizacion.csv")
tam_rows = leer("tamanos.csv")

tiempos = {}
for r in tiempos_rows:
    tiempos[(r["escala"], r["variante"], r["consulta"].lstrip("C"), int(r["ejecucion"]))] = float(r["ms"])

resumen = {}
for r in resumen_rows:
    resumen[(r["escala"], r["variante"], r["consulta"].lstrip("C"))] = {
        "n": int(r["n"]),
        "prom": float(r["promedio_ms"]),
        "std": float(r["desv_std_ms"]),
        "min": float(r["min_ms"]),
        "max": float(r["max_ms"]),
        "vs": r["vs_sin_%"],
        "usa": r["usa_indice"],
        "ver": r["veredicto"],
        "acc": r["acceso"],
    }


def avg(q, esc, var="sin"):
    return resumen[(esc, var, q)]["prom"]


def fmt(v: float | None) -> str:
    if v is None:
        return r"\textit{--}"
    if v < 10:
        s = f"{v:.3f}"
    elif v < 1000:
        s = f"{v:.2f}"
    else:
        s = f"{v:,.1f}"
    return s.replace(",", r"\,")


def variacion(q):
    s = avg(q, "1m", "sin")
    c = avg(q, "1m", "teoria")
    return (c - s) / s * 100.0


def factor(q):
    return avg(q, "1m", "sin") / avg(q, "1m", "teoria")


def fmt_factor(f: float) -> str:
    if f < 10:
        return f"{f:.1f}"
    return f"{f:,.0f}".replace(",", r"\,")


def sub(t: str, **kw) -> str:
    for k, v in kw.items():
        t = t.replace("@" + k + "@", str(v))
    return t


def tabla_tiempos(q: str, var: str) -> str:
    filas = []
    faltan = False
    for e in range(1, 6):
        celdas = []
        for esc in ESCALAS:
            v = tiempos.get((esc, var, q, e))
            if v is None:
                faltan = True
            celdas.append(fmt(v))
        filas.append(f"{e} & " + " & ".join(celdas) + r" \\ \hline")

    prom = " & ".join(fmt(avg(q, esc, var)) for esc in ESCALAS)
    std = " & ".join(fmt(resumen[(esc, var, q)]["std"]) for esc in ESCALAS)
    nota = ""
    if faltan:
        nota = (r"\par\footnotesize En 1M la corrida sin índices superó el umbral de "
                r"120\,s, por lo que se midió una sola vez ($n=1$); las celdas "
                r"restantes no aplican.")
    return (
        "\\begin{table}[H]\n\\centering\n\\small\n"
        f"\\caption{{Tiempos de ejecución --- Consulta {q} --- {VAR_TXT[var]}}}\n"
        "\\begin{tabular}{|c|r|r|r|r|}\n\\hline\n"
        "\\textbf{Ejecución} & \\textbf{1k (ms)} & \\textbf{10k (ms)} & "
        "\\textbf{100k (ms)} & \\textbf{1M (ms)} \\\\ \\hline\n"
        + "\n".join(filas) + "\n"
        f"\\textbf{{Promedio}} & {prom} \\\\ \\hline\n"
        f"\\textbf{{Desviación estándar}} & {std} \\\\ \\hline\n"
        "\\end{tabular}\n" + nota + "\n\\end{table}\n"
    )


def tabla_comparacion() -> str:
    filas = []
    for q in "12345":
        s = avg(q, "1m", "sin")
        c = avg(q, "1m", "teoria")
        v = variacion(q)
        f = factor(q)
        if v < -99.9:
            vtxt = r"$\approx-100$\,\%"
        else:
            vtxt = f"${v:+.1f}$\\,\\%"
        filas.append(f"{q} & {fmt(s)} & {fmt(c)} & {vtxt} & $\\approx{fmt_factor(f)}\\times$ \\\\ \\hline")
    return (
        "\\begin{table}[H]\n\\centering\n\\small\n"
        "\\caption{Tiempo promedio con 1\\,000\\,000 de lecturas y variación al usar índices}\n"
        "\\begin{tabular}{|c|r|r|r|r|}\n\\hline\n"
        "\\textbf{Consulta} & \\textbf{Sin índices (ms)} & \\textbf{Con índices (ms)} & "
        "\\textbf{Variación} & \\textbf{Factor} \\\\ \\hline\n"
        + "\n".join(filas) + "\n\\end{tabular}\n\\end{table}\n"
    )


def tabla_actualizacion() -> str:
    g = defaultdict(list)
    for r in act_rows:
        g[(r["operacion"], r["variante"])].append(float(r["ms"]))
    ops = ["INSERT 1000 lecturas", "UPDATE rms 1 día", "UPDATE estado alertas", "DELETE 1 día"]
    filas = []
    for op in ops:
        s = g[(op, "sin")]
        c = g[(op, "teoria")]
        ms_s = sum(s) / len(s)
        ms_c = sum(c) / len(c)
        nota = ""
        if len(s) == 1:
            nota = r" $^{\dagger}$"
        filas.append(
            f"{op}{nota} & {fmt(ms_s)} & {fmt(ms_c)} & "
            f"${(ms_c - ms_s) / ms_s * 100:+.1f}$\\,\\% \\\\ \\hline"
        )
    return (
        "\\begin{table}[H]\n\\centering\n\\small\n"
        "\\caption{Costo de actualización con 1M (ms; cada operación termina en ROLLBACK)}\n"
        "\\begin{tabular}{|l|r|r|r|}\n\\hline\n"
        "\\textbf{Operación} & \\textbf{Sin índices} & \\textbf{Con índices} & "
        "\\textbf{Variación} \\\\ \\hline\n"
        + "\n".join(filas) + "\n\\end{tabular}\n"
        "\\par\\footnotesize $^{\\dagger}$ Medido una sola vez ($n=1$): el anti-join "
        "sin índice tardó cerca de 16 minutos.\n\\end{table}\n"
    )


_g = defaultdict(list)
for _r in act_rows:
    _g[(_r["operacion"], _r["variante"])].append(float(_r["ms"]))
_upd_sin = sum(_g[("UPDATE rms 1 día", "sin")]) / len(_g[("UPDATE rms 1 día", "sin")])
_upd_con = sum(_g[("UPDATE rms 1 día", "teoria")]) / len(_g[("UPDATE rms 1 día", "teoria")])
upd_pct = (_upd_con - _upd_sin) / _upd_sin * 100.0

total_idx = sum(int(r["bytes"]) for r in tam_rows if r["variante"] == "teoria" and r["escala"] == "1m")
total_idx_mb = total_idx / (1024 ** 2)


def limpiar_sql(texto: str) -> str:
    """Quita comentarios -- (de linea completa y al final de linea) y lineas vacias."""
    salida = []
    for linea in texto.splitlines():
        dentro_comilla = True
        corte = len(linea)
        i = 0
        while i < len(linea) - 1:
            c = linea[i]
            if c == "'":
                dentro_comilla = not dentro_comilla
            elif dentro_comilla and c == "-" and linea[i + 1] == "-":
                corte = i
                break
            i += 1
        linea = linea[:corte].rstrip()
        if linea.strip():
            salida.append(linea)
    return "\n".join(salida)


def resultados_q(q: str, texto: str) -> str:
    return f"\\subsubsection{{Consulta {q}}}\n\\resultadoconsulta{{{q}}}\n{texto}\n"


def main() -> None:
    limpio = HERE / "consultas_limpias"
    limpio.mkdir(exist_ok=True)
    for q in "12345":
        origen = HERE / "consultas" / f"c{q}.sql"
        (limpio / f"c{q}.sql").write_text(
            limpiar_sql(origen.read_text(encoding="utf-8")) + "\n", encoding="utf-8"
        )

    p = []

    p.append(r"""
\section{Optimización y Experimentación}

\subsection{Consultas SQL para el experimento}

\subsubsection{Descripción de las 5 consultas intermedias seleccionadas (no triviales)}

Las cinco consultas trabajan sobre \texttt{LecturaVibracion}, la tabla que crece
con la escala, y responden preguntas de mantenimiento predictivo.

\textbf{Consulta 1:} ¿Qué lecturas anómalas (RMS $\ge 4$) superan en 1.5 veces o
más el promedio de las 24 horas previas de su mismo sensor?

\textit{Justificación:} detecta picos que no son ruido aislado sino un salto
frente al historial reciente del sensor, y los ubica en su turbina y parque.

\textbf{Consulta 2:} En las últimas 48 horas, ¿qué sensores vibran más que el
promedio de su parque? (top 5 por parque)

\textit{Justificación:} compara cada sensor contra sus pares del mismo parque
para priorizar la revisión de los que se salen del comportamiento conjunto.

\textbf{Consulta 3:} ¿Qué turbinas tienen más rachas de tres o más lecturas
consecutivas con RMS $> 2.5$? (top 10)

\textit{Justificación:} una lectura alta aislada puede ser ruido; una racha
sostenida indica deterioro real del componente.

\textbf{Consulta 4:} ¿Cómo venía la vibración en las cinco lecturas previas a
cada alerta grave? (por parque y componente)

\textit{Justificación:} mide la tendencia (pendiente) antes de la alerta para
distinguir fallas progresivas de eventos súbitos.

\textbf{Consulta 5:} ¿Qué turbinas pasan más rápido de ``normal'' a ``alerta''?
(top 10, incluyendo alertas sin orden de trabajo)

\textit{Justificación:} cuantifica la velocidad de degradación y detecta
alertas que todavía no tienen una orden asociada.

\subsubsection{Implementación de consultas en SQL}

\textbf{Consulta 1: Lecturas anómalas frente a su historial de 24 h}
\lstinputlisting[language=SQL]{consultas_limpias/c1.sql}

\textbf{Consulta 2: Sensores por encima del promedio de su parque (48 h)}
\lstinputlisting[language=SQL]{consultas_limpias/c2.sql}

\textbf{Consulta 3: Rachas de vibración alta por turbina}
\lstinputlisting[language=SQL]{consultas_limpias/c3.sql}

\textbf{Consulta 4: Tendencia previa a las alertas graves}
\lstinputlisting[language=SQL]{consultas_limpias/c4.sql}

\textbf{Consulta 5: Velocidad de degradación de cada turbina}
\lstinputlisting[language=SQL]{consultas_limpias/c5.sql}

\subsection{Metodología del experimento}

Para que la comparación sea válida, la variante \emph{sin índices} no se limita
a borrar los índices creados por el proyecto: también se desactiva el uso de los
índices automáticos de llave primaria y \texttt{UNIQUE} en la sesión, porque
PostgreSQL los aprovechaba y la prueba dejaba de ser ``sin índices''. El
procedimiento fue:

\begin{enumerate}
    \item \textbf{Preparación:} se parte de las bases \texttt{bd\_1k},
    \texttt{bd\_10k}, \texttt{bd\_100k} y \texttt{bd\_1m}, generadas con
    \texttt{crear\_todo.sh}, y se ejecuta \texttt{ANALYZE} para actualizar las
    estadísticas del planificador.

    \item \textbf{Sin índices:} se eliminan todos los índices \texttt{idx\_*} y,
    en la misma sesión, se ejecuta
    \begin{lstlisting}[language=SQL]
SET enable_indexscan = off;
SET enable_indexonlyscan = off;
SET enable_bitmapscan = off;
    \end{lstlisting}
    Así el planificador solo puede usar \texttt{Seq Scan}. El programa verifica
    en cada plan que la variante ``sin'' no use ningún índice.

    \item \textbf{Calentamiento:} antes de medir se ejecuta la consulta una vez
    para llevar los datos a la caché compartida.

    \item \textbf{Repeticiones:} se ejecutan 5 veces por consulta, escala y
    variante. Cada valor de las tablas es una ejecución; el promedio y la
    desviación estándar se calculan sobre esas 5 corridas. Si una corrida supera
    los 120\,s se mide una sola vez ($n=1$) para no extender el experimento; es
    el caso de C1 y C5 con 1M sin índices.

    \item \textbf{Con índices:} se ejecuta \texttt{indices/crear\_indices.sql}
    (índices elegidos por teoría) y se repite la misma medición en una sesión
    limpia.

    \item \textbf{Medición:} todo se hace con \texttt{benchmark.py} en una sola
    sesión de \texttt{psycopg} por variante, registrando el tiempo de ejecución
    y el tipo de acceso del plan. Los planes que se muestran en el informe se
    obtienen con \texttt{EXPLAIN (ANALYZE, BUFFERS)} en pgAdmin.
\end{enumerate}

\subsection{Optimización de consultas}

La regla usada para elegir cada índice es la siguiente: la igualdad
($=$, \texttt{IN}, join por llave) va con \textbf{Hash}; el rango, la
desigualdad y el orden ($<$, $>$, $\ge$, \texttt{ORDER BY},
\texttt{PARTITION BY \dots ORDER BY}) van con \textbf{B+ tree}; si hay igualdad
y rango en varias columnas se usa B+ tree, porque Hash solo indexa una columna y
solo sirve para igualdad. En PostgreSQL, \texttt{CREATE INDEX} sin
\texttt{USING} crea un B-tree, que es un B+ tree.

\subsubsection{Planes de índices para Consulta 1}
\begin{lstlisting}[language=SQL]
CREATE INDEX idx_btree_lectura_sensor_fecha
  ON LecturaVibracion (id_sensor, fecha_hora) INCLUDE (valor_rms);

CREATE INDEX idx_btree_lectura_rms
  ON LecturaVibracion (valor_rms);
\end{lstlisting}
La subconsulta correlacionada busca \texttt{(id\_sensor, fecha\_hora)} en un
rango de 24 h (B+ tree) y el filtro \texttt{valor\_rms >= 4} usa el B+ tree
sobre \texttt{valor\_rms}.

\subsubsection{Planes de índices para Consulta 2}
\begin{lstlisting}[language=SQL]
CREATE INDEX idx_btree_lectura_fecha
  ON LecturaVibracion (fecha_hora) INCLUDE (id_sensor, valor_rms, valor_pico);
\end{lstlisting}
El predicado es un rango de 48 h sobre \texttt{fecha\_hora}; el \texttt{INCLUDE}
permite un \texttt{Index Only Scan} sin volver a la tabla.

\subsubsection{Planes de índices para Consulta 3}
\begin{lstlisting}[language=SQL]
CREATE INDEX idx_btree_lectura_sensor_fecha
  ON LecturaVibracion (id_sensor, fecha_hora) INCLUDE (valor_rms);
\end{lstlisting}
Las ventanas necesitan las lecturas ordenadas por sensor y fecha; el B+ tree las
entrega en ese orden (evita el \texttt{Sort} de toda la tabla).

\subsubsection{Planes de índices para Consulta 4}
\begin{lstlisting}[language=SQL]
CREATE INDEX idx_btree_lectura_sensor_fecha
  ON LecturaVibracion (id_sensor, fecha_hora) INCLUDE (valor_rms);

CREATE INDEX idx_hash_alerta_nivel
  ON AlertaMantenimiento USING hash (nivel);
\end{lstlisting}
El \texttt{JOIN LATERAL} busca las 5 lecturas anteriores de un sensor
(igualdad + orden) y el filtro \texttt{nivel IN ('Alta','Critica')} es igualdad
(Hash).

\subsubsection{Planes de índices para Consulta 5}
\begin{lstlisting}[language=SQL]
CREATE INDEX idx_btree_lectura_sensor_fecha
  ON LecturaVibracion (id_sensor, fecha_hora) INCLUDE (valor_rms);

CREATE INDEX idx_hash_alertaorden_alerta
  ON AlertaOrden USING hash (id_alerta);
\end{lstlisting}
Cada alerta busca la última lectura normal anterior a una fecha (igualdad +
rango) y el \texttt{NOT EXISTS} resuelve \texttt{ao.id\_alerta = a.id\_alerta}
por igualdad.

\paragraph{Índices de las llaves foráneas.} Los joins por llave foránea se apoyan en índices Hash:
\texttt{SensorVibracion(id\_componente)},
\texttt{ComponenteTurbina(id\_turbina)} y \texttt{Turbina(id\_parque)}. El
conjunto completo de índices está en el repositorio del proyecto.

\subsection{Plataforma de Pruebas}

\begin{table}[H]
\centering
\small
\caption{Hardware y software utilizado}
\begin{tabular}{|l|l|}
\hline
\textbf{Componente} & \textbf{Descripción} \\ \hline
Memoria física instalada (RAM) & 12 GB \\ \hline
Procesador & Intel Core i5-1035G4 @ 1.10 GHz (4 núcleos / 8 hilos) \\ \hline
Almacenamiento & SSD NVMe SK Hynix 512 GB \\ \hline
Sistema Operativo & Fedora Linux 44 Workstation (kernel 7.3.3) \\ \hline
pgAdmin & pgAdmin 4 v9.19 \\ \hline
PostgreSQL & PostgreSQL 16.15 \\ \hline
\end{tabular}
\end{table}

\subsection{Medición de tiempos}

Se registra el \textit{Execution Time} de \texttt{EXPLAIN ANALYZE} en
milisegundos. Cada tabla muestra las cinco ejecuciones por escala, su promedio
y su desviación estándar.

\subsubsection{Sin índices}
""")

    for q in "12345":
        p.append(tabla_tiempos(q, "sin"))

    p.append("\n\\subsubsection{Con índices}\n")
    for q in "12345":
        p.append(tabla_tiempos(q, "teoria"))

    p.append(r"""
\subsection{Resultados}

Para cada consulta se muestran el árbol del plan (\textit{Query Plan Tree}) y el
plan de ejecución en las cuatro escalas, sin y con índices, seguidos de su
explicación.
""")

    p.append(resultados_q("1", r"""
\textbf{Sin índices:} por cada lectura anómala hay que promediar las 24 horas
previas de su sensor, y cada búsqueda recorre la tabla completa. El costo crece
de forma cuadrática: @c1s1@ ms (1k), @c1s2@ ms (10k), @c1s3@ ms (100k) y
@c1s4@ ms (1M, $n=1$).

\textbf{Con índices:} el B+ tree \texttt{(id\_sensor, fecha\_hora)} resuelve
cada ventana de 24 h en un salto y el índice sobre \texttt{valor\_rms} filtra
las lecturas anómalas. El tiempo baja a @c1c1@, @c1c2@, @c1c3@ y @c1c4@ ms; con
1M es aproximadamente @f1@ veces más rápida. La mejora es real en todas las
escalas.
""".replace("@c1s1@", fmt(avg("1", "1k", "sin")))
   .replace("@c1s2@", fmt(avg("1", "10k", "sin")))
   .replace("@c1s3@", fmt(avg("1", "100k", "sin")))
   .replace("@c1s4@", fmt(avg("1", "1m", "sin")))
   .replace("@c1c1@", fmt(avg("1", "1k", "teoria")))
   .replace("@c1c2@", fmt(avg("1", "10k", "teoria")))
   .replace("@c1c3@", fmt(avg("1", "100k", "teoria")))
   .replace("@c1c4@", fmt(avg("1", "1m", "teoria")))
   .replace("@f1@", f"{factor('1'):,.0f}".replace(",", r"\,"))))

    p.append(resultados_q("2", r"""
\textbf{Sin índices:} el rango de 48 h se resuelve con un recorrido secuencial
de \texttt{LecturaVibracion}: @c2s1@ ms (1k), @c2s2@ ms (10k), @c2s3@ ms
(100k) y @c2s4@ ms (1M).

\textbf{Con índices:} el B+ tree sobre \texttt{fecha\_hora} con
\texttt{INCLUDE} permite un \texttt{Index Only Scan} y reduce el tiempo a
@c2c1@, @c2c2@, @c2c3@ y @c2c4@ ms. Con 1k y 10k la mejora está dentro del
ruido (@v2a@ y @v2b@), porque 48 h abarcan casi toda la tabla; con 100k y 1M el
rango ya es selectivo y la ganancia crece hasta @v2d@ en 1M.
""".replace("@c2s1@", fmt(avg("2", "1k", "sin")))
   .replace("@c2s2@", fmt(avg("2", "10k", "sin")))
   .replace("@c2s3@", fmt(avg("2", "100k", "sin")))
   .replace("@c2s4@", fmt(avg("2", "1m", "sin")))
   .replace("@c2c1@", fmt(avg("2", "1k", "teoria")))
   .replace("@c2c2@", fmt(avg("2", "10k", "teoria")))
   .replace("@c2c3@", fmt(avg("2", "100k", "teoria")))
   .replace("@c2c4@", fmt(avg("2", "1m", "teoria")))
   .replace("@v2a@", resumen[("1k", "teoria", "2")]["vs"] + r"\,\%")
   .replace("@v2b@", resumen[("10k", "teoria", "2")]["vs"] + r"\,\%")
   .replace("@v2d@", resumen[("1m", "teoria", "2")]["vs"] + r"\,\%")))

    p.append(resultados_q("3", r"""
\textbf{Sin índices:} la consulta no tiene filtro: procesa todas las lecturas y
calcula dos funciones de ventana, por lo que el tiempo crece con el volumen:
@c3s1@ ms (1k), @c3s2@ ms (10k), @c3s3@ ms (100k) y @c3s4@ ms (1M).

\textbf{Con índices:} el B+ tree \texttt{(id\_sensor, fecha\_hora)} entrega las
filas ya ordenadas y evita el \texttt{Sort}, pero hay que procesar todas las
filas igual. El tiempo queda en @c3c1@, @c3c2@, @c3c3@ y @c3c4@ ms, con una
mejora de @v3@ en 1M. En 1k el planificador prefiere \texttt{Seq Scan}
(\texttt{usa\_indice = no}), así que la diferencia es ruido. Es el ejemplo de
una consulta donde el índice ayuda poco porque necesita todas las filas.
""".replace("@c3s1@", fmt(avg("3", "1k", "sin")))
   .replace("@c3s2@", fmt(avg("3", "10k", "sin")))
   .replace("@c3s3@", fmt(avg("3", "100k", "sin")))
   .replace("@c3s4@", fmt(avg("3", "1m", "sin")))
   .replace("@c3c1@", fmt(avg("3", "1k", "teoria")))
   .replace("@c3c2@", fmt(avg("3", "10k", "teoria")))
   .replace("@c3c3@", fmt(avg("3", "100k", "teoria")))
   .replace("@c3c4@", fmt(avg("3", "1m", "teoria")))
   .replace("@v3@", resumen[("1m", "teoria", "3")]["vs"] + r"\,\%")))

    p.append(resultados_q("4", r"""
\textbf{Sin índices:} por cada alerta grave, el \texttt{JOIN LATERAL} busca las
cinco lecturas anteriores de su sensor; sin índice cada búsqueda recorre toda
la tabla. El tiempo sube a @c4s1@ ms (1k), @c4s2@ ms (10k), @c4s3@ ms (100k) y
@c4s4@ ms (1M).

\textbf{Con índices:} el B+ tree sobre \texttt{(id\_sensor, fecha\_hora)}
permite leer solo las cinco entradas anteriores a cada alerta; el Hash sobre
\texttt{nivel} filtra las alertas graves. El tiempo baja a @c4c1@, @c4c2@,
@c4c3@ y @c4c4@ ms, es decir, alrededor de @f4@ veces menos con 1M.
""".replace("@c4s1@", fmt(avg("4", "1k", "sin")))
   .replace("@c4s2@", fmt(avg("4", "10k", "sin")))
   .replace("@c4s3@", fmt(avg("4", "100k", "sin")))
   .replace("@c4s4@", fmt(avg("4", "1m", "sin")))
   .replace("@c4c1@", fmt(avg("4", "1k", "teoria")))
   .replace("@c4c2@", fmt(avg("4", "10k", "teoria")))
   .replace("@c4c3@", fmt(avg("4", "100k", "teoria")))
   .replace("@c4c4@", fmt(avg("4", "1m", "teoria")))
   .replace("@f4@", f"{factor('4'):,.0f}".replace(",", r"\,"))))

    p.append(resultados_q("5", r"""
\textbf{Sin índices:} por cada alerta hay que buscar la última lectura normal
anterior a una fecha y comprobar con \texttt{NOT EXISTS} si tiene orden; cada
búsqueda recorre \texttt{LecturaVibracion} completa y el costo crece de forma
cuadrática: @c5s1@ ms (1k), @c5s2@ ms (10k), @c5s3@ ms (100k) y @c5s4@ ms
(1M, $n=1$).

\textbf{Con índices:} el B+ tree \texttt{(id\_sensor, fecha\_hora)} recorre el
árbol hacia atrás desde la fecha de la alerta y el Hash sobre
\texttt{AlertaOrden(id\_alerta)} resuelve el anti-join. El tiempo baja a
@c5c1@, @c5c2@, @c5c3@ y @c5c4@ ms; con 1M es aproximadamente @f5@ veces más
rápida, la mayor ganancia del experimento.
""".replace("@c5s1@", fmt(avg("5", "1k", "sin")))
   .replace("@c5s2@", fmt(avg("5", "10k", "sin")))
   .replace("@c5s3@", fmt(avg("5", "100k", "sin")))
   .replace("@c5s4@", fmt(avg("5", "1m", "sin")))
   .replace("@c5c1@", fmt(avg("5", "1k", "teoria")))
   .replace("@c5c2@", fmt(avg("5", "10k", "teoria")))
   .replace("@c5c3@", fmt(avg("5", "100k", "teoria")))
   .replace("@c5c4@", fmt(avg("5", "1m", "teoria")))
   .replace("@f5@", f"{factor('5'):,.0f}".replace(",", r"\,"))))

    p.append("\n\\subsection{Análisis y Discusión}\n\n")
    p.append(tabla_comparacion())
    p.append(r"""
Las consultas 1, 4 y 5 hacen una búsqueda por cada alerta o lectura anómala.
Sin índices, cada búsqueda recorre la tabla completa y el costo crece como
$N^2$: al pasar de 100k a 1M el tiempo se multiplica por casi 100. Con el B+
tree el acceso es un salto directo y el tiempo crece de forma aproximadamente
lineal, de ahí factores de mejora de miles de veces con 1M.

La consulta 2 filtra por un rango de 48 h. Con pocos datos ese rango abarca casi
toda la tabla y el índice no ayuda; con 1M representa cerca del 4\,\% de las
filas y la ganancia llega a dos tercios. La consulta 3 recorre todas las filas
para calcular las ventanas: el índice solo evita el ordenamiento, por eso la
mejora es pequeña (alrededor de 12\,\% con 1M). Es el caso típico de una
consulta que necesita todas las filas y donde un índice aporta poco.

Con 1k casi todas las consultas están por debajo de unos pocos milisegundos y
las diferencias son ruido. Por eso el análisis se concentra en 100k y 1M.

\paragraph{Costo en escrituras.}
Los índices también cuestan: cada \texttt{INSERT}, \texttt{UPDATE} o
\texttt{DELETE} debe mantener los B+ tree y los Hash. La tabla siguiente lo
cuantifica con 1M de lecturas.
""")
    p.append(tabla_actualizacion())
    p.append(sub(r"""
El \texttt{INSERT} de 1000 lecturas es más barato con índices porque la
verificación de las llaves foráneas y el trigger encuentran sus filas por Hash
en lugar de recorrer las tablas. El \texttt{UPDATE} de un día de
\texttt{valor\_rms} es más caro con índices (@upd@ de variación), porque hay que
actualizar los B+ tree que incluyen esa columna. Las alertas, al ser una tabla
pequeña, casi no cambian. La diferencia más grande está en el \texttt{DELETE}
con anti-join: sin índice tarda cerca de 16 minutos y con índice unos segundos.

\paragraph{Espacio.}
Con 1M de lecturas, los índices elegidos por teoría ocupan @mb@\,MB, mientras
que la tabla \texttt{LecturaVibracion} ronda los 65\,MB. Es el precio de las
ganancias anteriores: el espacio de los índices puede superar al de la tabla que
los usa.

\paragraph{Escalamiento por encima del millón de registros.}
Las consultas que recorren toda la tabla (como la 3) crecen en proporción al
número de filas; las búsquedas por índice crecen mucho más despacio. Con 10
millones de lecturas, la C5 sin índices pasaría de 9.6 minutos a varias horas,
mientras que con índices seguiría en el orden de segundos. Para volúmenes
mayores conviene particionar \texttt{LecturaVibracion} por fecha, mantener
tablas de resumen y, si el volumen crece mucho más, usar réplicas de lectura.
La arquitectura cliente-servidor con un solo PostgreSQL es suficiente para
algunos millones de registros, pero no para cientos de millones sin
particionamiento.
""".replace("@upd@", f"{upd_pct:+.1f}" + r"\,\%")
   .replace("@mb@", f"{total_idx_mb:.1f}")))

    (HERE / "seccion5.tex").write_text("\n".join(p), encoding="utf-8")
    print(f"Escrito {HERE / 'seccion5.tex'}")


if __name__ == "__main__":
    main()
