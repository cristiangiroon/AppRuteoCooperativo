"""Genera las figuras del artículo a partir de datos/ y resultados/ (python python/figuras.py)."""
import os
import re
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vrpd  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(RAIZ, "figuras")
RES = os.path.join(RAIZ, "resultados")
AZUL, NARANJA, AQUA, GRIS, TINTA, TINTA2 = "#2a78d6", "#eb6834", "#1baf7a", "#b9b8b2", "#0b0b0b", "#52514e"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": GRIS,
                     "axes.labelcolor": TINTA2, "xtick.color": TINTA2, "ytick.color": TINTA2,
                     "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 200})

nodos, P = vrpd.cargar(os.path.join(RAIZ, "datos"))
lat, lon = nodos["lat"], nodos["lon"]
CORTO = {0: "Bodega", 1: "Julumito", 2: "Puelenje", 3: "Cajete", 4: "H. Timbío", 5: "Poblazón", 6: "Las Piedras",
         7: "Quintana", 8: "La Rejoya", 9: "Calibío", 10: "H. Cajibío", 11: "H. Totoró", 12: "C.S. Coconuco"}


def base_mapa(ax):
    for i in nodos.index:
        t = nodos.loc[i, "tipo"]
        mk = "s" if t == "deposito" else ("D" if t in ("hospital", "centro") else "o")
        fc = TINTA if t == "deposito" else ("white" if nodos.loc[i, "tipo_via"] == "pavimentada" else "#f0efec")
        ax.scatter(lon[i], lat[i], marker=mk, s=70 if i == 0 else 45, facecolor=fc, edgecolor=TINTA, lw=1, zorder=5)
        ax.annotate(f"{i} {CORTO[i]}", (lon[i], lat[i]), xytext=(4, 4), textcoords="offset points",
                    fontsize=7, color=TINTA2, zorder=6)
    ax.set_xlabel("Longitud (°)")
    ax.set_ylabel("Latitud (°)")
    ax.set_aspect("equal")
    ax.grid(color="#ecebe7", lw=0.6)


def dibujar_ruta(ax, seq, color, ls="-", lw=2):
    seq = [0 if s == 13 else s for s in seq]
    ax.plot(lon[seq], lat[seq], ls, color=color, lw=lw, zorder=3, solid_capstyle="round")


def parse_rutas(txt):
    rutas = []
    for parte in txt.split(" | "):
        m = re.match(r"([\d-]+)(?: \[dron: (.*)\])?", parte.strip())
        seq = [int(v) for v in m.group(1).split("-")]
        dr = []
        if m.group(2):
            dr = [tuple(int(v) for v in s.split(">")) for s in m.group(2).split(", ")]
        rutas.append((seq, dr))
    return rutas


alt = pd.read_csv(os.path.join(RES, "julia_alternativas.csv"))

# ---------- Figura 1: sistema real y plan actual
fig, ax = plt.subplots(figsize=(6.6, 5.2))
base_mapa(ax)
for (seq, _), c in zip(parse_rutas(alt.query("temporada=='Seca' and codigo=='LB'").rutas.iloc[0]), [AZUL, NARANJA]):
    dibujar_ruta(ax, seq, c, lw=1.6)
ax.legend(handles=[Line2D([], [], color=AZUL, lw=2, label="Ruta Sur actual"),
                   Line2D([], [], color=NARANJA, lw=2, label="Ruta Norte-Oriente actual"),
                   Line2D([], [], marker="s", ls="", mfc=TINTA, mec=TINTA, label="Bodega (Popayán)"),
                   Line2D([], [], marker="D", ls="", mfc="white", mec=TINTA, label="Hospital / centro (vía pavimentada)"),
                   Line2D([], [], marker="o", ls="", mfc="#f0efec", mec=TINTA, label="Puesto de salud (vía destapada)")],
          loc="lower right", fontsize=7, frameon=False)
ax.set_title("Red de distribución de MediRuta Cauca y rutas actuales", fontsize=10, color=TINTA, loc="left")
fig.tight_layout()
fig.savefig(os.path.join(FIG, "fig1_sistema.png"))
plt.close(fig)

# ---------- Figura 2: solución óptima A2 en seca y lluvias
fig, axs = plt.subplots(1, 2, figsize=(10, 4.8))
for ax, temp in zip(axs, ["Seca", "Lluvias"]):
    base_mapa(ax)
    fila = alt.query("temporada==@temp and codigo=='A2'").iloc[0]
    for (seq, dr), c in zip(parse_rutas(fila.rutas), [AZUL, NARANJA, AQUA]):
        dibujar_ruta(ax, seq, c)
        for (i, j, h) in dr:
            ax.plot(lon[[i, j, h]], lat[[i, j, h]], ":", color=c, lw=1.5, zorder=4)
    ax.set_title(f"Temporada {temp.lower()}: ${fila.objetivo:,.0f} COP/día".replace(",", "."),
                 fontsize=10, color=TINTA, loc="left")
fig.legend(handles=[Line2D([], [], color=AZUL, lw=2, label="Camión 1 (lleva dron)"),
                       Line2D([], [], color=NARANJA, lw=2, label="Camión 2 (sin dron)"),
                       Line2D([], [], color=TINTA2, lw=1.5, ls=":", label="Vuelo del dron (i → j → h)")],
              loc="lower center", ncol=3, fontsize=8, frameon=False)
fig.tight_layout(rect=(0, 0.06, 1, 1))
fig.savefig(os.path.join(FIG, "fig2_solucion_A2.png"))
plt.close(fig)

# ---------- Figura 3: alternativas por temporada
cods = ["LB", "A1", "A2", "A3", "A4"]
nombres = {"LB": "Plan actual", "A1": "A1 Solo camión\noptimizado", "A2": "A2 Camión + dron\n5 kg",
           "A3": "A3 Camión + dron\n10 kg", "A4": "A4 Solo camión\nflota de 2"}
fig, ax = plt.subplots(figsize=(7.5, 3.8))
w = 0.38
for k, (temp, col) in enumerate([("Seca", AZUL), ("Lluvias", NARANJA)]):
    for x, c in enumerate(cods):
        v = alt.query("temporada==@temp and codigo==@c").objetivo.iloc[0]
        xx = x + (k - 0.5) * w
        if pd.isna(v):
            ax.text(xx, 40, "infactible", rotation=90, ha="center", va="bottom", fontsize=7, color=TINTA2)
            continue
        ax.bar(xx, v / 1000, w - 0.04, color=col, label=temp if x == 0 else None)
        ax.text(xx, v / 1000 + 15, f"{v / 1000:,.0f}".replace(",", "."), ha="center", fontsize=7, color=TINTA2)
ax.set_xticks(range(len(cods)), [nombres[c] for c in cods], fontsize=7.5)
ax.set_ylabel("Costo total diario (miles de COP)")
ax.grid(axis="y", color="#ecebe7", lw=0.6)
ax.set_axisbelow(True)
ax.legend(frameon=False, fontsize=8, loc="upper left")
ax.text(0 + 0.5 * w, 1129154 / 1000 + 70, "excede jornada", ha="center", fontsize=6.5, color=TINTA2)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "fig3_alternativas.png"))
plt.close(fig)

# ---------- Figura 5: arquitectura de la app
fig, ax = plt.subplots(figsize=(9, 2.6))
ax.axis("off")
cajas = [("Entrada de datos", "Tablas editables\n(nodos y parámetros),\ncarga de CSV,\nvalidaciones"),
         ("Módulo del modelo", "vrpd.py\nconstruir_instancia():\ntiempos, autonomía, F"),
         ("Solver", "PuLP → HiGHS\n(o CBC)\nMILP exacto"),
         ("Interfaz de resultados", "KPI, mapa Plotly,\ntabla de rutas,\ncomparación,\nexportar Excel/CSV")]
for k, (t, d) in enumerate(cajas):
    x = 0.02 + k * 0.25
    ax.add_patch(FancyBboxPatch((x, 0.12), 0.2, 0.76, boxstyle="round,pad=0.01,rounding_size=0.02",
                                fc="#f5f9fe", ec=AZUL, lw=1.2, transform=ax.transAxes))
    ax.text(x + 0.1, 0.78, t, ha="center", va="center", fontsize=9, weight="bold", color=TINTA, transform=ax.transAxes)
    ax.text(x + 0.1, 0.42, d, ha="center", va="center", fontsize=7.5, color=TINTA2, transform=ax.transAxes)
    if k < 3:
        ax.annotate("", xy=(x + 0.245, 0.5), xytext=(x + 0.205, 0.5), xycoords="axes fraction",
                    arrowprops=dict(arrowstyle="-|>", color=TINTA2, lw=1.2))
ax.text(0.5, 0.0, "Streamlit (Python) · ejecución local o en Streamlit Community Cloud · usuario sin conocimientos de programación",
        ha="center", fontsize=7.5, color=TINTA2, transform=ax.transAxes)
fig.savefig(os.path.join(FIG, "fig5_arquitectura.png"), bbox_inches="tight")
plt.close(fig)

# ---------- Figura 4: sensibilidad (si existe)
ruta_s = os.path.join(RES, "julia_sensibilidad.csv")
if os.path.exists(ruta_s):
    s = pd.read_csv(ruta_s)
    a1 = {t: alt.query("temporada==@t and codigo=='A1'").objetivo.iloc[0] for t in ["Seca", "Lluvias"]}
    fig, axs = plt.subplots(1, 3, figsize=(11, 3.4))
    ax = axs[0]
    for temp, col in [("Seca", AZUL), ("Lluvias", NARANJA)]:
        d = s.query("parametro=='costo_fijo_dron' and temporada==@temp")
        ax.plot(d.valor / 1000, d.objetivo / 1000, "-o", color=col, ms=4, lw=2, label=f"Camión + dron ({temp.lower()})")
        ax.axhline(a1[temp] / 1000, color=col, ls="--", lw=1, alpha=0.7)
        ax.text(122, a1[temp] / 1000, f"solo camión\n({temp.lower()})", fontsize=6.5, color=TINTA2, va="center")
    ax.set_xlabel("Costo fijo diario del dron (miles de COP)")
    ax.set_ylabel("Costo óptimo (miles de COP/día)")
    ax.set_title("a) Costo del dron", loc="left", fontsize=9, color=TINTA)
    ax.legend(frameon=False, fontsize=7)
    for ax, par, xl, tt in [(axs[1], "vel_camion_lluvia_kmh", "Velocidad del camión en lluvias (km/h)", "b) Velocidad en lluvias"),
                            (axs[2], "jornada_max_min", "Jornada máxima (min)", "c) Jornada (lluvias)")]:
        for conf, col in [("Solo camión", GRIS), ("Camión + dron", NARANJA)]:
            d = s.query("parametro==@par and configuracion==@conf").sort_values("valor")
            ok = d.dropna(subset=["objetivo"])
            ax.plot(ok.valor, ok.objetivo / 1000, "-o", color=col if col != GRIS else "#6b6a66", ms=4, lw=2, label=conf)
            for _, r in d[d.objetivo.isna()].iterrows():
                ax.annotate("infactible", (r.valor, ax.get_ylim()[0] if ok.empty else ok.objetivo.min() / 1000),
                            fontsize=6.5, color=TINTA2, rotation=90, ha="center", va="bottom")
            for _, r in ok.iterrows():
                ax.annotate(str(int(r.camiones)), (r.valor, r.objetivo / 1000), xytext=(0, 5),
                            textcoords="offset points", fontsize=6, color=TINTA2, ha="center")
        ax.set_xlabel(xl)
        ax.set_title(tt + " · nº = camiones", loc="left", fontsize=9, color=TINTA)
        ax.legend(frameon=False, fontsize=7)
    for ax in axs:
        ax.grid(color="#ecebe7", lw=0.6)
        ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig4_sensibilidad.png"))
    plt.close(fig)
print("figuras listas")
