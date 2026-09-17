"""Tarea: componer una pista con ElevenLabs Music (para un proyecto o para la
biblioteca de música de los music videos).

    python -X utf8 -u -m h3pipeline.app.componer <carpeta>/musica-pedido.json [--solo-prompt]

El pedido trae duración total, género, descripción libre y, si lleva letra, la
letra con su idioma y tipo de voz. De ahí sale UN prompt en inglés para
ElevenLabs Music:

- instrumental loopeable (lo de siempre para los music videos): sin intro, sin
  final, textura constante para que el loop de video se repita encima;
- instrumental con forma (intro, desarrollo, final), si se desmarca «loopeable»;
- canción con letra: se pasa la letra literal y se pide que se cante entera,
  con `force_instrumental=False`.

ElevenLabs compone como mucho 5 minutos por pieza. Una pista más larga (hasta
30 min) se arma con varias piezas del mismo pedido, cada una con **fundido a
silencio al final y desde silencio al principio** (pedido del usuario, 17/9:
piezas empalmadas pero con degradé a 0 entre una y otra, nunca un corte). Las
piezas quedan en `musica-partes/` y la pista final al lado del pedido.
"""
import json
import math
import subprocess
import sys
import time
from pathlib import Path

from .. import config, montaje, musica

MAX_PIEZA = 300.0        # s por llamada a ElevenLabs Music
FUNDIDO_IN = 2.0         # s desde silencio al empezar cada pieza
FUNDIDO_OUT = 4.0        # s a silencio al terminar cada pieza

PROMPT_LOOP = (
    "Instrumental music for a looping ambient video, {dur:.0f} seconds. {tipo} "
    "It must be seamlessly loopable: no intro, no build-up, no ending, no fade; "
    "steady texture and steady level from the very first second to the last, so "
    "any 60-second segment sounds complete on its own. No vocals, no lyrics, no "
    "risers, no stingers, no sudden peaks.")

PROMPT_INSTRUMENTAL = (
    "Instrumental music, {dur:.0f} seconds. {tipo} "
    "A complete piece with a natural shape: a short intro, development and a clean "
    "ending. No vocals, no lyrics.")

PROMPT_CANCION = (
    "A song of {dur:.0f} seconds with sung lyrics. {tipo} "
    "{voz} vocals, lyrics in {idioma}, clearly intelligible and in front of the mix. "
    "Sing exactly these lyrics, in this order, complete, without adding or changing "
    "words; if the song is shorter than the lyrics, keep the order and drop the last "
    "lines rather than rushing:\n\n{letra}\n\n"
    "Natural song structure that fits the lyrics; a clean ending.")

GENEROS = {
    "lofi": "Lo-fi hip hop: dusty drums, warm Rhodes or piano, vinyl crackle, laid back.",
    "ambient": "Ambient: slow evolving pads, no drums, spacious, calm.",
    "piano": "Solo piano, intimate, soft dynamics, room reverb.",
    "jazz": "Soft jazz: brushed drums, upright bass, mellow piano or guitar.",
    "chillhop": "Chillhop: relaxed beat, jazzy chords, light bass, warm.",
    "synthwave": "Synthwave: analog synths, steady 80s drums, nostalgic.",
    "downtempo": "Downtempo electronic: slow beat, deep bass, atmospheric.",
    "acustico": "Acoustic folk: fingerpicked guitar, warm and simple.",
    "clasica": "Chamber classical: strings and piano, restrained, elegant.",
    "bossa": "Bossa nova: nylon guitar, soft percussion, gentle swing.",
    "cinematica": "Cinematic score: strings, subtle percussion, slow build, wide.",
    "pop": "Pop: bright, catchy, modern production, clear hook.",
    "rock": "Soft rock: clean electric guitars, steady drums, warm bass.",
    "cumbia": "Cumbia: güiro and congas groove, accordion or keys, warm and danceable.",
    "reggaeton": "Reggaeton: dembow beat, deep 808 bass, modern urban production.",
    "tango": "Tango: bandoneon, piano, strings, dramatic and rhythmic.",
    "trap": "Trap: 808s, hi-hat rolls, dark and spacious.",
    "infantil": "Children's music: playful, simple melody, bright timbres.",
    "": "",
}
IDIOMAS = {"es": "Spanish", "en": "English", "pt": "Portuguese", "it": "Italian", "fr": "French"}
VOCES = {"femenina": "Female", "masculina": "Male", "duo": "Male and female duet", "coro": "Choir"}


# ───────────────────────────────────────────────────────────── el prompt

def _tipo(m: dict) -> str:
    desc = (m.get("tipo") or "").strip().rstrip(".")
    partes = [GENEROS.get(m.get("genero", ""), ""), f"Mood and details: {desc}." if desc else ""]
    return " ".join(p for p in partes if p).strip()


def armar_prompt(m: dict, dur: float, letra: str | None = None) -> tuple[str, bool | None]:
    """(prompt, instrumental) para UNA pieza de `dur` segundos."""
    tipo = _tipo(m)
    if m.get("con_letra") and (letra if letra is not None else m.get("letra") or "").strip():
        p = PROMPT_CANCION.format(dur=dur, tipo=tipo, letra=(letra if letra is not None else m["letra"]).strip(),
                                  idioma=IDIOMAS.get(m.get("idioma_letra", "es"), "Spanish"),
                                  voz=VOCES.get(m.get("voz_letra", "femenina"), "Female"))
        return p, False
    if m.get("loopeable", True):
        return PROMPT_LOOP.format(dur=dur, tipo=tipo), True
    return PROMPT_INSTRUMENTAL.format(dur=dur, tipo=tipo), True


# ───────────────────────────────────────────────────────────── las piezas

def plan(m: dict) -> list[dict]:
    """Las piezas: cuántas, de cuánto y con qué letra cada una. Una pista de
    hasta 5 min es una pieza; 30 min son 6 piezas de 5. La letra se reparte por
    bloques (estrofas separadas por línea en blanco) entre las piezas."""
    total = float(m["duracion"])
    n = max(1, math.ceil(total / MAX_PIEZA))
    dur = round(total / n, 1)
    letra = (m.get("letra") or "").strip() if m.get("con_letra") else ""
    bloques = [b.strip() for b in letra.split("\n\n") if b.strip()] if letra else []
    piezas = []
    for i in range(n):
        li = None
        if bloques:
            if n == 1:
                li = letra
            elif len(bloques) < n:
                li = letra                      # menos estrofas que piezas: cada pieza canta la letra entera
            else:
                # estrofas consecutivas, en tandas parejas: la pieza 1 canta las
                # primeras, la última las últimas (la canción avanza en orden).
                a, b = round(i * len(bloques) / n), round((i + 1) * len(bloques) / n)
                li = "\n\n".join(bloques[a:b])
        piezas.append({"i": i + 1, "dur": dur, "letra": li})
    return piezas


def _ffmpeg(*args: str) -> None:
    r = subprocess.run([config.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", *args],
                       capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"ffmpeg: {r.stderr.strip()[-400:]}")


def unir(partes: list[Path], destino: Path, fin: float = FUNDIDO_OUT, ini: float = FUNDIDO_IN) -> Path:
    """Cada pieza con fundido desde silencio al principio y a silencio al
    final, y todas seguidas en un solo MP3. Entre una y otra la música llega
    a 0 y vuelve a subir: transición limpia, sin choque de tonalidades."""
    tmp = destino.parent / "musica-partes" / "_fundidas"
    tmp.mkdir(parents=True, exist_ok=True)
    fundidas = []
    for i, p in enumerate(partes, 1):
        d = montaje.duracion(p)
        f = tmp / f"{i:02d}.wav"
        _ffmpeg("-i", str(p), "-af", f"afade=t=in:st=0:d={ini},afade=t=out:st={max(0.0, d - fin):.3f}:d={fin}",
                "-ar", "44100", "-ac", "2", str(f))
        fundidas.append(f)
    lista = tmp / "lista.txt"
    lista.write_text("".join(f"file '{f.as_posix()}'\n" for f in fundidas), encoding="utf-8")
    _ffmpeg("-f", "concat", "-safe", "0", "-i", str(lista), "-c:a", "libmp3lame", "-b:a", "192k", str(destino))
    for f in fundidas:
        f.unlink(missing_ok=True)
    lista.unlink(missing_ok=True)
    return destino


def main() -> int:
    ruta = Path(sys.argv[1])
    m = json.loads(ruta.read_text(encoding="utf-8"))
    c = ruta.parent
    piezas = plan(m)
    if "--solo-prompt" in sys.argv:
        for pz in piezas:
            prompt, instrumental = armar_prompt(m, pz["dur"], pz["letra"])
            print(f"=== pieza {pz['i']}/{len(piezas)} · {pz['dur']:.0f} s · instrumental={instrumental}\n{prompt}\n")
        return 0
    total = float(m["duracion"])
    sello = time.strftime("%H%M")
    destino = c / f"{m['nombre']}-{int(total)}s-{sello}.mp3"
    print(f"componiendo {total / 60:.1f} min en {len(piezas)} pieza(s) de {piezas[0]['dur']:.0f} s · "
          f"{'con letra' if m.get('con_letra') else 'instrumental'}{' loopeable' if m.get('loopeable', True) and not m.get('con_letra') else ''}")
    partes = []
    for pz in piezas:
        prompt, instrumental = armar_prompt(m, pz["dur"], pz["letra"])
        if pz["i"] == 1:
            print("prompt: " + prompt[:160].replace("\n", " ") + ("…" if len(prompt) > 160 else ""))
        if len(piezas) == 1:
            destino.write_bytes(musica.componer(pz["dur"], "", prompt=prompt, instrumental=instrumental))
            partes.append(destino)
        else:
            (c / "musica-partes").mkdir(exist_ok=True)
            f = c / "musica-partes" / f"{m['nombre']}-{sello}-{pz['i']:02d}.mp3"
            t0 = time.time()
            f.write_bytes(musica.componer(pz["dur"], "", prompt=prompt, instrumental=instrumental))
            print(f"  pieza {pz['i']}/{len(piezas)}: {f.stat().st_size / 1024:.0f} KB en {time.time() - t0:.0f} s", flush=True)
            partes.append(f)
    if len(partes) > 1:
        print(f"uniendo {len(partes)} piezas con fundido a silencio de {FUNDIDO_OUT:.0f} s y desde silencio de {FUNDIDO_IN:.0f} s…")
        unir(partes, destino)
    dur = montaje.duracion(destino)
    (c / (destino.stem + ".json")).write_text(json.dumps({**m, "piezas": len(partes), "duracion_real": round(dur, 1)},
                                                          ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{destino.name}  {destino.stat().st_size / 1024:.0f} KB · {dur / 60:.1f} min")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
