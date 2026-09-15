r"""
Fase 3 — postproducción visual: SRT, hoja de sonido, concatenado y quemado.

Todo el módulo se apoya en una sola suposición, la que fija `guion.SEGUNDOS_POR_CLIP`:
**cada clip dura exactamente 15 s**. Nada acá mide la duración de un MP4 para
calcular tiempos. Eso hace la fase determinista y rápida — el SRT se puede
generar sin que exista un solo clip — pero también significa que si la Fase 2
rindió clips de otro largo, los subtítulos quedan corridos y el video no avisa.
Por eso al final se verifica la duración del máster contra la esperada.

Los cuatro pasos

    1  Subtitulos.srt     (clip_id-1)*15 → clip_id*15, formateado HH:MM:SS,mmm
    2  Guia_de_Sonido.txt  la hoja_de_ruta_sonora del LLM, tal cual, sin recalcular
    3  concat demuxer      ffmpeg -f concat -safe 0 -c copy, sin recodificar
    4  quemado             filtro subtitles con force_style, -c:a copy

Sobre el paso 4 en Windows
  El filtro `subtitles` parsea su argumento dentro del filtergraph, donde `\` es
  escape y `:` separa parámetros. Pasarle `C:\Users\...\Subtitulos.srt` falla
  siempre. En vez de pelear con el escapado, se lanza ffmpeg con el cwd puesto en
  la carpeta del SRT y se lo nombra relativo. Es la variante que no se rompe.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from . import frames, guion

for flujo in (sys.stdout, sys.stderr):
    flujo.reconfigure(encoding="utf-8", errors="replace")

SEGUNDOS = guion.SEGUNDOS_POR_CLIP

# El estilo del pedido. Colores ASS en &HAABBGGRR — 00FFFFFF es blanco opaco.
ESTILO = "FontSize=24,PrimaryColour=&H00FFFFFF,Outline=1,Shadow=1"

TEMPORAL = "Pelicula_Temporal.mp4"
MASTER = "Pelicula_Base.mp4"
SRT = "Subtitulos.srt"
GUIA = "Guia_de_Sonido.txt"
LISTA = "mylist.txt"


class ErrorMontaje(RuntimeError):
    """Falló un paso de ffmpeg o falta un insumo."""


# ───────────────────────────── SRT ─────────────────────────────

def srt_tiempo(segundos: float) -> str:
    """Segundos → HH:MM:SS,mmm, el formato que quiere SubRip."""
    total_ms = round(segundos * 1000)
    ms = total_ms % 1000
    s = total_ms // 1000
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d},{ms:03d}"


def escribir_srt(g: guion.Guion, destino: Path) -> int:
    """Genera el SRT con tiempos deterministas. Devuelve cuántos subtítulos puso.

    Los clips sin `texto_dialogo_limpio` se saltean, pero **no** corren el reloj:
    el tiempo sale del clip_id, así que un clip mudo deja su hueco de 15 s.
    """
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)

    bloques = []
    for c in g.timeline:
        texto = (c.texto_dialogo_limpio or "").strip()
        if not texto:
            continue
        ini = (c.clip_id - 1) * SEGUNDOS
        fin = c.clip_id * SEGUNDOS
        bloques.append(
            f"{len(bloques) + 1}\n"
            f"{srt_tiempo(ini)} --> {srt_tiempo(fin)}\n"
            f"{texto}\n")

    # UTF-8 con BOM: libass lee el SRT como Latin-1 si no lo encuentra, y ahí se
    # comen los acentos y las eñes de los diálogos en castellano.
    destino.write_text("\n".join(bloques), encoding="utf-8-sig")
    return len(bloques)


def escribir_guia(g: guion.Guion, destino: Path) -> int:
    """Vuelca la hoja_de_ruta_sonora tal cual la escribió el LLM."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)

    lineas = ["GUÍA DE SONIDO", "=" * 60, ""]
    for tramo in g.hoja_de_ruta_sonora:
        rango = tramo.get("rango_tiempo", "?")
        lineas.append(f"[{rango}]  {tramo.get('instruccion', '')}")
    lineas += ["", "-" * 60, "Diálogos por clip (para referencia de doblaje):", ""]
    for c in g.timeline:
        if (c.texto_dialogo_limpio or "").strip():
            ini = srt_tiempo((c.clip_id - 1) * SEGUNDOS)
            lineas.append(f"[{ini}]  clip {c.clip_id:03d}  {c.texto_dialogo_limpio}")

    destino.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return len(g.hoja_de_ruta_sonora)


# ───────────────────────────── ffmpeg ─────────────────────────────

def _correr(cmd: list[str], que: str, cwd: Path | None = None) -> None:
    r = subprocess.run(cmd, cwd=str(cwd) if cwd else None,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        cola = "\n".join((r.stderr or "").strip().splitlines()[-15:])
        raise ErrorMontaje(f"{que} falló (ffmpeg salió {r.returncode}):\n{cola}")


def escribir_lista(clips: list[Path], destino: Path) -> None:
    """El mylist.txt del demuxer concat.

    Rutas absolutas en POSIX — ffmpeg las acepta en Windows y evitan que los
    backslashes se coman como escapes. Las comillas simples internas se escapan
    como '\\'' , que es lo que entiende el parser del demuxer.
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    lineas = []
    for c in clips:
        p = str(Path(c).resolve().as_posix()).replace("'", r"'\''")
        lineas.append(f"file '{p}'")
    destino.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def concatenar(clips: list[Path], salida: Path, lista: Path | None = None) -> Path:
    """Une los clips sin recodificar. Exige que compartan códec y dimensiones."""
    if not clips:
        raise ErrorMontaje("No hay clips que concatenar")
    faltan = [c for c in clips if not Path(c).exists()]
    if faltan:
        raise ErrorMontaje(
            f"Faltan {len(faltan)} clips del timeline:\n  "
            + "\n  ".join(str(f) for f in faltan[:5]))

    salida = Path(salida)
    lista = lista or salida.parent / LISTA
    escribir_lista(clips, lista)

    _correr(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
             "-f", "concat", "-safe", "0", "-i", str(lista),
             "-c", "copy", str(salida)], "El concatenado")
    return salida


def quemar(video: Path, srt: Path, salida: Path, estilo: str = ESTILO) -> Path:
    """Quema el SRT sobre el video. Corre con cwd en la carpeta del SRT.

    Ver el docstring del módulo: nombrar el SRT relativo es lo que evita el
    infierno de escapar `C:\\` dentro de un filtergraph.
    """
    video, srt, salida = Path(video), Path(srt), Path(salida)
    if not srt.exists():
        raise ErrorMontaje(f"No existe el SRT {srt}")
    if srt.parent.resolve() != salida.parent.resolve():
        raise ErrorMontaje("El SRT y el máster tienen que salir en la misma carpeta")

    filtro = f"subtitles={srt.name}:force_style='{estilo}'"
    _correr(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
             "-i", video.name, "-vf", filtro, "-c:a", "copy", salida.name],
            "El quemado de subtítulos", cwd=srt.parent)
    return salida


# ───────────────────────────── orquestación ─────────────────────────────

def montar(g: guion.Guion, clips: list[Path], final: Path,
           estilo: str = ESTILO, limpiar: bool = True) -> Path:
    """Los cuatro pasos de la Fase 3. Devuelve la ruta del máster."""
    final = Path(final)
    final.mkdir(parents=True, exist_ok=True)

    n = escribir_srt(g, final / SRT)
    print(f"  ·   {SRT}: {n} subtítulos de {len(g.timeline)} clips")
    escribir_guia(g, final / GUIA)
    print(f"  ·   {GUIA}: {len(g.hoja_de_ruta_sonora)} tramos")

    temporal = final / TEMPORAL
    concatenar(clips, temporal)
    print(f"  ·   {TEMPORAL}: {len(clips)} clips unidos sin recodificar")

    master = quemar(temporal, final / SRT, final / MASTER, estilo)
    print(f"  ·   {MASTER}: subtítulos quemados")

    # El SRT se calculó suponiendo 15 s por clip; si la Fase 2 rindió otra cosa,
    # acá es donde se ve. cv2 ya es dependencia, así que no hace falta ffprobe.
    esperado = len(clips) * SEGUNDOS
    try:
        real = frames.info(master).duracion
        desvio = abs(real - esperado)
        estado = "OK " if desvio <= 1 else "!  "
        print(f"  {estado} duración: {real:.1f}s real vs {esperado}s esperada "
              f"({len(clips)} clips × {SEGUNDOS}s)")
        if desvio > 1:
            print(f"      Los subtítulos van a estar corridos ~{desvio:.1f}s al final.")
            print(f"      Revisá que la Fase 2 haya rendido clips de {SEGUNDOS}s.")
    except ValueError as e:
        print(f"  !   no pude verificar la duración: {e}")

    if limpiar:
        for basura in (final / LISTA, temporal):
            basura.unlink(missing_ok=True)

    return master


def revisar_ids(g: guion.Guion) -> list[str]:
    """Avisos sobre los clip_id, que son los que fijan los tiempos del SRT.

    El tiempo sale de `clip_id`, no de la posición en el array. Si los ids no son
    1..N corridos, el SRT y el video concatenado hablan de momentos distintos.
    """
    ids = [c.clip_id for c in g.timeline]
    avisos = []
    if ids != sorted(ids):
        avisos.append("Los clip_id no vienen ordenados: el SRT usa el id y el "
                      "concatenado usa el orden del array. Van a discrepar.")
    esperados = list(range(1, len(ids) + 1))
    if sorted(ids) != esperados:
        faltan = sorted(set(esperados) - set(ids))
        avisos.append(
            f"Los clip_id no son 1..{len(ids)} corridos (faltan {faltan or 'ninguno'}, "
            f"hay {sorted(ids)}). Como el tiempo se calcula (clip_id-1)×{SEGUNDOS}, "
            "cada hueco corre los subtítulos contra el video.")
    return avisos


# ───────────────────────────── CLI ─────────────────────────────

def main(argv=None) -> int:
    import argparse

    from .render import Rutas

    ap = argparse.ArgumentParser(description="Fase 3 — ensamblaje visual y subtítulos")
    ap.add_argument("--proyecto", type=Path, default=Path("Proyecto_Cine_IA"))
    ap.add_argument("--guion", type=Path, help="default: <proyecto>/guion.json")
    ap.add_argument("--estilo", default=ESTILO, help="force_style del filtro subtitles")
    ap.add_argument("--solo-srt", action="store_true",
                    help="escribe SRT y guía de sonido, no toca ffmpeg")
    ap.add_argument("--conservar", action="store_true", help="deja mylist.txt y el temporal")
    a = ap.parse_args(argv)

    r = Rutas(a.proyecto.resolve())
    g = guion.cargar(a.guion or (r.raiz / "guion.json"))

    for aviso in revisar_ids(g):
        print(f"  !   {aviso}")

    print(f"── {len(g.timeline)} clips × {SEGUNDOS}s = "
          f"{len(g.timeline) * SEGUNDOS}s de película ──")

    if a.solo_srt:
        n = escribir_srt(g, r.final / SRT)
        escribir_guia(g, r.final / GUIA)
        print(f"  OK  {SRT} ({n} subtítulos) y {GUIA} en {r.final}")
        return 0

    clips = [r.mp4(c) for c in g.timeline]
    master = montar(g, clips, r.final, a.estilo, limpiar=not a.conservar)
    print(f"\n  OK  {master}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ErrorMontaje, guion.GuionInvalido) as e:
        print(f"\n  X   {e}", file=sys.stderr)
        raise SystemExit(1)
