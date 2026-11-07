# RutaDron Cauca — Ruteo cooperativo camión-dron (MediRuta Cauca S.A.S., caso ficticio)

Modelo MILP de ruteo de vehículos con drones (VRP-D), adaptado de Zhen et al. (2023),
*IISE Transactions* 55(3), 271–287, https://doi.org/10.1080/24725854.2022.2060535,
aplicado a la distribución de medicamentos a 12 puestos de salud y hospitales rurales desde Popayán.

> La empresa y sus datos son ficticios, construidos para ser cercanos a la realidad caucana.

## Estructura

| Carpeta | Contenido |
| --- | --- |
| `datos/` | `nodos.csv` (bodega + 12 clientes), `parametros.csv`, `rutas_actuales.csv` (línea base) |
| `julia/` | `vrpd.jl` (modelo JuMP + HiGHS), `experimentos.jl` (alternativas, casos extremos, sensibilidad) |
| `python/` | `vrpd.py` (modelo PuLP, CBC o HiGHS), `experimentos.py` (contraste), `figuras.py` |
| `app/` | `app.py` (aplicación Streamlit), `capturas.js` (capturas con Playwright) |
| `resultados/` | CSV de resultados de Julia y Python, duales condicionados, logs |
| `figuras/` | Figuras del artículo y capturas de la aplicación |

## Cómo ejecutar

### Julia (implementación principal)
```bash
julia -e 'using Pkg; Pkg.add(["JuMP","HiGHS","CSV","DataFrames"])'
julia julia/experimentos.jl datos resultados todo      # o "base" / "sensibilidad"
```
Versiones usadas: Julia 1.13.3, JuMP 1.32.1, HiGHS.jl 1.26.1 (HiGHS 1.15.1), CSV 1.3.0, DataFrames 1.8.2.

### Python (herramienta de contraste)
```bash
pip install -r requirements.txt
python python/experimentos.py CBC datos resultados     # o HIGHS
python python/figuras.py
```
Versiones usadas: Python 3.13, PuLP 2.9.0 (CBC 2.10.3 incluido); el código también funciona con PuLP 4.x, highspy 1.15.1, pandas, matplotlib.

### Aplicación web
```bash
streamlit run app/app.py
```
Se abre en http://localhost:8501. Para publicarla, subir el repositorio a GitHub y desplegarlo en Streamlit Community Cloud.

## Resultados principales (costo por día de despacho, COP)

| Alternativa | Seca | Lluvias |
| --- | --- | --- |
| Plan actual (manual, solo camión) | 854.200 | 1.129.154 (viola jornada) |
| A1 Solo camión optimizado | 840.716 | 1.352.926 (3 camiones) |
| A2 Camión + dron 5 kg | **839.008** | **1.061.604** |
| A3 Camión + dron 10 kg | 840.716 | 1.069.333 |
| A4 Solo camión, flota 2 | 840.716 | Infactible |
| A5 Camión + dron, flota 2 | 839.008 | 1.061.604 |

Julia (HiGHS) y Python (CBC) obtienen el mismo óptimo en las 10 corridas.
