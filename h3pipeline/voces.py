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
    python -m h3pipeline.voces llenar-elevenlabs        # los 20 presets de abajo (~4.000 caracteres)

SIN CASTING (21/9, pedido del usuario: «propone las voces vos, no es necesario
casting»): la referencia de timbre no tiene por qué salir de H3. Cada preset de
`ELEVEN` es una voz de la cuenta de ElevenLabs que lee una frase de ~10 s; ese
audio, recortado con `voz_ref`, es el `<Audio 1>` de Ref2VA. Cuesta caracteres
de ElevenLabs, no GPU, y el narrador de una serie (Pablo) puede ser también la
voz de su protagonista cuando narra en primera persona.
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
EDADES = ("joven", "adulto", "mayor")

# id, nombre, género, edad, voice_id de ElevenLabs, descripción (en inglés, va
# al prompt). Elegidas de las 611 voces de la cuenta el 21/9: castellano, con
# acento rioplatense donde lo hay, repartidas por edad.
ELEVEN = [
    ("m01_tomas_ar", "Tomás (rioplatense)", "m", "joven", "QK4xDwo9ESPHA4JNUpX3", "young Argentine man, Rioplatense accent, natural and direct"),
    ("m02_franco_ar", "Franco (argentino)", "m", "joven", "JNcXxzrlvFDXcrGo2b47", "young Argentine man, warm and natural"),
    ("m03_agus_ar", "Agus (argentino, rápido)", "m", "joven", "vgekQLm3GYiKMHUnPVvY", "young Argentine man, fast-talking, witty"),
    ("m04_pablo_ar", "Pablo (cordobés, el narrador)", "m", "adulto", "JXKQ929SO0LLl7spbEAI", "Argentine man from Córdoba, middle-aged, calm storyteller"),
    ("m05_alonso", "Alonso (grave, pausado)", "m", "joven", "HMMu0XoIm7ib2e6V02E3", "Latin American man, slightly deep, calm and methodical"),
    ("m06_carlos", "Carlos (documental)", "m", "adulto", "8MeTTgXVwMEhRVfblXOj", "Latin American man, adult, casual documentary tone"),
    ("m07_edoardo", "Edoardo (oscuro, contenido)", "m", "adulto", "YqZLNYWZm98oKaaLZkUA", "Latin American man, deep, restrained, dramatic"),
    ("m08_faraon", "Faraón (mayor, autoritario)", "m", "mayor", "Rl2JPHsuEWSfwCD4ZHIQ", "older Latin American man, deep, powerful, authoritative"),
    ("m09_salvatore", "Salvatore (mayor, cálido)", "m", "mayor", "wfTWLJ20rcMqvU8gIiAB", "older Latin American man, warm, deep, approachable"),
    ("m10_abuelo", "Abuelo Charlie (anciano)", "m", "mayor", "Yb8JGzcZyW5YYzenhRCm", "elderly Latin American man, warm and calm"),
    ("f01_malena_ar", "Malena (rioplatense)", "f", "joven", "p7AwDmKvTdoHTBuueGvP", "young Argentine woman, Rioplatense accent, dynamic"),
    ("f02_sofi_ar", "Sofi (argentina)", "f", "joven", "vqoh9orw2tmOS3mY7D2p", "young Argentine woman, bright storyteller"),
    ("f03_gaby", "Gaby (dulce, tímida)", "f", "joven", "n4GNpJP6Y2Nd09pDtetA", "young Latin American woman, sweet and soft"),
    ("f04_valeria_ar", "Valeria (argentina)", "f", "adulto", "9oPKasc15pfAbMr7N6Gs", "Argentine woman, adult, feminine and clear"),
    ("f05_kate", "Kate (cercana)", "f", "adulto", "EYBbN7OENxAX5QX56IiW", "Latin American woman, adult, close and natural"),
    ("f06_carolina", "Carolina (cálida)", "f", "adulto", "cIBxLwfshLYhRB9lCXEg", "Latin American woman, warm and conversational"),
    ("f07_karolina", "Karolina (grave, resonante)", "f", "adulto", "Wuv1s5YTNCjL9mFJTqo4", "Latin American woman, warm, deep, resonant"),
    ("f08_gabriela", "Gabriela (madura)", "f", "mayor", "hHjbwzYZW17oh0p05AKv", "mature Latin American woman, warm"),
    ("f09_regina", "Regina (mayor, serena)", "f", "mayor", "eBthAb30UYbt2nojGXeA", "older Latin American woman, calm and deep"),
    ("f10_luisa", "Luisa (anciana, narradora)", "f", "mayor", "efcRUax7uSa9kpBwtDPe", "elderly Latin American woman, deep, measured storyteller"),
]
FRASE_MUESTRA = ("Mirá, te lo digo una sola vez. Hace años que conozco este lugar, a esta gente, "
                 "cada rincón. Y te aseguro que nada de lo que pasó fue casualidad. Nada.")


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


def elegir(genero: str | None, evitar: list[str] | None = None, semilla: str | None = None,
           edad: str | None = None) -> str | None:
    """Una voz al azar del género pedido (m|f|n; None = cualquiera). Prefiere las
    que no usa nadie más en la serie (`evitar`); si todas están usadas, repite.
    Devuelve el id o None si el banco está vacío para ese género."""
    vs = listar()
    g = (genero or "").lower()[:1]
    # Sin voz del género pedido NO se cruza (el 21/9 Marta, de 68, quedó con la
    # voz del mono): mejor sin preset, que la describa el texto.
    del_genero = [v for v in vs if v.get("genero") == g] if g in ("m", "f") else vs
    if not del_genero:
        return None
    # Misma franja de edad si la hay (una señora de 68 no con la voz de una chica).
    if edad in EDADES:
        de_edad = [v for v in del_genero if v.get("edad") == edad]
        if de_edad:
            del_genero = de_edad
    libres = [v for v in del_genero if v["id"] not in set(evitar or [])] or del_genero
    rnd = random.Random(semilla) if semilla else random
    return rnd.choice(libres)["id"]


def _segundos(w: Path) -> float:
    with wave.open(str(w), "rb") as f:
        return f.getnframes() / f.getframerate()


CAMPOS = ("id", "nombre", "genero", "edad", "descripcion", "archivo", "origen", "segundos", "creado", "eleven")


def agregar(vid: str, wav: Path, genero: str, nombre: str = "", descripcion: str = "",
            origen: str = "", carpeta: Path | None = None, edad: str | None = None,
            eleven: str | None = None) -> dict:
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
    lista = [{k: v[k] for k in CAMPOS if k in v} for v in lista]
    nuevo = {"id": vid, "nombre": nombre.strip() or vid, "genero": genero.lower()[:1] if genero else "n",
             "descripcion": descripcion.strip(), "archivo": destino.name, "origen": origen,
             "segundos": round(_segundos(destino), 2), "creado": time.time()}
    if edad in EDADES:
        nuevo["edad"] = edad
    if eleven:
        nuevo["eleven"] = eleven
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


def desde_elevenlabs(vid: str, voice_id: str, genero: str, nombre: str, descripcion: str = "",
                     edad: str | None = None, texto: str = FRASE_MUESTRA, carpeta: Path | None = None) -> dict:
    """Una voz de ElevenLabs al banco: lee `texto` (~10 s), se recorta a la norma
    de Ref2VA (32 kHz estéreo, múltiplo de 800 muestras, 2-15 s) y se guarda."""
    import tempfile
    from . import tts, voz_ref
    carpeta = carpeta or DISCO
    carpeta.mkdir(parents=True, exist_ok=True)
    mp3 = Path(tempfile.mkdtemp(prefix="h3voz_")) / "m.mp3"
    mp3.write_bytes(tts.sintetizar(texto, voice_id))
    dur = min(15.0, max(2.0, tts.duracion_util(mp3) + 0.3))
    tmp = carpeta / f"_{vid}.tmp.wav"
    try:
        voz_ref.recortar(mp3, 0.0, dur, tmp)
        return agregar(vid, tmp, genero, nombre, descripcion, origen=f"ElevenLabs {voice_id}", carpeta=carpeta,
                       edad=edad, eleven=voice_id)
    finally:
        tmp.unlink(missing_ok=True)
        try:
            mp3.unlink()
            mp3.parent.rmdir()
        except OSError:
            pass


def llenar_elevenlabs(carpeta: Path | None = None, log=print) -> int:
    """Los presets de `ELEVEN` que falten, al banco de fábrica (van al repo)."""
    carpeta = carpeta or FABRICA
    ya = {v["id"] for v in _leer(carpeta)}
    n = 0
    for vid, nombre, g, edad, eleven, desc in ELEVEN:
        if vid in ya:
            continue
        try:
            v = desde_elevenlabs(vid, eleven, g, nombre, desc, edad=edad, carpeta=carpeta)
            log(f"  {vid}: {v['segundos']} s")
            n += 1
        except Exception as e:
            log(f"  {vid}: no pude ({str(e)[:120]})")
    return n


def quitar(vid: str) -> bool:
    hecho = False
    for carpeta in (DISCO, FABRICA):
        lista = _leer(carpeta)
        if any(v["id"] == vid for v in lista):
            (carpeta / f"{vid}.wav").unlink(missing_ok=True)
            resto = [{k: v[k] for k in CAMPOS if k in v} for v in lista if v["id"] != vid]
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
    if a[0] == "llenar-elevenlabs":
        print(f"{llenar_elevenlabs()} voces nuevas en {FABRICA}")
        return 0
    if a[0] == "extraer" and len(a) >= 6:
        v = extraer(Path(a[1]), float(a[2]), float(a[3]), a[4], a[5], a[6] if len(a) > 6 else "", a[7] if len(a) > 7 else "")
        print(f"{v['id']}: {v['segundos']} s → {DISCO / v['archivo']}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
