# -*- coding: utf-8 -*-
"""El máster de la réplica. Se corre DESPUÉS de bajar los clips de Vast.

No usa `python -m h3pipeline mezclar` porque la réplica tiene tres cosas que el
mezclador general no hace, y las tres salen del original medido:

  1. **Sin música y sin ambiente.** El original es voz sola sobre imagen muda:
     45 silencios reales de hasta 0,8 s, con el piso cayendo a -62 dB. Si
     hubiera cama musical ese piso no existiría. Así que el audio que genera H3
     se apaga (`ambiente_db=-60`) y no hay pista de música.

  2. **Cada línea se comprime a su ventana, hasta 1,30x.** El texto es de ellos
     y no se reescribe (es el benchmark), pero su voz corre a ~22,7 cps hablando
     y Kate a 16,7 medidos: 223,7 s para decir lo que ellos dicen en 181,3.
     Comprimir es exactamente lo que hacen ellos -la de ellos es TTS acelerada-
     y acá se hace línea por línea con el factor medido, no a ojo. Lo que pase
     de 1,30x se deja correr: deformar más se escucha.

     Con ese tope **la voz termina en 188,0 s contra 181,4 de video**: 6,6 s de
     atraso acumulado. Una línea nunca arranca antes de su marca del original ni
     encima de la anterior, así que el desvío se ve como retraso y no como dos
     voces sonando juntas. Al montar hay que decidir qué hacer con esos 6,6 s:
     estirar el último plano, o subir TOPE a 1,50 (ahí el atraso baja a 1,0 s y
     la deformación empieza a oírse).

  3. **Los subtítulos llevan los tiempos reales de nuestra voz**, frase por
     frase como ellos, no las marcas del original: si la voz va atrasada, el
     subtítulo tiene que ir con ella.

    python mis-videos/replica-jcfdlw/mezclar_replica.py <carpeta-de-clips>
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).parent
sys.path.insert(0, str(AQUI / "../.."))
from h3pipeline import config, montaje, tts, voz as vozmod    # noqa: E402
from h3pipeline.proyecto import Proyecto                      # noqa: E402

TOPE = vozmod.MAX_RAPIDO_DURO   # 1,30: más que esto se escucha deformado


def comprimir(mp3: Path, factor: float, salida: Path) -> None:
    """atempo acepta 0,5-100 por etapa, así que un solo filtro alcanza acá."""
    salida.parent.mkdir(parents=True, exist_ok=True)
    if factor <= 1.001:
        salida.write_bytes(mp3.read_bytes())
        return
    subprocess.run([config.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(mp3), "-filter:a", f"atempo={factor:.4f}",
                    "-c:a", "libmp3lame", "-q:a", "2", str(salida)], check=True)


def placa_fija(carpeta: Path, pid: str = "S77", png: str = "l_cosmos.png",
               segundos: float = 5.2) -> Path:
    """La placa final es un gráfico, no una toma: H3 le metió a la protagonista
    dos veces seguidas. Se reemplaza por la imagen madre quieta, que es lo que
    el original tiene de todos modos. Se regenera SIEMPRE antes del montaje,
    porque `bajar` vuelve a traer el clip malo de la máquina."""
    salida = Path(carpeta) / f"{pid}_00001_.mp4"
    subprocess.run([config.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
                    "-loop", "1", "-i", str(AQUI / "assets" / png), "-t", f"{segundos}",
                    "-vf", "scale=768:1344:force_original_aspect_ratio=increase,"
                           "crop=768:1344,format=yuv420p",
                    "-r", "24", "-c:v", "libx264", "-crf", "18", "-an", str(salida)],
                   check=True)
    return salida


def dibujo_con_zoom(carpeta: Path, pid: str, segundos: float = 6.0) -> Path:
    """Plan B sin GPU para un clip que no salió: su primer fotograma (que sí se
    revisó y está bien) con un acercamiento lento. En un video que corta cada
    2,3 s, un plano quieto de 5 s se nota; uno que respira, mucho menos. Se usa
    sólo para los ids que se pasan por línea de comando."""
    png = AQUI / "assets" / f"sb_{pid}.png"
    salida = Path(carpeta) / f"{pid}_00001_.mp4"
    n = int(segundos * 24)
    subprocess.run([config.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
                    "-loop", "1", "-i", str(png), "-t", f"{segundos}",
                    "-vf", (f"scale=1536:2688,zoompan=z='1+0.12*on/{n}':"
                            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=768x1344:fps=24,"
                            "format=yuv420p"),
                    "-c:v", "libx264", "-crf", "18", "-an", str(salida)], check=True)
    return salida


def main(carpeta, fijos=()):
    p = Proyecto.cargar(AQUI / "proyecto.json")
    _sb, doc = p.construir()
    planos = doc["planos"]
    placa_fija(Path(carpeta), pid="PLACA")
    for pid in fijos:
        print(f"  plan B sin GPU para {pid}: dibujo con zoom")
        dibujo_con_zoom(Path(carpeta), pid)

    falta = montaje.faltantes(planos, Path(carpeta))
    if falta:
        raise SystemExit(f"!! faltan {len(falta)} clips: {' '.join(falta)}")

    corte = AQUI / "corte.mp4"
    montaje.recortar_y_concatenar(planos, Path(carpeta), corte)

    # La misma línea de tiempo que usó armar.py para las duraciones de los
    # planos: la imagen sigue a la voz por construcción.
    sys.path.insert(0, str(AQUI))
    from linea_de_tiempo import lineas as lineas_nuevas
    ajustadas, pasados, subs = [], [], []
    reloj = 0.0
    for l in lineas_nuevas(TOPE):
        h = hashlib.sha1(l["texto"].encode("utf-8")).hexdigest()[:8]
        mp3 = AQUI / "voz" / f"{l['id']}_{h}.mp3"
        if l["factor"] > TOPE:
            pasados.append((l["id"], round(l["factor"], 2)))
        out = AQUI / "voz-ajustada" / f"{l['id']}.mp3"
        comprimir(mp3, l["usado"], out)
        ajustadas.append((l["ini"], out))
        subs.append((l["ini"], l["fin"], l["texto"]))
        reloj = l["fin"]

    srt = AQUI / "replica.srt"
    montaje.srt_voz(subs, srt)

    sin_sub = AQUI / "REPLICA - sin subtitulos.mp4"
    montaje.mezclar(corte, ajustadas, sin_sub, musica=None, ambiente_db=-60.0)
    montaje.quemar_srt(sin_sub, srt, AQUI / "REPLICA - final.mp4")

    atraso = reloj - montaje.duracion(corte)
    print(f"\n{len(ajustadas)} lineas · {len(pasados)} por encima de {TOPE:.2f}x "
          f"(se dejaron correr) · la voz termina {atraso:+.1f} s respecto del video")
    (AQUI / "mezcla.json").write_text(json.dumps(
        {"pasados": pasados, "tope": TOPE, "fin_voz": round(reloj, 2),
         "atraso_s": round(atraso, 2)}, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    main(sys.argv[1], fijos=sys.argv[2:])
