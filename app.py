"""
RutaDron Cauca – Aplicación de apoyo a la decisión (Streamlit)
MediRuta Cauca S.A.S. · Distribución de medicamentos camión + dron

Ejecutar desde la raíz:  streamlit run app.py
"""
import io
import os
import sys
import time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(RAIZ, "python"))
import vrpd  # noqa: E402

st.set_page_config(page_title="RutaDron Cauca", page_icon="🚚", layout="wide")

COLORES = ["#1f6f8b", "#e07a1f", "#4c9a2a", "#8e44ad"]
ETQ = {
    "n_grupos": "Camiones disponibles", "cap_camion_kg": "Capacidad del camión (kg)",
    "jornada_max_min": "Jornada máxima (min)", "vel_camion_kmh": "Velocidad camión, seca (km/h)",
    "vel_camion_lluvia_kmh": "Velocidad camión, lluvias (km/h)", "factor_circuidad": "Factor de circuidad vial",
    "factor_lluvia_destapada": "Multiplicador vías destapadas en lluvias", "vel_dron_kmh": "Velocidad del dron (km/h)",
    "factor_vuelo": "Factor de trayectoria del dron", "peso_dron_kg": "Peso del dron vacío (kg)",
    "cap_dron_kg": "Carga máxima del dron (kg)", "autonomia_vacio_min": "Autonomía del dron vacío (min)",
    "factor_autonomia_lluvia": "Factor de autonomía en lluvias", "servicio_dron_min": "Tiempo de entrega del dron (min)",
    "costo_camion_h": "Costo camión en movimiento (COP/h)", "costo_dron_h": "Costo dron en vuelo (COP/h)",
    "costo_espera_h": "Costo de espera del camión (COP/h)", "costo_fijo_camion": "Costo fijo diario camión (COP)",
    "costo_fijo_dron": "Costo fijo diario dron (COP)",
}


def cop(v):
    return "$" + f"{v:,.0f}".replace(",", ".")


@st.cache_data
def datos_iniciales():
    nodos, P = vrpd.cargar(os.path.join(RAIZ, "datos"))
    rutas = pd.read_csv(os.path.join(RAIZ, "datos", "rutas_actuales.csv"))
    return nodos, P, rutas


def validar(nodos: pd.DataFrame, P: dict):
    """Devuelve (errores, advertencias)."""
    err, adv = [], []
    req = ["id", "nombre", "lat", "lon", "demanda_kg", "servicio_min", "tipo_via", "factor_via", "apto_dron"]
    falt = [c for c in req if c not in nodos.columns]
    if falt:
        return [f"Faltan columnas en la tabla de nodos: {', '.join(falt)}"], adv
    if nodos[req].isnull().any().any():
        filas = nodos[nodos[req].isnull().any(axis=1)]["nombre"].fillna("(sin nombre)").tolist()
        err.append(f"Hay campos vacíos en: {', '.join(map(str, filas))}")
    if len(nodos) < 1 or str(nodos.iloc[0]["tipo"] if "tipo" in nodos else "") not in ("deposito", "depósito"):
        adv.append("La primera fila se usará como bodega (depósito).")
    for c in ["demanda_kg", "servicio_min", "factor_via"]:
        if (pd.to_numeric(nodos[c], errors="coerce") < 0).any():
            err.append(f"La columna '{c}' tiene valores negativos.")
    if not nodos["lat"].between(-4.5, 13.5).all() or not nodos["lon"].between(-82, -66).all():
        err.append("Hay coordenadas fuera de Colombia (lat −4,5 a 13,5; lon −82 a −66). Revise el signo de la longitud.")
    if (nodos["factor_via"].iloc[1:] < 1).any():
        adv.append("Algún factor de vía es menor que 1: la vía sería más rápida que una pavimentada ideal.")
    if not set(nodos["apto_dron"].unique()).issubset({0, 1}):
        err.append("La columna 'apto_dron' solo admite 0 o 1.")
    if not set(nodos["tipo_via"].str.lower().unique()).issubset({"pavimentada", "destapada"}):
        err.append("La columna 'tipo_via' solo admite 'pavimentada' o 'destapada'.")
    for k, v in P.items():
        if v < 0:
            err.append(f"El parámetro '{ETQ.get(k, k)}' no puede ser negativo.")
    if P["n_grupos"] < 1:
        err.append("Debe haber al menos un camión disponible.")
    if P["vel_camion_kmh"] <= 0 or P["vel_camion_lluvia_kmh"] <= 0 or P["vel_dron_kmh"] <= 0:
        err.append("Las velocidades deben ser mayores que cero.")
    grandes = nodos.iloc[1:][nodos.iloc[1:]["demanda_kg"] > P["cap_camion_kg"]]
    if len(grandes):
        err.append("Clientes con demanda mayor que la capacidad del camión: " + ", ".join(grandes["nombre"]))
    if nodos.iloc[1:]["demanda_kg"].sum() > P["cap_camion_kg"] * P["n_grupos"]:
        err.append("La demanda total supera la capacidad de toda la flota.")
    if P["jornada_max_min"] > 720:
        adv.append("La jornada supera 12 horas; verifique que sea correcta.")
    return err, adv


def mapa(ins, res, titulo):
    nod = ins.nodos
    fig = go.Figure()
    end = ins.n + 1
    for idx, ru in enumerate(res["rutas"]):
        col = COLORES[idx % len(COLORES)]
        seq = [0 if s == end else s for s in ru["secuencia"]]
        fig.add_trace(go.Scatter(x=nod.loc[seq, "lon"], y=nod.loc[seq, "lat"], mode="lines",
                                 line=dict(color=col, width=3), name=f"Camión {ru['grupo']}"))
        for (i, j, h) in ru["salidas_dron"]:
            h = 0 if h == end else h
            fig.add_trace(go.Scatter(x=nod.loc[[i, j, h], "lon"], y=nod.loc[[i, j, h], "lat"], mode="lines",
                                     line=dict(color=col, width=2, dash="dot"), showlegend=False,
                                     hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines", line=dict(color="gray", dash="dot"), name="Vuelo del dron"))
    tipo_m = {"deposito": "square", "hospital": "diamond", "centro": "diamond", "puesto": "circle"}
    fig.add_trace(go.Scatter(
        x=nod["lon"], y=nod["lat"], mode="markers+text", text=[str(i) for i in nod.index],
        textposition="top center", name="Nodos",
        marker=dict(size=[16] + [11] * (len(nod) - 1), color="white", line=dict(color="black", width=1.5),
                    symbol=[tipo_m.get(t, "circle") for t in nod.get("tipo", ["puesto"] * len(nod))]),
        hovertext=[f"{r.nombre}<br>{r.demanda_kg} kg" for r in nod.itertuples()], hoverinfo="text"))
    fig.update_layout(title=titulo, height=520, margin=dict(l=10, r=10, t=40, b=10),
                      xaxis_title="Longitud", yaxis_title="Latitud", plot_bgcolor="#f7f7f4",
                      yaxis=dict(scaleanchor="x", scaleratio=1), legend=dict(orientation="h", y=-0.15))
    return fig


def tabla_rutas(ins, res):
    end = ins.n + 1
    nom = ins.nodos["nombre"]
    filas = []
    for ru in res["rutas"]:
        seq = [0 if s == end else s for s in ru["secuencia"]]
        dr = "; ".join(f"{nom[j]} (sale en {nom[i]}, vuelve en {nom[0 if h == end else h]})"
                       for (i, j, h) in ru["salidas_dron"]) or "—"
        filas.append({
            "Camión": ru["grupo"], "Lleva dron": "Sí" if ru["lleva_dron"] else "No",
            "Recorrido del camión": " → ".join(nom[s] for s in seq), "Entregas con dron": dr,
            "km camión": round(ru["km_camion"], 1), "Duración (h)": round(ru["duracion_min"] / 60, 2),
            "Espera por dron (min)": round(ru["min_espera"], 1), "Carga (kg)": round(ru["carga_kg"], 1),
            "Costo (COP)": round(ru["costo_fijo"] + ru["costo_camion"] + ru["costo_dron"] + ru["costo_espera"]),
        })
    return pd.DataFrame(filas)


# ---------------------------------------------------------------- estado
nodos0, P0, rutas0 = datos_iniciales()
if "nodos" not in st.session_state:
    st.session_state.nodos = nodos0.copy()
    st.session_state.P = dict(P0)
    st.session_state.escenarios = []
    st.session_state.ultimo = None

st.title("RutaDron Cauca")
st.caption("Apoyo a la decisión para planear la entrega de medicamentos con camiones y drones · MediRuta Cauca S.A.S. (datos ficticios)")

with st.sidebar:
    st.header("1. Escenario")
    nombre_esc = st.text_input("Nombre del escenario", value="Mi escenario")
    temporada = st.radio("Temporada", ["Seca", "Lluvias"], horizontal=True)
    usar_dron = st.toggle("Permitir entregas con dron", value=True)
    P = st.session_state.P
    P["n_grupos"] = st.number_input(ETQ["n_grupos"], 1, 4, int(P["n_grupos"]))
    P["jornada_max_min"] = st.number_input(ETQ["jornada_max_min"], 60, 900, int(P["jornada_max_min"]), step=30)
    P["costo_fijo_dron"] = st.number_input(ETQ["costo_fijo_dron"], 0, 500000, int(P["costo_fijo_dron"]), step=5000)
    P["cap_dron_kg"] = st.number_input(ETQ["cap_dron_kg"], 0.0, 50.0, float(P["cap_dron_kg"]), step=0.5)
    st.header("2. Resolver")
    solver = st.selectbox("Solver", ["HiGHS (rápido)", "CBC"], index=0)
    limite = st.slider("Tiempo máximo de cálculo (s)", 30, 900, 300, step=30)
    if st.button("↺ Restaurar datos originales"):
        st.session_state.nodos = nodos0.copy()
        st.session_state.P = dict(P0)
        st.rerun()

tab_datos, tab_res, tab_comp, tab_ayuda = st.tabs(["📋 Datos", "▶️ Optimizar", "⚖️ Comparar escenarios", "❓ Ayuda"])

with tab_datos:
    st.subheader("Clientes (puestos de salud) y bodega")
    st.write("Edite las celdas directamente, agregue filas con el botón **+** o cargue un archivo CSV con las mismas columnas. "
             "La **primera fila es la bodega**. Un cliente con demanda 0 no se visita.")
    up = st.file_uploader("Cargar nodos desde CSV", type="csv")
    if up is not None:
        try:
            st.session_state.nodos = pd.read_csv(up)
            st.success("Archivo cargado.")
        except Exception as e:  # noqa: BLE001
            st.error(f"No se pudo leer el archivo: {e}")
    st.session_state.nodos = st.data_editor(
        st.session_state.nodos, num_rows="dynamic", use_container_width=True, key="ed_nodos",
        column_config={
            "tipo_via": st.column_config.SelectboxColumn("tipo_via", options=["pavimentada", "destapada"]),
            "apto_dron": st.column_config.SelectboxColumn("apto_dron", options=[0, 1],
                                                          help="1 = el puesto tiene zona de aterrizaje y permiso de vuelo"),
            "demanda_kg": st.column_config.NumberColumn("demanda_kg", min_value=0.0, format="%.1f"),
        })
    st.subheader("Parámetros técnicos y de costo")
    dfp = pd.DataFrame([{"Parámetro": ETQ.get(k, k), "clave": k, "Valor": v} for k, v in P.items()
                        if k not in ("usar_dron", "temporada")])
    dfp = st.data_editor(dfp, disabled=["Parámetro", "clave"], hide_index=True, use_container_width=True, key="ed_par")
    for r in dfp.itertuples():
        P[r.clave] = float(r.Valor)
    st.download_button("⬇️ Descargar nodos (CSV)", st.session_state.nodos.to_csv(index=False).encode("utf-8"),
                       "nodos.csv", "text/csv")

with tab_res:
    nodos = st.session_state.nodos.copy()
    Pc = dict(P)
    Pc["usar_dron"] = 1.0 if usar_dron else 0.0
    Pc["temporada"] = 1.0 if temporada == "Lluvias" else 0.0
    errores, advert = validar(nodos, Pc)
    for a in advert:
        st.warning(a)
    for e in errores:
        st.error(e)
    col1, col2 = st.columns([1, 3])
    lanzar = col1.button("▶️ Optimizar plan de entregas", type="primary", disabled=bool(errores))
    col2.info(f"Escenario: **{nombre_esc}** · Temporada **{temporada}** · Dron **{'sí' if usar_dron else 'no'}** · "
              f"{int(Pc['n_grupos'])} camiones")
    if lanzar:
        with st.spinner("Calculando el plan óptimo… (puede tardar uno o dos minutos)"):
            ins = vrpd.construir_instancia(nodos, Pc)
            res = vrpd.resolver(ins, solver="HIGHS" if solver.startswith("HiGHS") else "CBC", time_limit=limite)
        # plan actual con la misma función de costo
        act = None
        try:
            if len(nodos) == len(nodos0):
                seqs = [[int(v) for v in s.split("-")] for s in rutas0["secuencia"]]
                seqs = [s[:-1] + [ins.n + 1] for s in seqs]
                act, _ = vrpd.evaluar_rutas_fijas(ins, seqs)
        except Exception:  # noqa: BLE001
            act = None
        st.session_state.ultimo = (nombre_esc, temporada, usar_dron, ins, res, act)

    if st.session_state.ultimo:
        nombre_r, temp_r, dron_r, ins, res, act = st.session_state.ultimo
        if res["estado"] != "Optimal":
            st.error("❌ **No existe un plan que cumpla todas las condiciones** (modelo infactible o sin solución en el tiempo dado).\n\n"
                     "Posibles causas: la jornada es muy corta para llegar a todos los clientes, faltan camiones, "
                     "o la capacidad no alcanza. Pruebe aumentar la jornada, agregar un camión o permitir el dron.")
        else:
            costo = res["objetivo"]
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Costo total del día", cop(costo),
                      delta=(f"{(costo - act) / act * 100:+.1f}% vs plan actual" if act else None), delta_color="inverse")
            k2.metric("Camiones usados", len(res["rutas"]))
            k3.metric("Drones usados", sum(r["lleva_dron"] for r in res["rutas"]))
            k4.metric("Entregas con dron", sum(len(r["salidas_dron"]) for r in res["rutas"]))
            st.caption(f"Estado: óptimo · solver {res['solver']} · {res['tiempo_s']:.1f} s · "
                       f"{res['n_bin']} variables binarias, {res['n_restr']} restricciones")
            if act:
                st.write(f"Plan actual (rutas manuales, solo camión) con los mismos datos: **{cop(act)}**")
            st.plotly_chart(mapa(ins, res, f"{nombre_r} – temporada {temp_r.lower()}"), use_container_width=True)
            tr = tabla_rutas(ins, res)
            st.dataframe(tr, use_container_width=True, hide_index=True)
            c1, c2 = st.columns(2)
            if c1.button("💾 Guardar para comparar"):
                st.session_state.escenarios.append({
                    "Escenario": nombre_r, "Temporada": temp_r, "Dron": "Sí" if dron_r else "No",
                    "Costo (COP)": round(costo), "Camiones": len(res["rutas"]),
                    "Drones": sum(r["lleva_dron"] for r in res["rutas"]),
                    "km camión": round(sum(r["km_camion"] for r in res["rutas"]), 1),
                    "Jornada más larga (h)": round(max(r["duracion_min"] for r in res["rutas"]) / 60, 2),
                    "Plan actual (COP)": round(act) if act else None,
                })
                st.success("Escenario guardado. Véalo en la pestaña «Comparar escenarios».")
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as xw:
                tr.to_excel(xw, sheet_name="Rutas", index=False)
                ins.nodos.to_excel(xw, sheet_name="Nodos", index=False)
                pd.DataFrame([{"parametro": k, "valor": v} for k, v in Pc.items()]).to_excel(xw, sheet_name="Parametros", index=False)
            c2.download_button("⬇️ Exportar plan a Excel", buf.getvalue(), f"plan_{nombre_r}.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with tab_comp:
    esc = st.session_state.escenarios
    if not esc:
        st.info("Aún no hay escenarios guardados. Optimice un escenario y pulse «Guardar para comparar».")
    else:
        df = pd.DataFrame(esc)
        base = df["Costo (COP)"].iloc[0]
        df["Diferencia vs primero (%)"] = ((df["Costo (COP)"] - base) / base * 100).round(1)
        st.dataframe(df, use_container_width=True, hide_index=True)
        etiquetas = [f"{i + 1}. {e} ({t})" for i, (e, t) in enumerate(zip(df["Escenario"], df["Temporada"]))]
        fig = go.Figure(go.Bar(x=etiquetas, y=df["Costo (COP)"],
                               marker_color=COLORES[0], text=[cop(v) for v in df["Costo (COP)"]], textposition="outside"))
        fig.update_layout(yaxis_title="Costo total del día (COP)", height=420, plot_bgcolor="white")
        st.plotly_chart(fig, use_container_width=True)
        st.download_button("⬇️ Exportar comparación (CSV)", df.to_csv(index=False).encode("utf-8"), "comparacion.csv")
        if st.button("🗑️ Borrar escenarios"):
            st.session_state.escenarios = []
            st.rerun()

with tab_ayuda:
    st.markdown("""
**¿Qué decide la aplicación?** Qué camiones salen, en qué orden visitan los puestos de salud, qué camiones llevan dron
y qué puestos se atienden con el dron (y desde qué parada sale y a qué parada regresa), al **menor costo total del día**.

**Reglas que respeta el plan**
- Cada puesto recibe su pedido una sola vez, por camión o por dron.
- El dron lleva un pedido por vuelo, solo si pesa menos que su carga máxima y si el vuelo cabe en su autonomía
  (que baja cuando el paquete es más pesado).
- El dron despega del camión y aterriza en la **siguiente parada** de ese mismo camión; si llega después, el camión lo espera.
- Ningún camión supera su capacidad ni la jornada máxima.
- En temporada de lluvias el camión va más lento y las vías destapadas empeoran.

**Pasos:** 1) revise o edite datos → 2) elija temporada y opciones → 3) Optimizar → 4) guarde y compare escenarios → 5) exporte.
""")
