"""Genera la Mesa de Armado: la página que convierte una idea en el brief que
el modelo transforma en storyboard.

    python -m h3pipeline.web            # escribe h3pipeline/web/mesa.html

Se genera **desde el módulo** y no se escribe a mano: los tramos, los rangos de
corte, los umbrales de retención y el esqueleto de huecos salen de
`estructuras/*.json` en el momento de generar. Si cambiás un tramo en el JSON,
cambia en la página. Una copia escrita a mano se desincroniza en una semana.

La plantilla vive al lado, en `web/plantilla.html`, con un marcador `__DATOS__`.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import grilla, prompts
from .estructura import Estructura, disponibles

AQUI = Path(__file__).resolve().parent / "web"
PLANTILLA = AQUI / "plantilla.html"
SALIDA = AQUI / "mesa.html"

# Presets de estilo. Cada uno trae las tres piezas que el proyecto necesita:
# el prompt del fotograma, la cabecera del prompt de video y su coda.
ESTILOS = [
    {
        "nombre": "Fotorrealista cinematográfico",
        "medio": "live-action film",
        "prompt": ("Photorealistic cinematic footage, shot on a full-frame camera with a fast "
                   "lens. Natural light, high ISO grain, shallow depth of field, restrained "
                   "colour grade."),
        "cabecera": "Photorealistic cinematic footage.",
        "cierre": ("Keep the framing of the first frame. Grainy, photographic. Not animated, "
                   "not illustrated, not CGI-looking."),
    },
    {
        "nombre": "Animación 2D, sombreado plano",
        "medio": "2D animated film",
        "prompt": ("Original 2D animated illustration, clean confident linework, flat cel "
                   "shading, rich ornate detail, a limited and deliberate palette."),
        "cabecera": "2D animated film.",
        "cierre": "Keep the framing of the first frame. Hold the line weight and the palette.",
    },
    {
        "nombre": "Documental de archivo, años 90",
        "medio": "documentary reconstruction",
        "prompt": ("Documentary photography, 1990s reconstruction. 35 mm film emulsion with "
                   "visible grain and soft halation. Muted amber, phosphor-green CRT glow and "
                   "steel blue. Only light from sources visible in frame."),
        "cabecera": "Documentary reconstruction, 35 mm film look.",
        "cierre": ("Keep the framing of the first frame. Hold the grain and the colour cast. "
                   "No on-screen text, no readable signage, no logos."),
    },
    {
        "nombre": "Submarino, agua turbia",
        "medio": "underwater film",
        "prompt": ("Photorealistic cinematic underwater footage, shot on a full-frame camera "
                   "with a fast wide lens. Heavy particulate suspended in the water catching "
                   "the light. Volumetric beams. Deep teal-black water, cold. High ISO grain."),
        "cabecera": "Photorealistic cinematic underwater footage.",
        "cierre": ("Keep the framing of the first frame. Grainy, cold, photographic. Not "
                   "animated, not illustrated, not CGI-looking."),
    },
    {
        "nombre": "Nocturno urbano, neón",
        "medio": "live-action film",
        "prompt": ("Photorealistic night cinematography in a city. Wet asphalt holding "
                   "reflections, sodium and neon practicals as the only light, deep shadows "
                   "with lifted blacks, anamorphic flare, fine grain."),
        "cabecera": "Photorealistic night cinematography.",
        "cierre": ("Keep the framing of the first frame. Hold the practical lighting and the "
                   "lifted blacks. Not animated, not CGI-looking."),
    },
]

# Lo que el módulo inyecta solo en cada prompt. Va en la instrucción para que el
# modelo no lo repita: repetirlo diluye las restricciones que sí importan.
AUTOMATICO = [
    "El bloque de castellano (SPOKEN LANGUAGE: SPANISH), en todos los planos, hablen o no.",
    "El «no inventes»: nada que no esté en el primer fotograma entra al plano.",
    "La regla del humo, sólo en los planos donde aparece humo, polvo o niebla.",
    "La descripción del tamaño de plano en fracciones de la altura del cuadro.",
    "La relación de aspecto y el «esto es un fotograma, no un póster».",
    "La descripción de vestuario de cada personaje que aparece.",
    "El «no hay diálogo» (NO SPEECH) cuando el plano no lleva línea.",
]

REGLAS = [
    "H3 acepta de 5,17 a 15,08 s por plano. Fuera de ahí no está roto: adivina.",
    "El tamaño de plano va en el dibujo Y en el prompt. En uno solo, H3 lo corrige y los "
    "personajes salen gigantes.",
    "No cortes entre dos planos del mismo tamaño, misma locación y misma gente: da un "
    "brinco, no un corte.",
    "Los números que cambian (contadores, marcadores) van como gráfico en post, nunca "
    "pedidos al modelo: destroza el texto en movimiento.",
    "Las caras humanas en primer plano son lo peor que le sale al modelo. Taparlas — "
    "máscara, casco, sombra, de espaldas — o esquivarlas.",
    "Elegí un entorno que perdone: agua turbia, humo, niebla, poca luz. Ahí los artefactos "
    "de generación desaparecen.",
    "Escribí `ve` y `mueve` como dos cosas distintas: uno es una foto, el otro es lo que "
    "pasa después de esa foto.",
]

# Para la línea de costo del panel. Medido en la corrida real del 28/8/2026:
# 0,67 a 0,81 min de GPU por segundo de video, a 8 pasos con turbo.
COSTO = {"min_por_seg": 0.75, "dolar_por_min": 1.909 / 60}

# Lo que rompió la primera corrida real contra Vast. Va en la página porque es
# donde vas a estar cuando pase, no en un .md que nadie relee. El detalle
# completo está en VAST.md.
TRAMPAS = [
    {"t": "La máquina arranca y no se puede entrar",
     "s": "Queda en `running` con todos los puertos cerrados. El proxy SSH acepta la "
          "conexión y la cierra sin saludar.",
     "p": "Se alquiló pasando `image` y un `onstart` propio.",
     "a": "Alquilar con el **template oficial** (`template_hash_id`). Es el que trae "
          "`entrypoint.sh`, que levanta sshd, Jupyter y supervisor. Ya lo hace `alquilar`."},
    {"t": "`kex_exchange_identification: Connection closed`",
     "s": "El SSH cierra antes de pedirte la clave, así que no es un problema de clave.",
     "p": "El proxy de Vast autentica contra las claves de la **cuenta**, y una API key "
          "de team no puede registrarlas.",
     "a": "Entrar por **SSH directo**: la IP pública y el puerto mapeado al 22. Y la "
          "clave se adjunta **a la instancia**, que sí lo permite una key de team."},
    {"t": "`python: command not found` dentro de la máquina",
     "s": "El instalador termina pero la verificación no corre, y `UnetLoaderGGUF` "
          "no aparece.",
     "p": "El intérprete está en `/venv/main/bin/python` y un shell no interactivo no "
          "lo trae en el PATH. El `pip install gguf` fue al Python equivocado.",
     "a": "Anteponer `/venv/main/bin` al PATH. Si el nodo GGUF falta: instalar `gguf` "
          "en ese venv y reiniciar ComfyUI."},
    {"t": "`HTTP 400 · prompt_outputs_failed_validation`",
     "s": "ComfyUI rechaza el workflow entero. En el detalle: un valor fuera de rango, "
          "por ejemplo `denoise: 20` cuando el máximo es 1.",
     "p": "`widgets_values` es posicional. Si un campo pasó a ser cable, los valores "
          "que siguen se corren un lugar.",
     "a": "El runner valida cada valor contra `/object_info` y devuelve al default el "
          "que no entra. Es general, no un parche para ese nodo."},
    {"t": "Uno o dos clips fallan por falta de VRAM",
     "s": "`Allocation would exceed allowed memory`, con ~25 GB de 31,4 ya ocupados.",
     "p": "El GGUF ocupa 23,9 GB y la memoria se fragmenta tras varios clips seguidos. "
          "En la corrida real fallaron 2 de 12, los dos en el tercero de su placa.",
     "a": "Reiniciar ComfyUI y relanzar: el runner saltea los que ya existen. Los dos "
          "salieron a la primera."},
    {"t": "El video final sale más corto de lo que debería",
     "s": "Pediste 60 s y el MP4 dura 57,6.",
     "p": "`-shortest` recorta a la pista de audio más corta, y la última línea de voz "
          "termina antes que el video.",
     "a": "`apad` en la mezcla y duración explícita del video. Ya lo hace `montaje.mezclar`."},
    {"t": "El audio suena distorsionado",
     "s": "Picos por encima de 0 dBFS en el máster.",
     "p": "**El audio que genera H3 ya viene clipeado**: medido a +2,68 dBFS.",
     "a": "Masterizar siempre con `loudnorm` a −14 LUFS y −1 dBTP. No es opcional."},
    {"t": "Un plano ENCADENADO falla por VRAM y reintentar no lo arregla",
     "s": "El mismo out-of-memory, pero en el **primer** clip de la cadena.",
     "p": "Un eslabón carga el GGUF de 23,9 GB **y** el último fotograma del plano "
          "anterior. En 32 GB el margen se cierra justo ahí.",
     "a": "En 32 GB, **con encadenado no pasar de 5,9 s por plano**. Suelto sí llega a "
          "7,3. Una toma continua larga se hace con más eslabones cortos, no más largos."},
    {"t": "La corrida tarda de más y una placa figura sin trabajo",
     "s": "Media hora extra de factura sin ningún error a la vista.",
     "p": "S06 no puede empezar sin el último fotograma de S05. Si S05 muere, su placa "
          "se queda parada —el resto ya está repartido— y sigue cobrando.",
     "a": "Generar los cabezas de cadena **primero** y verificarlos antes de repartir "
          "el resto. Si una cadena cae, relanzarla a mano en cuanto se ve el error."},
    {"t": "Te olvidás la máquina prendida",
     "s": "La factura.",
     "p": "Es lo que más olvido genera.",
     "a": "`python -m h3pipeline destruir <id> --si` apenas bajaste los clips. "
          "`instancias` te dice qué tenés corriendo."},
]

# El flujo real, ya probado de punta a punta.
PASOS_VAST = [
    ("En tu máquina, con la GPU apagada", [
        "python -m h3pipeline construir mi-video/proyecto.json",
        "python -m h3pipeline voz       mi-video/proyecto.json",
        "python -m h3pipeline frames    mi-video/proyecto.json",
        "#   …revisá los PNG acá. Un encuadre malo se ve en un dibujo,",
        "#   no después de cuatro minutos de generación cobrando.",
        "python -m h3pipeline empaquetar mi-video/proyecto.json",
    ]),
    ("Elegir y alquilar", [
        "python -m h3pipeline gpu      mi-video/proyecto.json",
        "#   ordena por costo TOTAL, no por $/h: bajar 59 GB pesa.",
        "python -m h3pipeline alquilar mi-video/proyecto.json <id> --si",
        "#   crea, adjunta tu clave SSH, espera el arranque y sube el ZIP.",
    ]),
    ("Dentro de la máquina", [
        "cd /workspace/refs && unzip -oq mi-video-para-vast.zip",
        "sed -i 's/\\r$//' *.sh *.py",
        "bash setup.sh                 # ~59 GB, 2-5 min con buen enlace",
        "PASOS=8 bash lanzar.sh        # ~4 min por clip, 4 en paralelo",
        "python /root/runner.py --montar",
    ]),
    ("De vuelta acá", [
        "python -m h3pipeline montar   mi-video/proyecto.json clips/",
        "#   y la mezcla con voz y música:",
        "#   montaje.mezclar(video, voces, salida, musica=...)",
    ]),
    ("Y esto es lo que no se olvida", [
        "python -m h3pipeline destruir <id> --si",
    ]),
]


def datos() -> dict:
    """Todo lo que la página necesita, extraído del módulo."""
    ests = {}
    for nombre in disponibles():
        e = Estructura.cargar(nombre)
        esq = {x["tramo"]: x for x in e.esqueleto()}
        ests[nombre] = {
            "etiqueta": _etiqueta(e),
            "formato": e.formato,
            "duracion": e.duracion_objetivo,
            "retencion": e.retencion_objetivo,
            "plataformas": e.plataformas,
            "interrupcion_cada": e.interrupcion_cada,
            "para": _para(e),
            "tramos": [{
                "id": t.id, "nombre": t.nombre, "desde": t.desde, "hasta": t.hasta,
                "objetivo": t.objetivo, "exige": t.exige,
                "corte_min": t.corte_min, "corte_max": t.corte_max,
                "tamanos": t.tamanos, "planos_min": t.planos_min,
                "texto_pantalla": t.texto_pantalla, "interrupcion": t.interrupcion,
            } for t in e.tramos],
            "esqueleto": [{
                "tramo": t.id, "planos": esq[t.id]["planos"],
                "corte": esq[t.id]["corte_sugerido"], "genera": esq[t.id]["genera_sugerido"],
                "tamanos": t.tamanos,
            } for t in e.tramos],
        }
    return {
        "estructuras": ests,
        "estilos": ESTILOS,
        "tamanos": [[k, prompts.NOMBRE_TAMANIO.get(k, k)] for k in prompts.TAMANIO],
        "automatico": AUTOMATICO,
        "reglas": REGLAS,
        "trampas": TRAMPAS,
        "pasos_vast": PASOS_VAST,
        "costo": COSTO,
        "grilla": {"minimo": round(grilla.MINIMO, 3), "maximo": round(grilla.MAXIMO, 3)},
    }


def _etiqueta(e: Estructura) -> str:
    if e.formato == "largo":
        return f"Narrativo, {e.duracion_objetivo / 60:.0f} min"
    return {23: "Ultracorto · regla 3/8/12", 60: "El estándar", 90: "Largo para short"} \
        .get(int(e.duracion_objetivo), e.nombre)


def _para(e: Estructura) -> str:
    """La primera nota de la estructura, recortada: dice para qué sirve."""
    if e.formato == "largo":
        return ("Apertura fría, planteo, detonante, punto medio, clímax. Con loops de "
                "curiosidad abiertos y re-enganche cada 60-90 s.")
    return {
        23: "Alcance puro: maximiza descubrimiento entre no seguidores. Si la idea necesita "
            "tres peldaños de revelación, no entra acá.",
        60: "El punto donde entra en las tres plataformas. Es el que tiene un video hecho "
            "detrás (PROFUNDIDAD).",
        90: "Guardados y comunidad, no alcance. A 90 s ya no es un YouTube Short: rinde en "
            "TikTok.",
    }.get(int(e.duracion_objetivo), "")


def generar(salida: Path | None = None) -> Path:
    salida = Path(salida or SALIDA)
    html = PLANTILLA.read_text(encoding="utf-8")
    if "__DATOS__" not in html:
        raise RuntimeError(f"{PLANTILLA} no tiene el marcador __DATOS__")
    # `</script>` dentro de un string JS cierra la etiqueta: hay que escaparlo.
    crudo = json.dumps(datos(), ensure_ascii=False, separators=(",", ":")) \
        .replace("</", "<\\/")
    salida.write_text(html.replace("__DATOS__", crudo), encoding="utf-8")
    return salida


def main() -> int:
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    p = generar()
    d = datos()
    print(f"{p}  ·  {p.stat().st_size / 1024:.0f} KB")
    for n, e in d["estructuras"].items():
        print(f"  {n:<10} {e['duracion']:>4.0f} s · {len(e['tramos'])} tramos · "
              f"{sum(x['planos'] for x in e['esqueleto']):>2} planos · "
              f"{e['retencion'] * 100:.0f} % retención")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
