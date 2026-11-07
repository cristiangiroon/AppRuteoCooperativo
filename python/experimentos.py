"""Contraste en Python: resuelve las mismas alternativas que julia/experimentos.jl.
Uso: python python/experimentos.py [solver] [dir_datos] [dir_resultados]
     solver = CBC (por defecto) | HIGHS
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vrpd  # noqa: E402

solver = sys.argv[1] if len(sys.argv) > 1 else "CBC"
dir_datos = sys.argv[2] if len(sys.argv) > 2 else "datos"
dir_res = sys.argv[3] if len(sys.argv) > 3 else "resultados"
os.makedirs(dir_res, exist_ok=True)

ALTERNATIVAS = [
    ("A1", "Solo camión optimizado", {"usar_dron": 0.0}),
    ("A2", "Camión + dron estándar (5 kg)", {}),
    ("A3", "Camión + dron de 10 kg", {"cap_dron_kg": 10.0, "peso_dron_kg": 18.0,
                                      "autonomia_vacio_min": 35.0, "costo_fijo_dron": 65000.0}),
    ("A4", "Solo camión, flota de 2", {"usar_dron": 0.0, "n_grupos": 2.0}),
    ("A5", "Camión + dron, flota de 2", {"n_grupos": 2.0}),
]

nodos, P0 = vrpd.cargar(dir_datos)
filas = []
for temp, tnom in [(0.0, "Seca"), (1.0, "Lluvias")]:
    for cod, nom, cambios in ALTERNATIVAS:
        P = dict(P0)
        P["temporada"] = temp
        P.update(cambios)
        ins = vrpd.construir_instancia(nodos, P)
        r = vrpd.resolver(ins, solver=solver, time_limit=1800)
        filas.append({"temporada": tnom, "codigo": cod, "alternativa": nom, "estado": r["estado"],
                      "objetivo": r["objetivo"], "tiempo_s": round(r["tiempo_s"], 2),
                      "n_bin": r["n_bin"], "n_cont": r["n_cont"], "n_restr": r["n_restr"]})
        print(tnom, cod, r["estado"], r["objetivo"], f"{r['tiempo_s']:.1f}s", flush=True)
        pd.DataFrame(filas).to_csv(f"{dir_res}/python_{solver.lower()}_alternativas.csv", index=False)
