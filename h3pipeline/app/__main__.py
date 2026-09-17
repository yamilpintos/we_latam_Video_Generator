"""python -X utf8 -u -m h3pipeline.app [puerto]

Local: escucha en 127.0.0.1:8787. En un servidor (Render, el Teramont):
FABRICA_HOST=0.0.0.0 y PORT los pone el host; FABRICA_PASSWORD protege todo.
"""
import os
import sys

import uvicorn


def main() -> int:
    puerto = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", "8787"))
    host = os.environ.get("FABRICA_HOST", "127.0.0.1")
    print(f"La Fábrica · http://{host}:{puerto}   (Ctrl+C para cerrar)")
    if host != "127.0.0.1" and not os.environ.get("FABRICA_PASSWORD"):
        print("!! escuchando fuera de localhost SIN contraseña: definí FABRICA_PASSWORD")
    uvicorn.run("h3pipeline.app.server:app", host=host, port=puerto, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
