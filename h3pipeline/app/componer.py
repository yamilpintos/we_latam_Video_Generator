"""Tarea: componer una pista con ElevenLabs Music para un proyecto.

    python -X utf8 -u -m h3pipeline.app.componer mis-videos/<slug>/musica-pedido.json [--solo-prompt]

El pedido (musica-pedido.json) trae duración, género, descripción libre y, si
la pista lleva letra, la letra con su idioma y tipo de voz. De ahí sale UN
prompt en inglés para ElevenLabs Music:

- instrumental loopeable (lo de siempre para los music videos): sin intro, sin
  final, textura constante para que el loop de video se repita encima;
- instrumental con forma (intro, desarrollo, final), si se desmarca «loopeable»;
- canción con letra: se pasa la letra literal y se pide que se cante entera,
  con `force_instrumental=False`.
"""
import json
import sys
import time
from pathlib import Path

from .. import musica

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


def armar_prompt(m: dict) -> tuple[str, bool | None]:
    """(prompt, instrumental) a partir del pedido."""
    desc = (m.get("tipo") or "").strip().rstrip(".")
    partes = [GENEROS.get(m.get("genero", ""), ""), f"Mood and details: {desc}." if desc else ""]
    tipo = " ".join(p for p in partes if p).strip()
    dur = float(m["duracion"])
    if m.get("con_letra") and (m.get("letra") or "").strip():
        p = PROMPT_CANCION.format(dur=dur, tipo=tipo, letra=m["letra"].strip(),
                                  idioma=IDIOMAS.get(m.get("idioma_letra", "es"), "Spanish"),
                                  voz=VOCES.get(m.get("voz_letra", "femenina"), "Female"))
        return p, False
    if m.get("loopeable", True):
        return PROMPT_LOOP.format(dur=dur, tipo=tipo), True
    return PROMPT_INSTRUMENTAL.format(dur=dur, tipo=tipo), True


def main() -> int:
    ruta = Path(sys.argv[1])
    m = json.loads(ruta.read_text(encoding="utf-8"))
    c = ruta.parent
    prompt, instrumental = armar_prompt(m)
    if "--solo-prompt" in sys.argv:
        print(prompt)
        print(f"\n[instrumental={instrumental}]")
        return 0
    destino = c / f"{m['nombre']}-{int(m['duracion'])}s-{time.strftime('%H%M')}.mp3"
    print(f"componiendo {m['duracion']:.0f} s · {'con letra' if instrumental is False else 'instrumental'}"
          f"{' loopeable' if instrumental and m.get('loopeable', True) else ''}")
    print("prompt: " + prompt[:160].replace("\n", " ") + ("…" if len(prompt) > 160 else ""))
    destino.write_bytes(musica.componer(m["duracion"], "", prompt=prompt, instrumental=instrumental))
    (c / (destino.stem + ".json")).write_text(json.dumps({**m, "prompt": prompt}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{destino.name}  {destino.stat().st_size / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
