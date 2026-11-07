"""
VRP-D acotado (camión + dron cooperativo) para MediRuta Cauca S.A.S.
Herramienta de contraste: Python + PuLP (solver CBC por defecto, HiGHS opcional).

Formulación adaptada de Zhen et al. (2023), IISE Transactions 55(3):
  - cada grupo k = 1 camión + 1 dron dedicado;
  - el dron atiende 1 cliente por salida (i, j, h) y regresa a SU camión;
  - ACOTACIÓN: el encuentro (h) es la siguiente parada del camión después de i
    (rendezvous consecutivo), lo que vuelve lineal el costo de espera;
  - autonomía del dron dependiente de la carga: E_j = eD * f / (f + q_j).
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import pandas as pd
import pulp


# --------------------------------------------------------------------------
# Datos
# --------------------------------------------------------------------------
def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def leer_parametros(path):
    df = pd.read_csv(path)
    return {r.parametro: float(r.valor) for r in df.itertuples()}


@dataclass
class Instancia:
    nodos: pd.DataFrame            # incluye depósito id=0
    P: dict                        # parámetros
    n: int = 0
    tK: dict = field(default_factory=dict)   # min, camión  (i,j)
    tD: dict = field(default_factory=dict)   # min, dron    (i,j)
    dK: dict = field(default_factory=dict)   # km vial
    E: dict = field(default_factory=dict)    # autonomía con carga q_j, min
    A: list = field(default_factory=list)    # arcos del camión
    F: list = field(default_factory=list)    # salidas factibles (i,j,h)
    w: dict = field(default_factory=dict)    # espera del camión por salida, min
    q: dict = field(default_factory=dict)
    s: dict = field(default_factory=dict)


def construir_instancia(nodos: pd.DataFrame, P: dict) -> Instancia:
    # Los clientes con demanda cero no requieren visita (caso extremo de verificación)
    nodos = nodos[(nodos.index == 0) | (nodos["demanda_kg"] > 0)].reset_index(drop=True).copy()
    n = len(nodos) - 1                     # clientes 1..n ; depósito final = n+1
    end = n + 1
    ins = Instancia(nodos=nodos, P=P, n=n)
    lat = {i: nodos.loc[i, "lat"] for i in range(n + 1)}
    lon = {i: nodos.loc[i, "lon"] for i in range(n + 1)}
    lluvia = P.get("temporada", 0) >= 0.5
    vel = P["vel_camion_lluvia_kmh"] if lluvia else P["vel_camion_kmh"]
    rv = {}
    for i in range(n + 1):
        r = float(nodos.loc[i, "factor_via"])
        if lluvia and str(nodos.loc[i, "tipo_via"]).strip().lower() == "destapada":
            r *= P["factor_lluvia_destapada"]
        rv[i] = r
    lat[end], lon[end], rv[end] = lat[0], lon[0], rv[0]
    ins.q = {i: float(nodos.loc[i, "demanda_kg"]) for i in range(1, n + 1)}
    ins.s = {i: float(nodos.loc[i, "servicio_min"]) for i in range(1, n + 1)}
    ins.s[end] = 0.0
    apto = {i: int(nodos.loc[i, "apto_dron"]) for i in range(1, n + 1)}

    N0 = list(range(0, n + 1))
    Np = list(range(1, n + 2))
    for i in N0 + [end]:
        for j in N0 + [end]:
            d = haversine_km(lat[i], lon[i], lat[j], lon[j])
            dk = d * P["factor_circuidad"]
            ins.dK[i, j] = dk
            ins.tK[i, j] = dk * (rv[i] + rv[j]) / 2 / vel * 60
            ins.tD[i, j] = d * P["factor_vuelo"] / P["vel_dron_kmh"] * 60

    ins.A = [(i, j) for i in N0 for j in Np if i != j]   # incluye (0, n+1): grupo que no se mueve

    f, eD, mD = P["peso_dron_kg"], P["autonomia_vacio_min"], P["cap_dron_kg"]
    if lluvia:
        eD *= P["factor_autonomia_lluvia"]
    for j in range(1, n + 1):
        ins.E[j] = eD * f / (f + ins.q[j]) if ins.q[j] <= mD else 0.0

    if P.get("usar_dron", 1) >= 0.5:
        for (i, h) in ins.A:
            for j in range(1, n + 1):
                if j in (i, h) or not apto[j] or ins.q[j] > mD:
                    continue
                vuelo = ins.tD[i, j] + P["servicio_dron_min"] + ins.tD[j, h]
                if vuelo <= ins.E[j] + 1e-9:
                    ins.F.append((i, j, h))
                    ins.w[i, j, h] = max(0.0, vuelo - ins.tK[i, h] - ins.s[h])
    return ins


def cargar(dir_datos="datos"):
    nodos = pd.read_csv(f"{dir_datos}/nodos.csv")
    P = leer_parametros(f"{dir_datos}/parametros.csv")
    return nodos, P


# --------------------------------------------------------------------------
# Modelo MILP
# --------------------------------------------------------------------------
def resolver(ins: Instancia, solver="CBC", time_limit=600, gap=1e-4, verbose=False):
    P, n = ins.P, ins.n
    end = n + 1
    K = list(range(1, int(P["n_grupos"]) + 1))
    C = list(range(1, n + 1))
    A, F = ins.A, ins.F
    usar_dron = P.get("usar_dron", 1) >= 0.5
    sG = P["costo_fijo_camion"]
    sGD = P["costo_fijo_dron"]
    sK, sD, sW = P["costo_camion_h"] / 60, P["costo_dron_h"] / 60, P["costo_espera_h"] / 60
    sdr = P["servicio_dron_min"]

    m = pulp.LpProblem("VRPD_MediRuta", pulp.LpMinimize)
    def var(nombre, low=None, up=None, cat="Continuous"):
        # PuLP >= 4 crea las variables desde el problema; PuLP 2.x/3.x con LpVariable
        if hasattr(m, "add_variable"):
            return m.add_variable(nombre, lowBound=low, upBound=up, cat=cat)
        return pulp.LpVariable(nombre, lowBound=low, upBound=up, cat=cat)

    x = {(i, j, k): var(f"x_{i}_{j}_{k}", cat="Binary") for (i, j) in A for k in K}
    y = {(i, j, h, k): var(f"y_{i}_{j}_{h}_{k}", cat="Binary") for (i, j, h) in F for k in K}
    z = {k: var(f"z_{k}", cat="Binary") for k in K}
    v = {k: var(f"v_{k}", cat="Binary") for k in K} if usar_dron else {}
    u = {(i, k): var(f"u_{i}_{k}", low=1, up=n) for i in C for k in K}

    def costo_salida(i, j, h):
        return sD * (ins.tD[i, j] + sdr + ins.tD[j, h]) + sW * ins.w[i, j, h]

    # (1) Función objetivo
    m += (pulp.lpSum(sG * z[k] for k in K) + pulp.lpSum(sGD * v[k] for k in v)
          + pulp.lpSum(sK * ins.tK[i, j] * x[i, j, k] for (i, j) in A for k in K)
          + pulp.lpSum(costo_salida(i, j, h) * y[i, j, h, k] for (i, j, h) in F for k in K))

    out_arcs = {i: [(a, b) for (a, b) in A if a == i] for i in range(0, end + 1)}
    in_arcs = {j: [(a, b) for (a, b) in A if b == j] for j in range(0, end + 1)}
    F_by_arc = {}
    F_by_j = {j: [] for j in C}
    for (i, j, h) in F:
        F_by_arc.setdefault((i, h), []).append(j)
        F_by_j[j].append((i, h))

    for k in K:
        # (2)-(3) salida y regreso al depósito
        m += pulp.lpSum(x[i, j, k] for (i, j) in out_arcs[0]) == z[k], f"sal_{k}"
        m += pulp.lpSum(x[i, j, k] for (i, j) in in_arcs[end]) == z[k], f"lleg_{k}"
        for j in C:
            # (4) conservación de flujo y visita única por camión
            m += (pulp.lpSum(x[i, jj, k] for (i, jj) in in_arcs[j])
                  == pulp.lpSum(x[jj, h, k] for (jj, h) in out_arcs[j])), f"flujo_{j}_{k}"
            m += pulp.lpSum(x[i, jj, k] for (i, jj) in in_arcs[j]) <= z[k], f"visita_{j}_{k}"
        # (6) a lo sumo una salida de dron por arco recorrido (enlace binario)
        for (i, h), js in F_by_arc.items():
            m += pulp.lpSum(y[i, j, h, k] for j in js) <= x[i, h, k], f"enlace_{i}_{h}_{k}"
            m += pulp.lpSum(y[i, j, h, k] for j in js) <= v[k], f"usodron_{i}_{h}_{k}"
        if usar_dron:
            m += v[k] <= z[k], f"dron_en_camion_{k}"
        # (7) capacidad del camión (incluye lo que lleva el dron)
        m += (pulp.lpSum(ins.q[j] * x[i, j, k] for (i, j) in A if j in ins.q)
              + pulp.lpSum(ins.q[j] * y[i, j, h, k] for (i, j, h) in F)
              <= P["cap_camion_kg"] * z[k]), f"cap_{k}"
        # (8) jornada máxima (conducción + servicio + espera)
        m += (pulp.lpSum((ins.tK[i, j] + ins.s.get(j, 0)) * x[i, j, k] for (i, j) in A)
              + pulp.lpSum(ins.w[i, j, h] * y[i, j, h, k] for (i, j, h) in F)
              <= P["jornada_max_min"] * z[k]), f"jornada_{k}"
        # (9) eliminación de subtours (MTZ)
        for (i, j) in A:
            if i in C and j in C:
                m += u[j, k] >= u[i, k] + 1 - n * (1 - x[i, j, k]), f"mtz_{i}_{j}_{k}"
    # (5) cada cliente se atiende exactamente una vez (camión o dron)
    for j in C:
        m += (pulp.lpSum(x[i, jj, k] for (i, jj) in in_arcs[j] for k in K)
              + pulp.lpSum(y[i, j, h, k] for (i, h) in F_by_j[j] for k in K) == 1), f"cobertura_{j}"
    # (10) ruptura de simetría (flota homogénea)
    for a, b in zip(K[:-1], K[1:]):
        m += z[a] >= z[b], f"sim_{a}"

    if solver.upper() == "HIGHS":
        slv = pulp.HiGHS(msg=verbose, timeLimit=time_limit, gapRel=gap)
    else:
        cbc = getattr(pulp, "PULP_CBC_CMD", None)
        if cbc is None or not cbc().available():
            cbc = pulp.COIN_CMD   # PuLP >= 4: instalar con  pip install "pulp[cbc]"
        slv = cbc(msg=verbose, timeLimit=time_limit, gapRel=gap)
    t0 = time.perf_counter()
    sol = m.solve(slv)
    t = time.perf_counter() - t0
    if hasattr(sol, "status"):                      # PuLP >= 4 devuelve un objeto con el estado
        estado = sol.status.name
    else:                                           # PuLP 2.x/3.x
        estado = pulp.LpStatus[m.status]
    res = {"estado": estado, "tiempo_s": t, "modelo": m,
           "n_bin": len(x) + len(y) + len(z) + len(v), "n_cont": len(u),
           "n_restr": len(m.constraints() if callable(m.constraints) else m.constraints), "solver": solver}
    if estado != "Optimal":
        res["objetivo"] = None
        return res
    res["objetivo"] = pulp.value(m.objective)
    res.update(extraer_solucion(ins, x, y, z, v, K, sG, sGD, sK, sD, sW, sdr))
    return res


def extraer_solucion(ins, x, y, z, v, K, sG, sGD, sK, sD, sW, sdr):
    end = ins.n + 1
    rutas = []
    for k in K:
        if z[k].value() < 0.5:
            continue
        succ = {i: j for (i, j, kk) in x if kk == k and x[i, j, kk].value() > 0.5}
        seq, cur = [0], 0
        while cur != end and cur in succ:
            cur = succ[cur]
            seq.append(cur)
        salidas = [(i, j, h) for (i, j, h, kk) in y if kk == k and y[i, j, h, kk].value() > 0.5]
        km = sum(ins.dK[a, b] for a, b in zip(seq[:-1], seq[1:]))
        t_cond = sum(ins.tK[a, b] for a, b in zip(seq[:-1], seq[1:]))
        t_serv = sum(ins.s.get(b, 0) for b in seq[1:])
        t_esp = sum(ins.w[s] for s in salidas)
        t_vuelo = sum(ins.tD[i, j] + sdr + ins.tD[j, h] for (i, j, h) in salidas)
        carga = sum(ins.q[j] for j in seq[1:-1]) + sum(ins.q[j] for (_, j, _) in salidas)
        rutas.append({
            "grupo": k, "secuencia": [0 if v == end else v for v in seq], "salidas_dron": salidas,
            "km_camion": km, "km_dron": sum((ins.tD[i, j] + ins.tD[j, h]) * ins.P["vel_dron_kmh"] / 60 for (i, j, h) in salidas),
            "min_conduccion": t_cond, "min_servicio": t_serv, "min_espera": t_esp, "min_vuelo": t_vuelo,
            "duracion_min": t_cond + t_serv + t_esp, "carga_kg": carga,
            "lleva_dron": bool(k in v and v[k].value() > 0.5),
            "costo_fijo": sG + (sGD if (k in v and v[k].value() > 0.5) else 0.0), "costo_camion": sK * t_cond, "costo_dron": sD * t_vuelo, "costo_espera": sW * t_esp,
        })
    return {"rutas": rutas}


def evaluar_rutas_fijas(ins: Instancia, rutas_seq: list[list[int]], con_dron=False):
    """Costo de la operación actual (rutas manuales, solo camión) con la misma función de costo."""
    P = ins.P
    sG = P["costo_fijo_camion"]
    sK = P["costo_camion_h"] / 60
    detalle = []
    for seq in rutas_seq:
        t = sum(ins.tK[a, b] for a, b in zip(seq[:-1], seq[1:]))
        km = sum(ins.dK[a, b] for a, b in zip(seq[:-1], seq[1:]))
        serv = sum(ins.s.get(b, 0) for b in seq[1:-1])
        carga = sum(ins.q[b] for b in seq[1:-1])
        detalle.append({"secuencia": seq, "km_camion": km, "min_conduccion": t, "min_servicio": serv,
                        "duracion_min": t + serv, "carga_kg": carga, "costo": sG + sK * t})
    return sum(d["costo"] for d in detalle), detalle


if __name__ == "__main__":
    import sys
    nodos, P = cargar(sys.argv[1] if len(sys.argv) > 1 else "datos")
    ins = construir_instancia(nodos, P)
    print("clientes:", ins.n, "arcos:", len(ins.A), "salidas F:", len(ins.F))
    r = resolver(ins, solver=sys.argv[2] if len(sys.argv) > 2 else "CBC", verbose=False)
    print(r["estado"], r["objetivo"], f"{r['tiempo_s']:.2f}s")
    for ru in r.get("rutas", []):
        print(ru["grupo"], ru["secuencia"], ru["salidas_dron"], round(ru["duracion_min"]), round(ru["km_camion"], 1))
