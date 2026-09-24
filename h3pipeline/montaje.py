"""Montaje local con ffmpeg: recortar cada clip a su tramo `usa`, concatenar,
y escribir los subtítulos.

Dos detalles que costaron:
  - Cada clip se recorta y RECODIFICA por separado y recién después se
    concatena. Cortar con `-c copy` mueve el corte al keyframe más cercano,
    que puede estar a un segundo: justo lo que arruina un ritmo al décimo.
  - El SRT va con BOM (utf-8-sig): sin él libass lo lee como Latin-1 y
    destroza los acentos al quemar los subtítulos.
"""
from __future__ import annotations

import shutil
import os
import subprocess
import tempfile
from pathlib import Path

from . import config

# 22/9: el máster de un largo de 7 min tardaba ~40 min en el único procesador de
# Render. `veryfast` codifica 1,75× más rápido que `medium` con SSIM 0,993 contra
# él (medido en 20 s del camión); YouTube recomprime igual.
PRESET = "veryfast"


class ErrorMontaje(RuntimeError):
    pass


def _ffmpeg(*args: str) -> None:
    r = subprocess.run([config.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", *args],
                       capture_output=True, text=True)
    if r.returncode:
        raise ErrorMontaje("ffmpeg: " + r.stderr[-800:])


def duracion(archivo: Path) -> float:
    """Segundos de un archivo, leídos con ffmpeg.

    Sin ffprobe a propósito: la imagen de ffmpeg del proyecto no lo trae, y el
    dato está igual en el stderr del propio ffmpeg."""
    import re
    r = subprocess.run([config.ffmpeg(), "-hide_banner", "-i", str(archivo)],
                       capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", r.stderr)
    if not m:
        return 0.0
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


def es_ruido(mp4: Path, umbral: int = 22000) -> bool:
    """¿El clip es ruido puro? Un fotograma de ruido no comprime: a 192 px y
    calidad JPEG 5, los clips de ruido del 31/8 pesaron 25,0-25,6 KB y los
    buenos 4-15 — salvo S39 (ladrillo + carbón + nieve al sol), que dio 21,0 y
    era bueno: por eso el umbral es 22, no 20. Misma heurística que
    `remoto/runner.py`; si ffmpeg falla, se asume bueno."""
    import subprocess
    import tempfile
    try:
        dst = Path(tempfile.gettempdir()) / f"_ruido_{Path(mp4).stem}.jpg"
        r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                            "-ss", "2.5", "-i", str(mp4), "-frames:v", "1",
                            "-vf", "scale=192:-1", "-q:v", "5", str(dst)],
                           capture_output=True, text=True, timeout=60)
        if r.returncode or not dst.exists():
            return False
        tam = dst.stat().st_size
        dst.unlink()
        return tam > umbral
    except Exception:
        return False


def buscar_clip(carpeta: Path, id_: str) -> Path | None:
    carpeta = Path(carpeta)
    hay = sorted(carpeta.glob(f"{id_}_*.mp4")) or sorted(carpeta.glob(f"{id_}.mp4"))
    return hay[0] if hay else None


def clip_fuente(p: dict) -> str:
    """De qué clip sale este plano. Normalmente el suyo; con `clip_de`, el de
    otro plano: un encuadre que se repite se genera UNA vez y se trocea entre
    las tomas que lo usan. Es lo que hace costeable cortar cada 2,3 s con un
    generador que no baja de 5,17 s por clip."""
    return p.get("clip_de") or p["id"]


def faltantes(planos: list[dict], carpeta: Path) -> list[str]:
    return sorted({clip_fuente(p) for p in planos
                   if buscar_clip(carpeta, clip_fuente(p)) is None})


# Aire alrededor de la voz medida. NO es cosmético: es el 19 % de un largo
# actuado. Medido en «LA SANGRE ENCUENTRA EL CAMINO» (22/9): H3 habla a 152
# palabras/min, igual que los canales de referencia (151), pero el video
# terminado daba 123 porque sólo el 81 % era voz. Los 47 s restantes eran estos
# bordes, 0,75 s por clip × 70 clips. Con 0,15/0,20 el mismo video da ~139.
# Bajarlo más empieza a comerse el ataque de las consonantes suaves, porque la
# voz se mide por energía y un arranque flojo se detecta tarde.
AIRE_ANTES = float(os.environ.get("MONTAJE_AIRE_ANTES", "0.15"))
AIRE_DESPUES = float(os.environ.get("MONTAJE_AIRE_DESPUES", "0.20"))

# SINCRONÍA (22/9): H3 entrega cada clip con la voz ya en sincronía con la boca
# (medido: 0 ms en los clips crudos). Imagen y sonido de cada clip se cortan
# JUNTOS, con exactamente la misma duración, y nunca se separan (pedido del
# usuario: «cortá el video con el audio, no por separado»). El atraso que se oía
# en los diálogos del camión (0,2 s al principio, 3 s al final) era de montaje:
# cada tramo AAC traía ~30 ms de relleno del codificador y al mezclar se sumaban.
def adelanto(p: dict) -> float:
    """Compatibilidad: ya no se adelanta nada."""
    return 0.0
MIN_TRAMO_HABLADO = 1.4                   # s: un plano hablado nunca queda más corto
FPS = 24


def _cuadro(t: float) -> float:
    return round(round(t * FPS) / FPS, 3)


def ajustar_usa_por_voz(planos: list[dict], carpeta: Path, idioma: str = "es", log=print) -> int:
    """LA BOCA MANDA EL CORTE (réplica, REGLAS 48/63; a la web el 21/9). En cada
    plano con diálogo se mide dónde habla de verdad el clip (`voz_clip`) y el
    tramo `usa` se corre a la voz, con aire antes y después. Las tomas largas
    (≥ 10 s) no se recortan —son una toma continua— pero igual se miden para
    los subtítulos por línea. Devuelve cuántos `usa` cambiaron."""
    from . import voz_clip
    n = 0
    for p in planos:
        if not p.get("dialogo") or p.get("clip_de"):
            continue
        clip = buscar_clip(carpeta, clip_fuente(p))
        if not clip:
            continue
        try:
            v = voz_clip.medir(clip, p["dialogo"], idioma)
        except Exception as e:
            log(f"  {p['id']}: no pude medir la voz ({e}); queda el corte del plan")
            continue
        p["voz_medida"] = v
        seg = float(p.get("segundos") or v["dur"] or 0) or v["dur"]
        if v["fuente"] == "nada":
            log(f"  {p['id']}: sin voz detectable en el clip; queda el corte del plan")
            continue
        if seg >= 10 or p.get("usa_manual"):
            log(f"  {p['id']}: voz {v['ini']:.2f}-{v['fin']:.2f} s ({v['fuente']}); toma entera, sin recorte")
            continue
        ini = max(0.0, v["ini"] - AIRE_ANTES)
        fin = min(seg, v["fin"] + AIRE_DESPUES)
        if fin - ini < MIN_TRAMO_HABLADO:
            falta = MIN_TRAMO_HABLADO - (fin - ini)
            fin = min(seg, fin + falta)
            ini = max(0.0, ini - max(0.0, MIN_TRAMO_HABLADO - (fin - ini)))
        nuevo = [_cuadro(ini), _cuadro(fin)]
        viejo = list(p.get("usa") or [0.0, seg])
        if abs(nuevo[0] - viejo[0]) > 0.02 or abs(nuevo[1] - viejo[1]) > 0.02:
            n += 1
        p["usa"] = nuevo
        log(f"  {p['id']}: voz {v['ini']:.2f}-{v['fin']:.2f} s ({v['fuente']}) → corte {nuevo[0]:.2f}-{nuevo[1]:.2f} (plan {viejo[0]:.2f}-{viejo[1]:.2f})")
    return n


def _lista(partes: list[Path], ruta: Path) -> None:
    ruta.write_text("".join(f"file '{x.as_posix()}'\n" for x in partes), encoding="utf-8")


FPS_H3 = 24
MUESTRAS_POR_CUADRO = 48000 // FPS_H3      # 2000


def _tramo_exacto(fuente: str, ini: float, dur: float, parte: Path) -> int:
    """Un tramo del clip con imagen y sonido JUNTOS y del mismo largo exacto:
    N cuadros de video y N×2000 muestras de audio PCM (sin el relleno que agrega
    AAC, que al pegar 92 tramos atrasaba la voz hasta 3 s). Devuelve N."""
    n = max(1, int(round(dur * FPS_H3)))
    _ffmpeg("-ss", f"{ini:.3f}", "-i", fuente, "-frames:v", str(n),
            "-af", f"aresample=48000,apad,atrim=end_sample={n * MUESTRAS_POR_CUADRO}",
            "-c:v", "libx264", "-preset", PRESET, "-crf", "17", "-pix_fmt", "yuv420p", "-r", str(FPS_H3),
            "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", str(parte))
    return n


def _segundos_audio(archivo: Path) -> float:
    """Segundos de audio CONTADOS EN MUESTRAS (no por marcas de tiempo): es lo que
    ve el filtro al mezclar, y lo que se corría antes."""
    r = subprocess.run([config.ffmpeg(), "-hide_banner", "-loglevel", "error", "-i", str(archivo),
                        "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "-"], capture_output=True)
    return len(r.stdout) / 2 / 8000


def _pegar(partes: list[Path], salida: Path, tmp: Path) -> None:
    """Pega los tramos (video copiado) y codifica el audio UNA sola vez."""
    lista = tmp / "orden.txt"
    _lista(partes, lista)
    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    _ffmpeg("-f", "concat", "-safe", "0", "-i", str(lista), "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", str(salida))


def recortar_y_concatenar(planos: list[dict], carpeta: Path, salida: Path, log=print) -> Path:
    """De cada clip se toma el tramo `usa` (o el clip entero) y se pegan en orden.
    Cada tramo dura un número entero de cuadros y su audio exactamente lo mismo."""
    faltan = faltantes(planos, carpeta)
    if faltan:
        raise ErrorMontaje(f"faltan clips en {carpeta}: {' '.join(faltan)}")
    tmp = Path(tempfile.mkdtemp(prefix="h3corte_"))
    partes, t = [], 0.0
    try:
        for k, p in enumerate(planos):
            ini, fin = p.get("usa") or (0.0, p["segundos"])
            if p.get("usa"):
                # El tramo se redondea a cuadros ACÁ, en el mismo plano: la línea de
                # tiempo de la narración se calcula después con estos mismos `usa`
                # y así coincide con el video al cuadro.
                n_ = max(1, int(round((float(fin) - float(ini)) * FPS_H3)))
                p["usa"] = [round(float(ini), 4), round(float(ini) + n_ / FPS_H3, 4)]
                ini, fin = p["usa"]
            parte = tmp / f"{k:03d}_{p['id']}.mkv"
            n = _tramo_exacto(str(buscar_clip(carpeta, clip_fuente(p))), float(ini), float(fin) - float(ini), parte)
            dur = n / FPS_H3
            partes.append(parte)
            log(f"  {p['id']:<5} {float(ini):4.1f}-{float(fin):<4.1f} → {t:5.1f}-{t + dur:<5.1f} "
                f"{p.get('funcion', '')[:44]}")
            t += dur
        _pegar(partes, salida, tmp)
        # Control: el audio pegado tiene que durar lo mismo que la suma de los
        # tramos (22/9: el relleno del AAC atrasaba la voz hasta 3 s y nadie avisaba).
        dif = _segundos_audio(Path(salida)) - t
        if abs(dif) > 0.15:
            raise ErrorMontaje(f"el audio del corte quedó {dif:+.2f} s respecto del video "
                               f"({t:.2f} s): la voz saldría corrida")
        log(f"\n{Path(salida).name}   {t:.1f} s   {Path(salida).stat().st_size / 1e6:.1f} MB "
            f"· audio {dif:+.3f} s")
        return Path(salida)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def concatenar(planos: list[dict], carpeta: Path, salida: Path, log=print) -> Path:
    """Para el largo: los planos enteros, uno tras otro. Va por el mismo camino
    exacto que el recorte (22/9): pegar clips crudos con su AAC arrastraba el
    relleno del codificador y el sonido se corría ~30 ms por clip."""
    return recortar_y_concatenar(planos, carpeta, salida, log=log)


def mezclar(video: Path, voces: list[tuple[float, Path]], salida: Path,
            musica: Path | None = None, ambiente_db: float = -6.0,
            musica_db: float = -19.0, voz_db: float = 2.0, log=print,
            realces: list[tuple[float, float]] | None = None, realce_db: float = 9.0) -> Path:
    """Las tres capas de audio, en su lugar.

        1. lo que generó H3   viento, estática, metal. **No se descarta**: es lo
                              que el modelo hace distinto. Se le baja mientras
                              habla la voz y vuelve a subir después.
        2. la voz             de ElevenLabs, arriba de todo, sin comprimir.
        3. la música          debajo, y es la que más se corre: existe para
                              sostener, no para que se la escuche.

    `voces` son `(segundo_de_entrada, mp3)`. El ducking va por
    `sidechaincompress`, disparado por la propia voz: sube y baja exactamente
    cuando hay palabra, en vez de por automatización a mano.
    """
    video, salida = Path(video), Path(salida)
    if not voces:
        raise ErrorMontaje("no hay pistas de voz para mezclar")
    entradas = ["-i", str(video)]
    for _t, mp3 in voces:
        entradas += ["-i", str(mp3)]
    i_mus = None
    if musica:
        i_mus = len(voces) + 1
        entradas += ["-i", str(musica)]

    f = []
    for n, (t, _mp3) in enumerate(voces, start=1):
        ms = int(round(t * 1000))
        # adelay corre la pista a su segundo; asetpts la reancla desde cero.
        f.append(f"[{n}:a]aresample=48000,asetpts=PTS-STARTPTS,"
                 f"adelay={ms}|{ms},volume={voz_db}dB[v{n}]")
    todas = "".join(f"[v{n}]" for n in range(1, len(voces) + 1))
    # `apad` sobre la mezcla de voces, y no es cosmético: `sidechaincompress`
    # deja de emitir cuando la señal de disparo se acaba, así que sin esto el
    # ambiente y la música se cortan en cuanto termina la última línea. Pasó:
    # la última voz cerraba en el segundo 51 y los últimos ocho segundos del
    # video quedaban en silencio absoluto.
    f.append(f"{todas}amix=inputs={len(voces)}:normalize=0:dropout_transition=0,"
             f"apad[voz]")
    # Una copia de la voz por cada cosa que tiene que agacharse, más la que suena.
    n_copias = 3 if musica else 2
    f.append(f"[voz]asplit={n_copias}" + "".join(f"[voz{k}]" for k in range(1, n_copias + 1)))

    # Donde un personaje habla en cámara (largo narrado con diálogos, 21/9) el
    # audio de H3 ES la voz: se sube `realce_db` en esas ventanas.
    realce = ""
    if realces:
        expr = "+".join(f"between(t\\,{a:.2f}\\,{b:.2f})" for a, b in realces)
        realce = f",volume={realce_db}dB:enable='{expr}'"
    f.append(f"[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo{realce}[amb0]")
    f.append("[amb0][voz1]sidechaincompress=threshold=0.02:ratio=12:"
             "attack=25:release=350:makeup=1[ambd]")
    f.append(f"[ambd]volume={ambiente_db}dB[amb]")

    if musica:
        f.append(f"[{i_mus}:a]aresample=48000,aformat=sample_fmts=fltp:"
                 f"channel_layouts=stereo,afade=t=in:st=0:d=2[mus0]")
        f.append("[mus0][voz2]sidechaincompress=threshold=0.02:ratio=16:"
                 "attack=25:release=500:makeup=1[musd]")
        f.append(f"[musd]volume={musica_db}dB[mus]")
        f.append(f"[amb][mus][voz{n_copias}]amix=inputs=3:normalize=0[mez]")
    else:
        f.append(f"[amb][voz{n_copias}]amix=inputs=2:normalize=0[mez]")
    # `apad` antes de masterizar: sin esto, la pista de audio más corta se lleva
    # puesto el final del video. Pasó — la última línea de voz termina en 57,5 s
    # y el video quedó recortado ahí.
    #
    # Y se masteriza con `loudnorm` a -14 LUFS / -1 dBTP, que es el estándar de
    # YouTube y el mismo al que masteriza el resto del proyecto. No es opcional:
    # **el audio que genera H3 sale clipeado**, medido a +2,68 dBFS en este
    # video. Sin masterizar, esa distorsión viaja al máster final.
    f.append("[mez]apad,loudnorm=I=-14:TP=-1.0:LRA=11,aresample=48000[out]")

    salida.parent.mkdir(parents=True, exist_ok=True)
    dur = duracion(video)
    _ffmpeg(*entradas, "-filter_complex", ";".join(f),
            "-map", "0:v", "-map", "[out]", "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k", "-ac", "2",
            *(["-t", f"{dur:.3f}"] if dur else []), str(salida))
    capas = f"{len(voces)} líneas" + (" + música" if musica else "") + " sobre el audio de H3"
    log(f"{salida.name}   {capas}   {salida.stat().st_size / 1e6:.1f} MB")
    return salida


# Nombre viejo, por si algo lo llama.
def mezclar_voz(video, pistas, salida, **kw):
    return mezclar(video, pistas, salida, **kw)


def _srt_t(s: float) -> str:
    h, r = divmod(s, 3600)
    m, r = divmod(r, 60)
    return "%02d:%02d:%02d,%03d" % (h, m, int(r), round(r % 1 * 1000))


def srt(planos: list[dict], ruta: Path) -> int:
    """Subtítulos a partir de las duraciones: como nosotros elegimos cuánto dura
    cada plano, el tiempo de cada línea es una suma. No hace falta Whisper."""
    from . import voz_clip
    lineas, t0, n = [], 0.0, 0
    for p in planos:
        usa_ini = p["usa"][0] if p.get("usa") else 0.0
        dur = (p["usa"][1] - p["usa"][0]) if p.get("usa") else p["segundos"]
        if p.get("dialogo"):
            v = p.get("voz_medida")
            if v and v.get("fuente") != "nada":
                # Con la voz medida, cada línea entra cuando se dice (21/9: antes
                # una toma de 4 líneas salía como un solo bloque de 15 s).
                for a, b, texto in voz_clip.lineas_en_tiempo(v, p["dialogo"]):
                    a_, b_ = t0 + max(0.0, a - usa_ini) - 0.1, t0 + max(0.0, b - usa_ini) + 0.25
                    a_, b_ = max(t0, a_), min(t0 + dur, max(b_, a_ + 0.6))
                    n += 1
                    lineas.append(f"{n}\n{_srt_t(a_)} --> {_srt_t(b_)}\n{texto}\n")
            else:
                n += 1
                # Entra un poco después del corte y sale un poco antes del siguiente.
                lineas.append(f"{n}\n{_srt_t(t0 + 0.4)} --> {_srt_t(t0 + dur - 0.3)}\n{p['dialogo']}\n")
        t0 += dur
    Path(ruta).write_text("\n".join(lineas), encoding="utf-8-sig")
    return n


def srt_voz(lineas: list[tuple[float, float, str]], ruta: Path) -> int:
    """El SRT de la VOZ EN OFF: `(entra, sale, texto)` por línea, con los
    tiempos reales medidos sobre el mp3 que ganó — no los estimados. Es el que
    se quema en el género recap, donde el subtítulo va frase por frase."""
    out = []
    for n, (a, b, texto) in enumerate(sorted(lineas), start=1):
        out.append(f"{n}\n{_srt_t(a)} --> {_srt_t(max(b, a + 0.3))}\n{texto.strip()}\n")
    Path(ruta).write_text("\n".join(out), encoding="utf-8-sig")
    return len(out)


# Estilo de los subtítulos quemados: blanco con borde negro, centrado, en el
# tercio inferior-medio del cuadro vertical. Es donde los pone el género
# (medido en el canal de referencia): ni tapando la cara, ni pegado al borde
# donde la interfaz de TikTok los cubre.
#
# OJO con las unidades: al convertir un SRT, ffmpeg le pone al ASS una
# resolución de referencia de 384×288 y libass escala desde ahí. `MarginV` y
# `FontSize` van en ESA escala, no en píxeles del video: un MarginV=330
# "para el tercio inferior" quedó arriba del borde superior y el subtítulo
# no se veía en ningún fotograma. 70 sobre 288 ≈ 24 % desde abajo.
ESTILO_SUB = ("FontName=Arial,FontSize=11,Bold=1,PrimaryColour=&H00FFFFFF,"
              "OutlineColour=&H00000000,Outline=1.5,Shadow=0,Alignment=2,"
              "MarginV=85,MarginL=12,MarginR=12")


ESCALA_1080 = (1920, 1080)      # largos: H3 entrega 1344×768; YouTube lo lista como 720p


def quemar_srt(video: Path, srt_: Path, salida: Path, estilo: str = ESTILO_SUB,
               log=print, escala: tuple[int, int] | None = None) -> Path:
    """Quema el SRT sobre el video (recodifica el video, copia el audio). Con
    `escala` primero reescala (lanczos) y recién después quema los subtítulos,
    así el texto se dibuja nítido al tamaño final (21/9: largos a 1080p).

    Se corre con `cwd` en la carpeta del SRT y se pasa sólo el nombre: el
    filtro `subtitles` de ffmpeg se atraganta con los `:` y `\\` de una ruta
    de Windows, y escaparlos a mano falla de formas distintas según la shell.
    """
    import subprocess
    video, srt_, salida = Path(video).resolve(), Path(srt_).resolve(), Path(salida).resolve()
    filtro = f"subtitles=filename='{srt_.name}':force_style='{estilo}'"
    if escala:
        filtro = f"scale={escala[0]}:{escala[1]}:flags=lanczos," + filtro
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                        "-i", str(video), "-vf", filtro,
                        "-c:v", "libx264", "-preset", PRESET, "-crf", "17",
                        "-pix_fmt", "yuv420p", "-c:a", "copy", str(salida)],
                       capture_output=True, text=True, cwd=str(srt_.parent))
    if r.returncode:
        raise ErrorMontaje("ffmpeg (subtítulos): " + r.stderr[-800:])
    log(f"{salida.name}   subtítulos quemados   {salida.stat().st_size / 1e6:.1f} MB")
    return salida
