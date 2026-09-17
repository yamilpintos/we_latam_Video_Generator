"""El máster del loop: clips → corte → música loopeada → −14 LUFS → MP4 que se
repite sin costura.

    python -X utf8 -u bucle.py --musica pista.mp3                 # el loop
    python -X utf8 -u bucle.py --musica pista.mp3 --repite 10     # y la versión de 10 min

Por qué no usa `montaje.mezclar`: aquélla exige al menos una voz y le hace un
fundido de entrada de 2 s a la música. Un loop no tiene voz y no puede tener
fundidos en los extremos.

Cómo se cierra el bucle
  VIDEO   El último plano corta al primero como cualquier otro corte del video:
          planos sueltos, cámara fija, tamaños distintos a cada lado del corte.
          No hay nada que empalmar. Se usa `usa` segundos de cada clip (5,0 de
          los 5,17 generados): la cola de un clip de H3 deriva.
  AMBIENTE  El audio propio de H3 (lluvia) va debajo de la música. Cada tramo
          lleva un fundido de 50 ms a cada lado para que el corte no chasquee;
          la lluvia es ruido estacionario y el bache no se oye.
  MÚSICA  Se toma un segmento de la pista de la duración exacta del video y se
          cierra con un cruce: los últimos X segundos del segmento se funden con
          los X segundos que PRECEDEN al arranque del segmento. Así el final del
          loop desemboca en el mismo audio que sigue al principio, y la vuelta
          es continua. Si la pista no tiene margen antes del segmento, el cruce
          se hace contra su propia cola.

Salidas (al lado de proyecto.json)
  <titulo> - loop.mp4        el loop, 1920×1080, −14 LUFS
  <titulo> - loop x3.mp4     tres vueltas seguidas, para MIRAR el empalme (0:60 y 2:00)
  <titulo> - <N>x.mp4        con --repite N, para publicar
  <titulo> - <pista>.mp4     con --musica X --largo-de-pista: la pista manda la duración
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent.parent
sys.path.insert(0, str(RAIZ))

from h3pipeline import config, montaje  # noqa: E402

ANCHO, ALTO = 1920, 1080
FPS = 24
CODEC_V = ["-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p",
           "-r", str(FPS), "-g", str(FPS * 2)]
CODEC_A = ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]


def ff(*args: str) -> None:
    r = subprocess.run([config.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", *args],
                       capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("ffmpeg: " + r.stderr[-1200:])


def cortar(planos: list[dict], clips: Path, usa: float, tmp: Path, log,
           planos_ruta: str = "") -> tuple[Path, float]:
    """Cada clip recortado a `usa` s, escalado a 1080p, con micro-fundidos de
    audio, y todos concatenados. Devuelve (corte.mp4, duración)."""
    faltan = montaje.faltantes(planos, clips)
    if faltan:
        raise SystemExit(f"faltan clips en {clips}: {' '.join(faltan)}")
    # Recortes por plano, opcionales: `recortes.json` al lado de planos.json,
    # {"P08": [0, 3.0]}. Para un clip que se arruina a mitad de camino y no
    # vale otra pasada de GPU: se usa lo que sirve y el loop dura un poco menos.
    rec_ruta = Path(planos_ruta).parent / "recortes.json"
    recortes = json.loads(rec_ruta.read_text(encoding="utf-8")) if rec_ruta.exists() else {}
    partes, t = [], 0.0
    for p in planos:
        fuente = montaje.buscar_clip(clips, montaje.clip_fuente(p))
        ini, fin = recortes.get(p["id"], [0.0, usa])
        if float(fin) <= float(ini):
            log(f"  {p['id']:<5} omitido (recortes.json)")
            continue
        dur = min(float(fin) - float(ini), float(p["segundos"]) - float(ini))
        parte = tmp / f"{p['id']}.mp4"
        ff("-ss", f"{float(ini):.3f}", "-i", str(fuente), "-t", f"{dur:.3f}",
           "-vf", f"scale={ANCHO}:{ALTO}:flags=lanczos,setsar=1",
           "-af", f"afade=t=in:st=0:d=0.05,afade=t=out:st={dur - 0.05:.3f}:d=0.05,"
                  f"aresample=48000,apad,atrim=0:{dur:.3f}",
           *CODEC_V, *CODEC_A, str(parte))
        partes.append(parte)
        log(f"  {p['id']:<5} {float(ini):3.1f}-{float(ini) + dur:<4.1f} → {t:5.1f}-{t + dur:<5.1f} {p.get('funcion', '')[:50]}")
        t += dur
    lista = tmp / "orden.txt"
    lista.write_text("".join(f"file '{x.as_posix()}'\n" for x in partes), encoding="utf-8")
    corte = tmp / "corte.mp4"
    ff("-f", "concat", "-safe", "0", "-i", str(lista), "-c", "copy", str(corte))
    return corte, t


def una_escena(fuente: Path, dur: float, cierre: str, fundido: float, tmp: Path, log) -> tuple[Path, float]:
    """El loop de UN solo clip. H3 no puede hacer que el último cuadro sea el
    primero, así que el bucle se cierra de dos maneras:

      fundido   la cola del clip se funde sobre su cabeza (x segundos). El loop
                dura dur − x y arranca y termina en el mismo cuadro (el del
                segundo x). Sirve para casi todo movimiento ambiente.
      pingpong  el clip y después el clip al revés. Perfecto para lo simétrico
                (fuego, agua, luz que late, una respiración); se nota en lo que
                cae (lluvia, nieve) porque sube.
    """
    fuente = Path(fuente)
    corte = tmp / "corte.mp4"
    if cierre == "pingpong":
        ida = tmp / "ida.mp4"
        ff("-i", str(fuente), "-t", f"{dur:.3f}", "-vf", f"scale={ANCHO}:{ALTO}:flags=lanczos,setsar=1",
           *CODEC_V, *CODEC_A, str(ida))
        vuelta = tmp / "vuelta.mp4"
        ff("-i", str(ida), "-vf", "reverse", "-af", "areverse", *CODEC_V, *CODEC_A, str(vuelta))
        lista = tmp / "orden.txt"
        lista.write_text(f"file '{ida.as_posix()}'\nfile '{vuelta.as_posix()}'\n", encoding="utf-8")
        ff("-f", "concat", "-safe", "0", "-i", str(lista), "-c", "copy", str(corte))
        log(f"  una escena · ping-pong · {2 * dur:.1f} s")
        return corte, 2 * dur
    x = min(fundido, dur / 3)
    largo = dur - x
    # entrada 1: el clip desde x hasta el final; entrada 2: el clip de 0 a x.
    # xfade con d=x y offset=dur−2x: los últimos x segundos se funden sobre los
    # primeros x, y el resultado termina en el cuadro del segundo x, que es
    # exactamente donde arranca.
    # xfade exige a las dos entradas cuadros a ritmo constante, mismo tamaño,
    # formato y base de tiempo. Lo más robusto es escribir las dos partes como
    # archivos (ya a 24 fps, 1080p) y cruzarlas después.
    cola = tmp / "cola.mp4"
    cabeza = tmp / "cabeza.mp4"
    escala = f"scale={ANCHO}:{ALTO}:flags=lanczos,setsar=1"
    ff("-ss", f"{x:.3f}", "-i", str(fuente), "-t", f"{dur - x:.3f}", "-vf", escala,
       "-af", "aresample=48000", *CODEC_V, *CODEC_A, str(cola))
    ff("-i", str(fuente), "-t", f"{x:.3f}", "-vf", escala,
       "-af", "aresample=48000", *CODEC_V, *CODEC_A, str(cabeza))
    dur_cola = montaje.duracion(cola) or (dur - x)
    offset = max(0.0, dur_cola - x)
    ff("-i", str(cola), "-i", str(cabeza), "-filter_complex",
       f"[0:v][1:v]xfade=transition=fade:duration={x:.3f}:offset={offset:.3f}[v];"
       f"[0:a][1:a]acrossfade=d={x:.3f}:c1=tri:c2=tri[au]",
       "-map", "[v]", "-map", "[au]", *CODEC_V, *CODEC_A, str(corte))
    largo = montaje.duracion(corte) or largo
    log(f"  una escena · fundido de {x:.1f} s · loop de {largo:.1f} s (empieza y termina en el mismo cuadro)")
    return corte, largo


def filtro_musica(dur_pista: float, largo: float, cruce: float, desde: float | None):
    """El grafo de ffmpeg que deja la música de `largo` s exactos y cerrada en
    bucle. Devuelve (filtro, etiqueta_de_salida, desde_usado)."""
    if desde is None:
        margen = dur_pista - largo - 2 * cruce
        desde = cruce + max(0.0, margen) / 2 if margen >= 0 else 0.0
    if desde + largo > dur_pista + 0.01:
        raise SystemExit(f"la pista dura {dur_pista:.1f} s y el segmento pide "
                         f"{desde:.1f}+{largo:.1f}: elegí otro --desde o una pista más larga")
    fin = desde + largo
    if desde >= cruce:
        pre = f"[1:a]atrim=start={desde - cruce:.3f}:end={desde:.3f},asetpts=PTS-STARTPTS[B]"
    else:
        # Sin margen antes del segmento: el cruce va contra la cola de la pista.
        pre = (f"[1:a]atrim=start={dur_pista - cruce:.3f}:end={dur_pista:.3f},"
               f"asetpts=PTS-STARTPTS[B]")
    f = [
        f"[1:a]atrim=start={desde:.3f}:end={fin:.3f},asetpts=PTS-STARTPTS,asplit[A1][A2]",
        f"[A1]atrim=0:{largo - cruce:.3f},asetpts=PTS-STARTPTS[cabeza]",
        f"[A2]atrim=start={largo - cruce:.3f}:end={largo:.3f},asetpts=PTS-STARTPTS[cola]",
        pre,
        f"[cola][B]acrossfade=d={cruce:.3f}:c1=tri:c2=tri[cierre]",
        "[cabeza][cierre]concat=n=2:v=0:a=1[mus]",
    ]
    return ";".join(f), "[mus]", desde


def masterizar(corte: Path, musica: Path | None, largo: float, salida: Path,
               ambiente_db: float, cruce: float, desde: float | None, log) -> None:
    entradas = ["-i", str(corte)]
    f = [f"[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
         f"volume={ambiente_db}dB[amb]"]
    if musica:
        entradas += ["-i", str(musica)]
        dur_pista = montaje.duracion(musica)
        fm, et, usado = filtro_musica(dur_pista, largo, cruce, desde)
        f.append(fm)
        f.append(f"{et}aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[m]")
        f.append("[amb][m]amix=inputs=2:normalize=0:duration=first[mez]")
        log(f"  música: pista de {dur_pista:.1f} s, segmento {usado:.1f}-{usado + largo:.1f} s, "
            f"cruce de {cruce:.1f} s")
    else:
        f.append("[amb]anull[mez]")
    f.append("[mez]atrim=0:%.3f[pre]" % largo)
    pre = ";".join(f)
    # loudnorm en DOS pasadas. En una sola (modo dinámico) la lluvia sola quedó
    # en −18,3 LUFS con objetivo −14; con las medidas de la primera pasada
    # trabaja en modo lineal y clava el objetivo.
    m = _medir_loudnorm(entradas, pre, "[pre]")
    try:
        medido_i = float(m["input_i"])
    except (TypeError, ValueError):
        medido_i = float("-inf")
    if medido_i < -70:
        # Audio prácticamente mudo (un clip de H3 sin ambiente y sin música):
        # loudnorm no puede normalizar el silencio. Se deja tal cual.
        log("  audio casi mudo: sin normalizar")
        ff(*entradas, "-filter_complex", pre + ";[pre]aresample=48000[out]",
           "-map", "0:v", "-map", "[out]", "-c:v", "copy", *CODEC_A, "-t", f"{largo:.3f}", str(salida))
    else:
        log(f"  medido: {medido_i:.1f} LUFS, pico {float(m['input_tp']):.1f} dBTP, "
            f"LRA {float(m['input_lra']):.1f}")
        ln = (f"loudnorm=I=-14:TP=-1.0:LRA=11:measured_I={m['input_i']}:"
              f"measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:"
              f"measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
        ff(*entradas, "-filter_complex", pre + f";[pre]{ln},aresample=48000[out]",
           "-map", "0:v", "-map", "[out]", "-c:v", "copy", *CODEC_A, "-t", f"{largo:.3f}", str(salida))
    log(f"  {salida.name}   {largo:.1f} s   {salida.stat().st_size / 1e6:.1f} MB")


def _medir_loudnorm(entradas: list[str], pre: str, etiqueta: str) -> dict:
    """Primera pasada de loudnorm: mide la mezcla y devuelve los valores que
    necesita la segunda (`measured_*`)."""
    import json as _json
    r = subprocess.run(
        [config.ffmpeg(), "-hide_banner", "-nostats", *entradas, "-filter_complex",
         pre + f";{etiqueta}loudnorm=I=-14:TP=-1.0:LRA=11:print_format=json[med]",
         "-map", "[med]", "-f", "null", "-"], capture_output=True, text=True)
    txt = r.stderr
    i, j = txt.rfind("{"), txt.rfind("}")
    if i < 0 or j < 0:
        raise SystemExit("loudnorm no devolvió medidas:\n" + txt[-800:])
    return _json.loads(txt[i:j + 1])


def repetir(loop: Path, veces: int, salida: Path, log) -> None:
    lista = salida.with_suffix(".orden.txt")
    lista.write_text(f"file '{loop.as_posix()}'\n" * veces, encoding="utf-8")
    try:
        ff("-f", "concat", "-safe", "0", "-i", str(lista), "-c", "copy", str(salida))
    finally:
        lista.unlink(missing_ok=True)
    log(f"  {salida.name}   ×{veces}   {salida.stat().st_size / 1e6:.1f} MB")


def cubrir_pista(loops: list[Path], pista: Path, salida: Path, log) -> None:
    """La PISTA manda: se alternan los loops hasta cubrir su duración, se corta
    al largo exacto de la pista y se funde el último segundo. Para una canción
    de 3 minutos con loops de 15 s, alternar varios evita que el mismo se vea
    doce veces."""
    dur = montaje.duracion(pista)
    if not dur:
        raise SystemExit(f"no pude medir {pista}")
    largos = [montaje.duracion(l) for l in loops]
    orden, t, i = [], 0.0, 0
    while t < dur + 0.5:
        orden.append(loops[i % len(loops)]); t += largos[i % len(largos)]; i += 1
    lista = salida.with_suffix(".orden.txt")
    lista.write_text("".join(f"file '{l.as_posix()}'\n" for l in orden), encoding="utf-8")
    try:
        # El video se COPIA, no se recodifica: los loops ya salieron de acá con
        # el mismo códec, tamaño y fps, así que el concat es exacto y una
        # canción de 30 minutos se arma en segundos (recodificar 1080p a 0,5
        # CPU en un servidor llevaría horas). Sólo el audio se procesa: la
        # pista reemplaza al ambiente del loop y se normaliza a −14 LUFS.
        ff("-f", "concat", "-safe", "0", "-i", str(lista), "-i", str(pista),
           "-filter_complex",
           f"[1:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
           f"loudnorm=I=-14:TP=-1.0:LRA=11,aresample=48000,afade=t=out:st={max(0.0, dur - 2.0):.3f}:d=2.0[a]",
           "-map", "0:v", "-map", "[a]", "-c:v", "copy", *CODEC_A,
           "-t", f"{dur:.3f}", "-movflags", "+faststart", str(salida))
    finally:
        lista.unlink(missing_ok=True)
    real = montaje.duracion(salida) or dur
    log(f"  {salida.name}   {real:.0f} s (pista {dur:.0f} s) · {len(orden)} vueltas de {len(loops)} loop(s)   "
        f"{salida.stat().st_size / 1e6:.1f} MB · video copiado sin recodificar")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--planos", default=str(AQUI / "planos.json"))
    ap.add_argument("--clips", default=str(AQUI / "clips"))
    ap.add_argument("--musica", help="la pista (mp3/wav). Sin ella, sólo el ambiente de H3")
    ap.add_argument("--usa", type=float, default=5.0, help="segundos de cada clip (default 5,0)")
    ap.add_argument("--cruce", type=float, default=2.0, help="cruce del cierre musical, s")
    ap.add_argument("--desde", type=float, help="segundo de la pista donde arranca el segmento")
    ap.add_argument("--ambiente-db", type=float, default=-18.0,
                    help="nivel del audio de H3 bajo la música (default -18)")
    ap.add_argument("--sin-ambiente", action="store_true", help="apaga el audio de H3")
    ap.add_argument("--repite", type=int, default=0, help="además, una versión de N vueltas")
    ap.add_argument("--largo-de-pista", action="store_true",
                    help="la pista manda: el loop se repite hasta cubrirla y se corta a su largo")
    ap.add_argument("--otros-loops", nargs="*", default=[],
                    help="otros «- loop.mp4» ya hechos para alternar con éste (con --largo-de-pista)")
    ap.add_argument("--cierre", choices=("fundido", "pingpong", "corte"), default="fundido",
                    help="cómo se cierra un loop de UNA escena (un solo plano)")
    ap.add_argument("--fundido", type=float, default=1.0, help="segundos del fundido de cierre (una escena)")
    a = ap.parse_args()

    doc = json.loads(Path(a.planos).read_text(encoding="utf-8"))
    planos = doc["planos"]
    titulo = doc["titulo"]
    log = print
    tmp = Path(tempfile.mkdtemp(prefix="bucle_"))
    try:
        log("corte:")
        if len(planos) == 1 and a.cierre != "corte":
            p = planos[0]
            fuente = montaje.buscar_clip(Path(a.clips), montaje.clip_fuente(p))
            if not fuente:
                raise SystemExit(f"falta el clip de {p['id']} en {a.clips}")
            corte, largo = una_escena(fuente, float(p["segundos"]), a.cierre, a.fundido, tmp, log)
        else:
            corte, largo = cortar(planos, Path(a.clips), a.usa, tmp, log, a.planos)
        log(f"  corte.mp4   {largo:.1f} s\n")
        loop = AQUI / f"{titulo} - loop.mp4"
        log("máster:")
        if a.largo_de_pista and a.musica:
            # El loop se masteriza SIN música (sólo ambiente, cerrado en bucle) y
            # después la pista entera manda la duración del video final.
            masterizar(corte, None, largo, loop, -90.0 if a.sin_ambiente else a.ambiente_db, a.cruce, None, log)
            loops = [loop] + [Path(x) for x in a.otros_loops if Path(x).exists()]
            final = AQUI / f"{titulo} - {Path(a.musica).stem}.mp4"
            cubrir_pista(loops, Path(a.musica), final, log)
        else:
            masterizar(corte, Path(a.musica) if a.musica else None, largo, loop,
                       -90.0 if a.sin_ambiente else a.ambiente_db, a.cruce, a.desde, log)
        repetir(loop, 3, AQUI / f"{titulo} - loop x3.mp4", log)
        if a.repite:
            repetir(loop, a.repite, AQUI / f"{titulo} - {a.repite}x.mp4", log)
        log(f"\nMirá el empalme en «{titulo} - loop x3.mp4» en {largo:.0f} s y en {2 * largo:.0f} s.")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
