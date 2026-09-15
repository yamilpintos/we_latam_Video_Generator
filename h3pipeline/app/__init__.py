"""La Fábrica: la web que corre el pipeline.

    python -X utf8 -u -m h3pipeline.app          # http://127.0.0.1:8787

Una sola aplicación (FastAPI) sirve la página y ejecuta el módulo. No hay base
de datos: cada proyecto es su carpeta en `mis-videos/`, como siempre. Todo lo
que tarda (dibujos, alquiler, corrida, bajada, máster) corre como una tarea en
segundo plano con su log, y la página la sigue.
"""
