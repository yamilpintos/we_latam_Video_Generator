"""CASTING PARA EL BANCO DE VOCES: 10 voces femeninas + 10 masculinas de H3.

Pedido del usuario (21/9/2026): presets de voz «como los de ElevenLabs», para
asignarlos al azar a los personajes de una serie y que cada uno conserve la
suya. H3 no recuerda voces: la única forma de tener una voz fija es la voz de
referencia de Ref2VA (`voces.py`), y esas referencias tienen que salir de H3.

Este módulo arma un proyecto normal (`mis-videos/casting-voces/`) con veinte
planos de 7,29 s: en cada uno una persona distinta, de frente, dice una frase
larga en castellano con la voz descripta en el prompt. Se produce como
cualquier proyecto (dibujos → ZIP → cola → máquina), y al bajar los clips,
`cosechar` recorta el tramo hablado de cada uno y lo guarda en el banco de
fábrica (`h3pipeline/voces/`, viaja con el repo).

    python -m h3pipeline.casting_voces armar            # proyecto.json
    python -m h3pipeline frames mis-videos/casting-voces/proyecto.json --motor openai
    python -m h3pipeline empaquetar mis-videos/casting-voces/proyecto.json
    (cola / máquina, como siempre)
    python -m h3pipeline.casting_voces cosechar         # clips → banco

Costo estimado: 20 dibujos (~$1,20) + 20 clips de 7,3 s (~110 min de GPU,
~30 min de pared en 4×5090, ~$1) + instalación (~$0,70). Unos $3.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from . import config, grilla, voces

RAIZ = Path(__file__).resolve().parent.parent
CARPETA = RAIZ / "mis-videos" / "casting-voces"
SEGUNDOS = round(grilla.encajar(7.3)[1], 3)          # 175 fotogramas = 7,29 s

# id, nombre del preset, descripción de la voz (inglés, para el prompt), aspecto
# de la persona (para el dibujo), línea en castellano (~14 palabras, 4-5 s).
FEMENINAS = [
    ("f01_lucia", "Lucía", "young woman in her early 20s, bright clear voice, medium-high pitch, quick and cheerful, neutral Latin American Spanish",
     "a young woman in her early twenties with long dark hair, light freckles, a yellow t-shirt", "Hola a todos, hoy les voy a contar algo que me pasó ayer en el colectivo."),
    ("f02_valentina", "Valentina", "woman around 30, warm and smooth voice, medium pitch, calm and confident pace, Argentine accent",
     "a woman around thirty with wavy chestnut hair, a green blouse, small gold earrings", "Tranquilos, ya revisé todo dos veces y no falta absolutamente nada en la lista."),
    ("f03_martina", "Martina", "woman in her mid 30s, husky low-pitched voice, slow and relaxed, slightly ironic tone, Mexican accent",
     "a woman in her mid thirties with a black bob haircut, red lipstick, a denim jacket", "Mirá, si querés hacerlo así, hacelo, pero después no digas que no te avisé."),
    ("f04_camila", "Camila", "woman in her late 20s, sweet soft voice, high pitch, gentle and a bit shy, Colombian accent",
     "a woman in her late twenties with curly brown hair, round glasses, a lilac sweater", "Perdón, ¿me podrías repetir la dirección? Creo que anoté mal el número de la calle."),
    ("f05_sofia", "Sofía", "woman around 40, clear authoritative newscaster voice, medium pitch, steady rhythm, neutral Spanish",
     "a woman around forty with straight blonde hair pulled back, a navy blazer", "Buenas noches, estas son las noticias más importantes de la jornada de hoy."),
    ("f06_rosa", "Rosa", "woman in her 50s, warm motherly voice, medium-low pitch, unhurried and kind, Peruvian accent",
     "a woman in her fifties with grey-streaked hair in a bun, a floral apron", "Vengan a comer que se enfría, y lávense las manos antes de sentarse, por favor."),
    ("f07_carmen", "Carmen", "elderly woman around 70, thin slightly trembling voice, high pitch, slow with pauses, Spanish from Spain",
     "an elderly woman around seventy with short white hair, a beige cardigan, pearl necklace", "Cuando yo era joven, este barrio era todo campo y no había ni una sola farola."),
    ("f08_julieta", "Julieta", "teenage girl around 17, energetic fast voice, high pitch, excited and playful, Argentine accent",
     "a teenage girl around seventeen with a pink ponytail, braces, an oversized hoodie", "No, no, no, escuchame, esto es lo más increíble que vas a ver en tu vida."),
    ("f09_ana", "Ana", "woman in her mid 40s, deep velvety radio voice, low pitch, slow and seductive, Venezuelan accent",
     "a woman in her mid forties with long black hair, a dark red dress, a headset microphone", "Son las once de la noche y esta canción va dedicada a todos los que no pueden dormir."),
    ("f10_paula", "Paula", "woman around 35, nasal comic voice, medium-high pitch, fast and expressive, Chilean accent",
     "a woman around thirty-five with short red hair, big hoop earrings, a striped shirt", "¿Y ahora qué hacemos con todo esto? Porque yo no pienso cargarlo de vuelta."),
]
MASCULINAS = [
    ("m01_mateo", "Mateo", "young man in his early 20s, light clear voice, medium-high pitch, quick and friendly, neutral Latin American Spanish",
     "a young man in his early twenties with short curly hair, a grey t-shirt", "Che, ¿vieron dónde dejé las llaves? Las tenía hace un minuto en la mano."),
    ("m02_santiago", "Santiago", "man around 30, warm baritone, medium pitch, confident and relaxed, Argentine accent",
     "a man around thirty with a trimmed beard, a white shirt with rolled sleeves", "Quedate tranquilo, lo hablamos mañana con calma y lo resolvemos entre los dos."),
    ("m03_diego", "Diego", "man in his mid 30s, deep gravelly voice, low pitch, slow and serious, Mexican accent",
     "a man in his mid thirties with a shaved head, a black leather jacket", "Escúchame bien, porque no lo voy a repetir: esta noche nadie sale de aquí."),
    ("m04_tomas", "Tomás", "man in his late 20s, nasal nerdy voice, medium-high pitch, fast and precise, Colombian accent",
     "a man in his late twenties with thick glasses, a plaid shirt buttoned to the top", "Técnicamente eso no es un error, es una característica que nadie documentó todavía."),
    ("m05_alejandro", "Alejandro", "man around 45, authoritative newscaster voice, medium-low pitch, steady and clear, neutral Spanish",
     "a man around forty-five with grey temples, a dark suit and blue tie", "Buenas tardes, comenzamos esta edición con una noticia de último momento."),
    ("m06_ricardo", "Ricardo", "man in his 50s, rough smoker's voice, low pitch, tired and gruff, Uruguayan accent",
     "a man in his fifties with a weathered face, a wool cap, a worn brown jacket", "Hace treinta años que trabajo en esto y nunca vi una cosa igual, te lo juro."),
    ("m07_ernesto", "Ernesto", "elderly man around 75, thin raspy voice, medium pitch, slow with long pauses, Spanish from Spain",
     "an elderly man around seventy-five with white hair, a moustache, a tweed vest", "Siéntate, hijo, que te voy a contar cómo conocí a tu abuela en el pueblo."),
    ("m08_lucas", "Lucas", "teenage boy around 16, cracking adolescent voice, medium-high pitch, fast and excited, Argentine accent",
     "a teenage boy around sixteen with messy hair, a football jersey", "Bro, no sabés lo que pasó en el partido, fue una locura total, en serio."),
    ("m09_gabriel", "Gabriel", "man around 40, smooth deep radio voice, very low pitch, slow and warm, Venezuelan accent",
     "a man around forty with slicked-back dark hair, a burgundy sweater, a studio microphone", "Gracias por acompañarnos una noche más; quédense, que lo mejor todavía no empezó."),
    ("m10_fede", "Fede", "man around 35, high-pitched comic voice, fast and whiny, exaggerated, Chilean accent",
     "a man around thirty-five with a goatee, a bright orange shirt, a backwards cap", "¡No, por favor, otra vez no! Yo ya pagué la última, ahora te toca a ti."),
]

ESTILO = ("Photorealistic portrait, shot on a full-frame camera with an 85 mm lens, soft window light, neutral plain "
          "background, natural skin texture, no text, no logos.")


def armar() -> Path:
    planos, personajes = [], {}
    for genero, lista in (("f", FEMENINAS), ("m", MASCULINAS)):
        for vid, nombre, voz, aspecto, linea in lista:
            pid = vid
            personajes[pid] = {"hoja": f"m_{pid}", "descripcion": f"{nombre}, {aspecto}."}
            planos.append({
                "id": f"C{len(planos) + 1:02d}", "tipo": "PM", "segundos": SEGUNDOS, "loc": None, "personajes": [pid],
                "refs": [], "texto": "",
                "ve": f"MEDIUM CLOSE-UP, vertical 9:16, {nombre}, {aspecto}, facing the camera directly, eyes on the lens, "
                      f"mouth closed, relaxed neutral expression, centered, plain neutral background, soft window light.",
                "mueve": f"{nombre} looks at the camera and speaks one sentence naturally, with small head movements and natural blinking, "
                         f"then stays quiet looking at the camera.",
                "camara": "static shot throughout",
                "audio": "Quiet room tone; the small sounds of breathing and clothes.",
                "dialogo": f"{nombre}: {linea}", "habla": pid, "off": False,
                "voz_desc": voz, "casting": {"id": vid, "nombre": nombre, "genero": genero, "voz": voz},
            })
    d = {"titulo": "CASTING DE VOCES", "slug": "casting-voces", "formato": "short", "estructura": "short-15",
         "_concepto": "Veinte personas distintas, de frente, dicen una frase larga: de cada clip sale una voz de referencia para el banco.",
         "estilo_imagen": ESTILO, "estilo_video": "Photorealistic, natural motion.", "cierre_video": "",
         "medio": "photographic", "solo_sonidos": "Quiet room tone.", "negativos": True, "idioma": "es",
         "personajes": personajes, "locaciones": {}, "madre": [], "voces": {}, "voz": [], "planos": planos}
    CARPETA.mkdir(parents=True, exist_ok=True)
    (CARPETA / "proyecto.json").write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return CARPETA / "proyecto.json"


def _habla(clip: Path) -> tuple[float, float] | None:
    """Ventana [primer sonido, último sonido] del clip por silencedetect."""
    r = subprocess.run([config.ffmpeg(), "-hide_banner", "-i", str(clip), "-af", "silencedetect=n=-32dB:d=0.35", "-f", "null", "-"],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    dur = None
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stdout)
    if m:
        dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    if dur is None:
        return None
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stdout)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stdout)]
    # Sonido = complemento de los silencios.
    ini = ends[0] if starts and starts[0] < 0.05 and ends else 0.0
    fin = starts[-1] if starts and (not ends or ends[-1] < starts[-1]) else dur
    if fin - ini < 2.0:
        ini, fin = 0.0, dur
    return max(0.0, ini - 0.1), min(dur, fin + 0.2)


def cosechar() -> int:
    d = json.loads((CARPETA / "proyecto.json").read_text(encoding="utf-8"))
    n = 0
    for pl in d["planos"]:
        c = pl.get("casting") or {}
        clip = CARPETA / "clips" / f"{pl['id']}.mp4"
        if not clip.exists():
            print(f"  {pl['id']} {c.get('nombre')}: sin clip")
            continue
        v = _habla(clip)
        if not v:
            print(f"  {pl['id']} {c.get('nombre')}: no pude medir el audio")
            continue
        ini, fin = v
        from .voz_ref import MAXIMO
        fin = min(fin, ini + MAXIMO)
        r = voces.extraer(clip, ini, fin, c["id"], c["genero"], c["nombre"], c["voz"], carpeta=voces.FABRICA)
        print(f"  {pl['id']} {c['nombre']}: {ini:.2f}-{fin:.2f} s → {r['archivo']} ({r['segundos']} s)")
        n += 1
    print(f"{n} voces al banco de fábrica ({voces.FABRICA})")
    return n


def main(argv=None) -> int:
    a = list(argv if argv is not None else sys.argv[1:])
    if a[:1] == ["armar"]:
        print(armar())
        return 0
    if a[:1] == ["cosechar"]:
        return 0 if cosechar() else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
