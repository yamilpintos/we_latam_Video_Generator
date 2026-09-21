"""Baja los másters de una serie desde La Fábrica en Render a una carpeta prolija
de esta PC.

    python -X utf8 -u -m h3pipeline.app.bajar_serie https://<tu-app>.onrender.com el-mono-monky "C:\\Users\\Yamil\\Desktop\\El mono monky"

Usa el usuario y la contraseña de RENDER-VARIABLES.txt (HTTP Basic, que la app
acepta para scripts). Nombra cada archivo «NN - TÍTULO.mp4» y trae también el
.srt si existe. Lo que ya está bajado con el mismo tamaño no se vuelve a bajar.
"""
from __future__ import annotations

import base64
import json
import re
import sys
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def credenciales() -> tuple[str, str]:
    t = (RAIZ / "RENDER-VARIABLES.txt").read_text(encoding="utf-8")
    def valor(clave: str) -> str:
        m = re.search(rf"KEY:\s*{clave}\s*\nVALUE:\s*\n(.+)", t)
        return m.group(1).strip() if m else ""
    return valor("FABRICA_USUARIO") or "fabrica", valor("FABRICA_PASSWORD")


def pedir(base: str, ruta: str, auth: str) -> bytes:
    req = urllib.request.Request(base + ruta, headers={"Authorization": auth})
    with urllib.request.urlopen(req, timeout=600) as r:
        return r.read()


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    base, slug = sys.argv[1].rstrip("/"), sys.argv[2]
    destino = Path(sys.argv[3]) if len(sys.argv) > 3 else Path.home() / "Desktop" / slug
    destino.mkdir(parents=True, exist_ok=True)
    u, c = credenciales()
    auth = "Basic " + base64.b64encode(f"{u}:{c}".encode()).decode()
    serie = json.loads(pedir(base, f"/api/series/{slug}", auth))
    print(f"serie «{serie['titulo']}»: {len(serie['capitulos'])} capítulos → {destino}")
    bajados = 0
    for cap in sorted(serie["capitulos"], key=lambda x: x["n"]):
        if not cap.get("slug"):
            continue
        try:
            est = json.loads(pedir(base, f"/api/proyectos/{cap['slug']}", auth)).get("estado", {})
        except Exception as e:
            print(f"  {cap['n']:02d} {cap['titulo']}: el proyecto no responde ({str(e)[:60]}); lo salteo")
            continue
        masters = [m for m in est.get("masters", []) if m.lower().endswith(".mp4")]
        if not masters:
            print(f"  {cap['n']:02d} {cap['titulo']}: sin máster todavía")
            continue
        titulo = re.sub(r'[\\/:*?"<>|]+', " ", cap["titulo"]).strip()
        for m in masters[:1]:
            local = destino / f"{cap['n']:02d} - {titulo}.mp4"
            datos = pedir(base, f"/api/proyectos/{cap['slug']}/archivo/{urllib.request.quote(m)}", auth)
            local.write_bytes(datos)
            bajados += 1
            print(f"  {cap['n']:02d} {titulo}: {local.name} ({len(datos) / 1e6:.1f} MB)")
            srt = Path(m).with_suffix(".srt").name
            try:
                (destino / f"{cap['n']:02d} - {titulo}.srt").write_bytes(pedir(base, f"/api/proyectos/{cap['slug']}/archivo/{urllib.request.quote(srt)}", auth))
            except Exception:
                pass
    print(f"{bajados} máster(s) en {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
