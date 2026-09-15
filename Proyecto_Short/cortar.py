"""Arma el Short de 60 s recortando los 12 clips generados.

    python Proyecto_Short/cortar.py carpeta_con_los_clips

H3 no puede generar planos de menos de 5.2 s, pero el arranque de un Short
necesita cortes de 1.5 a 2.5 s o pierde al espectador. Por eso se generaron
74.8 s para usar 60: de cada clip se toma el tramo anotado en `usa` dentro de
planos.json y se descarta el resto.

Cada clip se recorta y se recodifica por separado, y recien despues se
concatenan. Cortar directo con -c copy no sirve: el corte cae en un fotograma
cualquiera y ffmpeg lo mueve al keyframe mas cercano, que puede estar a un
segundo de distancia — justo lo que arruina un ritmo pensado al decimo.

Para cambiar el ritmo se editan los `usa` en planos.json y se vuelve a correr.
"""
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

RAIZ = pathlib.Path(__file__).parent


def ffmpeg(*args):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
                       capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("!! ffmpeg: " + r.stderr[-600:])


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    origen = pathlib.Path(sys.argv[1])
    planos = json.loads((RAIZ / "planos.json").read_text(encoding="utf-8"))["planos"]

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="short_"))
    partes, t = [], 0.0
    print("%-5s %-9s %-9s %s" % ("id", "del clip", "en linea", "funcion"))
    try:
        for p in planos:
            hay = sorted(origen.glob(p["id"] + "_*.mp4")) or sorted(origen.glob(p["id"] + ".mp4"))
            if not hay:
                raise SystemExit(f"!! falta el clip de {p['id']} en {origen}")
            ini, fin = p["usa"]
            dur = fin - ini
            salida = tmp / (p["id"] + ".mp4")
            # -ss antes de -i busca rapido; -t despues fija la duracion exacta.
            ffmpeg("-ss", str(ini), "-i", str(hay[0]), "-t", str(dur),
                   "-c:v", "libx264", "-preset", "medium", "-crf", "17",
                   "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                   "-ar", "48000", "-ac", "2", str(salida))
            partes.append(salida)
            print("%-5s %4.1f-%-4.1f %5.1f-%-5.1f %s"
                  % (p["id"], ini, fin, t, t + dur, p["funcion"][:44]))
            t += dur

        lista = tmp / "orden.txt"
        lista.write_text("".join("file '%s'\n" % x.as_posix() for x in partes),
                         encoding="utf-8")
        final = RAIZ / "PROFUNDIDAD_60s.mp4"
        ffmpeg("-f", "concat", "-safe", "0", "-i", str(lista), "-c", "copy", str(final))
        print("\n%s   %.1f s   %.1f MB"
              % (final.name, t, final.stat().st_size / 1e6))
        print("\nFalta ponerle encima, en tu editor:")
        print("  - la voz en off (voz_en_off.txt, con sus tiempos)")
        print("  - el contador de profundidad como grafico sobre S03")
        print("  - la musica")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
