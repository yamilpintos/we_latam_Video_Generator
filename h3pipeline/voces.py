"""EL BANCO DE VOCES: presets de timbre para Ref2VA (pedido del usuario, 21/9/2026).

H3 no recuerda voces entre clips: en el capítulo 11 de «El mono monky» (45 s,
tres tomas) el mono cambió de voz en la tercera toma. La solución oficial es
Ref2VA con una voz de referencia (`<Audio 1>`, 2-15 s, 32 kHz estéreo, largo
múltiplo de 800 muestras; ver `voz_ref.py`). Este módulo guarda esas voces como
presets, «como los de ElevenLabs»: cada una con id, nombre, género y una
descripción, y las asigna a los personajes de una serie al azar según el
género. Una vez asignada, el personaje la conserva toda la serie
(`personaje.voz_id` en serie.json).

Dos carpetas, mezcladas:
  - `h3pipeline/voces/` (en el repo): el banco de fábrica, viaja con el código
    a Render. `voces.json` + un WAV por voz.
  - `mis-videos/_voces/` (disco): las que se extraen desde la web de un clip
    ya generado («sacar la voz de este clip»).

    python -m h3pipeline.voces listar
    python -m h3pipeline.voces extraer <clip.mp4> <ini> <fin> <id> <m|f> "<nombre>" "<descripción>"
"""
from __future__ import annotations

import json
import random
import shutil
import sys
import time
import wave
from pathlib import Path

AQUI = Path(__file__).resolve().parent
FABRICA = AQUI / "voces"                             # en el repo
DISCO = AQUI.parent / "mis-videos" / "_voces"        # disco persistente
GENEROS = {"m": "masculina", "f": "femenina", "n": "neutra"}


def _leer(carpeta: Path) -> list[dict]:
    f = carpeta / "voces.json"
    if not f.exists():
        return []
    try:
        lista = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return []
    out = []
    for v in lista:
        w = carpeta / v.get("archivo", f"{v.get('id')}.wav")
        if v.get("id") and w.exists():
            out.append({**v, "archivo": w.name, "ruta": str(w), "origen_carpeta": "repo" if carpeta == FABRICA else "disco"})
    return out


def listar() -> list[dict]:
    """Todas las voces, sin repetir ids (la del disco pisa a la del repo)."""
    por_id: dict[str, dict] = {}
    for v in _leer(FABRICA) + _leer(DISCO):
        por_id[v["id"]] = v
    return sorted(por_id.values(), key=lambda v: (v.get("genero", "n"), v["id"]))


def ver(vid: str | None) -> dict | None:
    if not vid:
        return None
    return next((v for v in listar() if v["id"] == vid), None)


def ruta(vid: str) -> Path:
    v = ver(vid)
    if not v:
        raise KeyError(f"no existe la voz {vid}")
    return Path(v["ruta"])


def resumen() -> dict:
    vs = listar()
    return {"total": len(vs), "m": sum(1 for v in vs if v.get("genero") == "m"),
            "f": sum(1 for v in vs if v.get("genero") == "f"), "n": sum(1 for v in vs if v.get("genero") not in ("m", "f"))}


def elegir(genero: str | None, evitar: list[str] | None = None, semilla: str | None = None) -> str | None:
    """Una voz al azar del género pedido (m|f|n; None = cualquiera). Prefiere las
    que no usa nadie más en la serie (`evitar`); si todas están usadas, repite.
    Devuelve el id o None si el banco está vacío para ese género."""
    vs = listar()
    g = (genero or "").lower()[:1]
    del_genero = [v for v in vs if v.get("genero") == g] if g in ("m", "f") else vs
    if not del_genero:
        del_genero = vs
    if not del_genero:
        return None
    libres = [v for v in del_genero if v["id"] not in set(evitar or [])] or del_genero
    rnd = random.Random(semilla) if semilla else random
    return rnd.choice(libres)["id"]


def _segundos(w: Path) -> float:
    with wave.open(str(w), "rb") as f:
        return f.getnframes() / f.getframerate()


def agregar(vid: str, wav: Path, genero: str, nombre: str = "", descripcion: str = "",
            origen: str = "", carpeta: Path | None = None) -> dict:
    """Guarda un WAV ya recortado (ver `voz_ref.recortar`) como preset."""
    carpeta = carpeta or DISCO
    carpeta.mkdir(parents=True, exist_ok=True)
    wav = Path(wav)
    vid = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in vid.strip().lower()).strip("_")
    if not vid:
        raise ValueError("id vacío")
    destino = carpeta / f"{vid}.wav"
    if wav.resolve() != destino.resolve():
        shutil.copy(wav, destino)
    lista = [v for v in _leer(carpeta) if v["id"] != vid]
    lista = [{k: v[k] for k in ("id", "nombre", "genero", "descripcion", "archivo", "origen", "segundos", "creado") if k in v} for v in lista]
    nuevo = {"id": vid, "nombre": nombre.strip() or vid, "genero": genero.lower()[:1] if genero else "n",
             "descripcion": descripcion.strip(), "archivo": destino.name, "origen": origen,
             "segundos": round(_segundos(destino), 2), "creado": time.time()}
    lista.append(nuevo)
    (carpeta / "voces.json").write_text(json.dumps(lista, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return nuevo


def extraer(clip: Path, ini: float, fin: float, vid: str, genero: str, nombre: str = "",
            descripcion: str = "", carpeta: Path | None = None) -> dict:
    """De un clip generado por H3 (mp4) al banco: recorta con voz_ref y guarda."""
    from . import voz_ref
    carpeta = carpeta or DISCO
    carpeta.mkdir(parents=True, exist_ok=True)
    tmp = carpeta / f"_{vid}.tmp.wav"
    voz_ref.recortar(Path(clip), float(ini), float(fin), tmp)
    try:
        return agregar(vid, tmp, genero, nombre, descripcion, origen=f"{Path(clip).name} {ini:.2f}-{fin:.2f}", carpeta=carpeta)
    finally:
        tmp.unlink(missing_ok=True)


def quitar(vid: str) -> bool:
    hecho = False
    for carpeta in (DISCO, FABRICA):
        lista = _leer(carpeta)
        if any(v["id"] == vid for v in lista):
            (carpeta / f"{vid}.wav").unlink(missing_ok=True)
            resto = [{k: v[k] for k in ("id", "nombre", "genero", "descripcion", "archivo", "origen", "segundos", "creado") if k in v} for v in lista if v["id"] != vid]
            (carpeta / "voces.json").write_text(json.dumps(resto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            hecho = True
    return hecho


def main(argv=None) -> int:
    a = list(argv if argv is not None else sys.argv[1:])
    if not a or a[0] == "listar":
        for v in listar():
            print(f"{v['id']:24} {GENEROS.get(v.get('genero'), '?'):10} {v.get('segundos', 0):5.1f} s  {v.get('nombre', '')} · {v.get('descripcion', '')[:70]}  [{v['origen_carpeta']}]")
        r = resumen()
        print(f"{r['total']} voces · {r['m']} masculinas · {r['f']} femeninas")
        return 0
    if a[0] == "extraer" and len(a) >= 6:
        v = extraer(Path(a[1]), float(a[2]), float(a[3]), a[4], a[5], a[6] if len(a) > 6 else "", a[7] if len(a) > 7 else "")
        print(f"{v['id']}: {v['segundos']} s → {DISCO / v['archivo']}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
