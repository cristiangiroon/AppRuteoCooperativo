# RutaDron Cauca

Aplicación Streamlit de apoyo a la decisión para planear entregas de medicamentos con camiones y drones. La empresa y los datos incluidos son ficticios.

## Estructura

```text
.
├── app.py
├── datos/
│   ├── nodos.csv
│   ├── parametros.csv
│   └── rutas_actuales.csv
├── python/
│   └── vrpd.py
└── requirements.txt
```

Mantén estos archivos y carpetas en la raíz del repositorio: la aplicación carga `datos/` y `python/` usando rutas relativas a `app.py`.

## Ejecutar localmente

Desde esta carpeta, instala las dependencias e inicia la aplicación:

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Publicar en Streamlit Community Cloud

1. Sube esta carpeta como raíz de un repositorio en GitHub. No selecciones la carpeta superior `vrpd_cauca`.
2. En Streamlit Community Cloud, conecta ese repositorio y la rama que quieres publicar.
3. Usa `app.py` como **Main file path**.
4. Despliega y comprueba la carga de los datos y una optimización.

`requirements.txt` debe permanecer en la raíz para que Streamlit instale las dependencias.

## Consideraciones

- Los datos de ejemplo son ficticios; no subas información personal, clínica o confidencial.
- Los escenarios guardados se mantienen en la sesión actual y no constituyen almacenamiento permanente.
- Una optimización puede tardar varios minutos; valida los límites de tiempo con los recursos del despliegue.
