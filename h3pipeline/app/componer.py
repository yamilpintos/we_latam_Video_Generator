"""Tarea: componer una pista con ElevenLabs Music para un proyecto.

    python -X utf8 -u -m h3pipeline.app.componer mis-videos/<slug>/musica-pedido.json

El prompt describe el papel de la música, no el género a secas, y pide que sea
loopeable: sin intro, sin final, textura constante desde el primer segundo.
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


def main() -> int:
    ruta = Path(sys.argv[1])
    m = json.loads(ruta.read_text(encoding="utf-8"))
    c = ruta.parent
    destino = c / f"{m['nombre']}-{int(m['duracion'])}s-{time.strftime('%H%M')}.mp3"
    prompt = PROMPT_LOOP.format(dur=m["duracion"], tipo=m["tipo"].strip())
    print(f"componiendo {m['duracion']:.0f} s: {m['tipo'][:80]}")
    destino.write_bytes(musica.componer(m["duracion"], "", prompt=prompt))
    print(f"{destino.name}  {destino.stat().st_size / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
