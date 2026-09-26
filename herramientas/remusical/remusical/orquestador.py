# -*- coding: utf-8 -*-
"""
El comando único: procesar(video) → carpeta `re-musical/` al lado del video con
  · re-musical <nombre>.mp4          el video con la música nueva
  · <nombre> - voz.flac              la voz original aislada
  · <nombre> - musica original.flac  la música que se quitó
  · <nombre> - musica nueva.flac     la música que se puso
  · <nombre> - informe.json          mapa, takes, guardas, créditos

Cadena:  audio → mapa (AudioSet) → separar regiones → por región: estilo → N takes →
         elegir → montar → guardas → (reintentos) → exportar

Cuando una guarda rechaza, el orquestador corrige lo que esa guarda señala y vuelve
a montar (sin regenerar salvo que haga falta). Si tras REINTENTOS sigue rechazado,
igual exporta, con el prefijo REVISAR y el informe explicando qué falló: un archivo
marcado es mejor que un fallo mudo.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np

from . import config as C
from .audio import (a16k, duracion_video, escribir, extraer_audio, leer48, mmss)
from . import mapa, separar, estilo, generar, elegir, montar, guardas


def _nada(*a, **k):
    pass


def takes_bajo_demanda(i: int, prompt: str, largo: float, ref: np.ndarray, trabajo: Path,
                       takes_max: int = C.TAKES_MAX, dist_max: float = C.DIST_MAX,
                       excluir: set | None = None, log=print,
                       _generar=None, _elegir=None, _leer=None) -> tuple[dict, list[str], list[dict]]:
    """Genera de a UN take y para en cuanto uno sirve.

    Devuelve (takes_audio, orden, tabla). `orden` son los candidatos de mejor a peor
    (sin los descalificados ni los de `excluir`). Si tras takes_max ninguno sirve,
    devuelve igual el menos malo: un archivo marcado REVISAR vale más que un fallo.
    Los `_generar/_elegir/_leer` inyectables existen para probar esto sin gastar."""
    gen = _generar or generar.generar
    eli = _elegir or elegir.elegir
    lee = _leer or leer48
    excluir = excluir or set()
    takes: dict[str, np.ndarray] = {}
    tabla: list[dict] = []
    orden: list[str] = []
    # takes que ya existen en disco (reintentos) cuentan y no se vuelven a pagar
    for dst in sorted((trabajo / "takes").glob(f"r{i+1}_take*.wav")):
        takes[dst.stem.split("_")[1]] = lee(dst)
    while True:
        if takes:
            orden, tabla = eli(ref, takes, log=log)
            orden = [t for t in orden if t not in excluir]
            if orden:
                mejor = next(f for f in tabla if f["take"] == orden[0])
                if mejor["distancia"] is not None and mejor["distancia"] <= dist_max:
                    return takes, orden, tabla
                log(f"    take {orden[0]}: distancia {mejor['distancia']:.3f} > {dist_max}: pido otro")
            else:
                log(f"    ningún take sirve todavía ({len(takes)} generados)")
        if len(takes) >= takes_max:
            break
        k = len(takes) + 1
        dst = trabajo / "takes" / f"r{i+1}_take{k}.wav"
        gen(prompt, largo, dst, log=log)
        takes[f"take{k}"] = lee(dst)
    if not orden:                     # nada pasó: el menos malo, para que salga marcado
        orden = [f["take"] for f in sorted(tabla, key=lambda f: (f["distancia"] is None, f["distancia"] or 9, -f["p_musica"]))
                 if f["take"] not in excluir] or [f["take"] for f in tabla]
        log(f"    región {i+1}: tras {len(takes)} takes ninguno convence; va el menos malo ({orden[0]})")
    return takes, orden, tabla


def procesar(video: Path, salida_dir: Path | None = None, separar_completo: bool = False,
             takes_por_region: int = C.TAKES_MAX, log=print, progreso=_nada) -> dict:
    """progreso(etapa: str, fraccion: float) se llama a medida que avanza."""
    video = Path(video)
    t0 = time.time()
    nombre = video.stem
    salida_dir = Path(salida_dir) if salida_dir else video.parent / C.PREFIJO
    trabajo = C.TRABAJO / nombre
    trabajo.mkdir(parents=True, exist_ok=True)
    informe = dict(video=str(video), inicio=time.strftime("%Y-%m-%d %H:%M:%S"),
                   version=__import__("remusical").__version__)

    try:
        creditos_antes = generar.saldo()
    except Exception:
        creditos_antes = None

    # ---------- 1. audio ----------
    progreso("audio", 0.02)
    dur = duracion_video(video)
    log(f"[{nombre}] {mmss(dur)}")
    wav = extraer_audio(video, trabajo / "audio48.wav")
    mezcla = leer48(wav)
    informe["duracion_s"] = round(dur, 2)

    # ---------- 2. mapa ----------
    # Se cachea por hash del audio: clasificar 27 min son 45 min de CPU, y un reintento
    # del mismo video no tiene por qué repetirlos.
    progreso("mapa", 0.05)
    from .audio import hash_archivo
    h_audio = hash_archivo(wav)
    mapa_json = trabajo / "mapa.json"
    cur = None
    if mapa_json.exists():
        try:
            d = json.loads(mapa_json.read_text(encoding="utf-8"))
            if d.get("hash_audio") == h_audio and d.get("umbral") == C.U_MUSICA:
                cur = d["curva"]
                log("  mapa: reutilizo el del intento anterior (mismo audio)")
        except Exception:
            cur = None
    if cur is None:
        log("  clasificando la mezcla (AudioSet)…")
        y16 = a16k(mezcla)
        cur = mapa.curva(y16, C.AST_PASO, progreso=lambda f: progreso("mapa", 0.05 + 0.15 * f))
    regs = mapa.regiones(cur, dur)
    mapa.guardar(mapa_json, cur, regs, dur)
    d = json.loads(mapa_json.read_text(encoding="utf-8"))
    d["hash_audio"] = h_audio
    mapa_json.write_text(json.dumps(d, indent=1), encoding="utf-8")
    for i, r in enumerate(regs):
        log(f"  región {i+1}: {mmss(r.inicio)} → {mmss(r.fin)}  {r.largo:5.1f}s  {r.etiqueta}  p={r.p_musica}")
    informe["regiones"] = [asdict(r) for r in regs]
    if not regs:
        log("  sin música detectada: no hay nada que reemplazar")
        informe.update(estado="SIN_MUSICA", fin=time.strftime("%Y-%m-%d %H:%M:%S"))
        salida_dir.mkdir(parents=True, exist_ok=True)
        (salida_dir / f"{nombre} - informe.json").write_text(json.dumps(informe, indent=2), encoding="utf-8")
        return informe

    # ---------- 3. separar ----------
    progreso("separar", 0.20)
    if separar_completo:
        log("  separando el archivo ENTERO (lento)…")
        voz, inst = separar.separar_todo(mezcla, trabajo, log=log)
    else:
        voz, inst = separar.separar_regiones(mezcla, regs, trabajo, log=log)
    progreso("separar", 0.55)

    # ---------- 3b. sub-segmentar: una región larga son varias PISTAS ----------
    # "La ruta de la seda": 93 % del video es música, en regiones de hasta 12 min sin
    # hueco. Se parten donde cambia la música (timbre/armonía), con tope de 240 s: el
    # pedido es "similar pero distinto en cada parte", y Eleven Music no pasa de 600 s.
    from . import segmentar
    regs = segmentar.subdividir(regs, inst, log=log)
    informe["pistas"] = [asdict(r) for r in regs]
    log(f"  {len(regs)} pistas a reemplazar")

    # ---------- 4. por región: estilo → takes → elegir ----------
    takes_audio: dict[int, dict[str, np.ndarray]] = {}
    orden: dict[int, list[str]] = {}
    refs, prompts, largos = {}, {}, {}
    informe["por_region"] = []
    # Una película tiene UNA paleta: si en una región la música está tan tapada por la
    # narración que AudioSet no distingue instrumentos (el outro del viajero), toma los
    # de las otras regiones antes de caer al genérico.
    descs = []
    for r in regs:
        a, b = int(r.inicio * C.SR), int(r.fin * C.SR)
        descs.append(estilo.describir(inst[a:b]))
    union_i = [x for d in descs for x in d["instrumentos"]]
    union_g = [x for d in descs for x in d["generos"]]
    for d in descs:
        if not d["instrumentos"] and union_i:
            d["instrumentos"] = list(dict.fromkeys(union_i))[:3]
            d["heredado"] = True
        if not d["generos"] and union_g:
            d["generos"] = list(dict.fromkeys(union_g))[:2]
    # ---------- 4b. UN TEMA POR ESTILO, generados en paralelo ----------
    from . import temas
    from concurrent.futures import ThreadPoolExecutor
    grupos = temas.agrupar(regs, descs)
    log("  temas:\n" + temas.resumen(grupos, regs))
    informe["temas"] = []
    temas_audio: dict[int, dict[str, np.ndarray]] = {}
    temas_orden: dict[int, list[str]] = {}
    grupo_de: dict[int, int] = {}
    for gi, g in enumerate(grupos):
        rep = max(g.pistas, key=lambda i: regs[i].largo)          # la pista más larga representa al grupo
        a, b = int(regs[rep].inicio * C.SR), int(regs[rep].fin * C.SR)
        g.prompt = estilo.prompt(g.desc, g.etiqueta, g.largo_tema)
        refs[gi] = elegir.referencia(mezcla[a:b], voz[a:b], inst[a:b])
        prompts[gi], largos[gi] = g.prompt, g.largo_tema
        for i in g.pistas:
            grupo_de[i] = gi

    def _tema(gi):
        g = grupos[gi]
        return gi, takes_bajo_demanda(1000 + gi, prompts[gi], largos[gi], refs[gi], trabajo,
                                      takes_max=takes_por_region, log=log)
    hechos = 0
    with ThreadPoolExecutor(max_workers=int(os.getenv("REMUSICAL_GEN_PARALELO", "4"))) as ex:
        for gi, (ta, orden_g, tabla) in ex.map(_tema, range(len(grupos))):
            temas_audio[gi], temas_orden[gi] = ta, orden_g
            hechos += 1
            progreso("generar", 0.55 + 0.20 * hechos / len(grupos))
            g = grupos[gi]
            informe["temas"].append(dict(tema=gi + 1, etiqueta=g.etiqueta, pistas=[i + 1 for i in g.pistas],
                                         largo_s=g.largo_tema, estilo=g.desc, prompt=g.prompt,
                                         takes=tabla, elegido=orden_g[0]))

    def _repartir():
        """Cada pista recibe su tramo del tema elegido de su grupo."""
        for i, r in enumerate(regs):
            gi = grupo_de[i]
            g = grupos[gi]
            tema = temas_audio[gi][temas_orden[gi][0]]
            largo_i = r.largo + temas.HOLGURA.get(r.etiqueta, 3.0)
            takes_audio[i] = {temas_orden[gi][0]: temas.tramo(tema, g.desde.get(i), largo_i)}
            orden[i] = [temas_orden[gi][0]]
    _repartir()
    for i, r in enumerate(regs):
        gi = grupo_de[i]
        informe["por_region"].append(dict(region=i + 1, etiqueta=r.etiqueta, estilo=descs[i],
                                          tema=gi + 1, desde_s=grupos[gi].desde.get(i),
                                          elegido=temas_orden[gi][0]))

    # ---------- 5. montar + guardas, con reintentos ----------
    idx = {i: 0 for i in range(len(regs))}
    probados: dict[int, set] = {}
    ajuste: dict[int, float] = {}
    res = []
    for intento in range(C.REINTENTOS + 1):
        progreso("montar", 0.75 + 0.05 * intento)
        log(f"  montaje (intento {intento+1})")
        elegidos = {i: takes_audio[i][orden[i][min(idx[i], len(orden[i]) - 1)]] for i in range(len(regs))}
        sal, detalle, mus_nueva = montar.montar(mezcla, voz, inst, regs, elegidos, ajuste, log=log)
        log("  nivelando pista por pista contra la música original:")
        sal, mus_nueva, niveles = montar.nivelar_hasta(mezcla, voz, inst, mus_nueva, regs, log=log)
        progreso("guardas", 0.85 + 0.03 * intento)
        res = guardas.auditar(mezcla, sal, voz, regs, inst=inst, musica=mus_nueva)
        for g in res:
            log(f"    {'PASA   ' if g['ok'] else 'RECHAZA'} {g['n']} {g['nombre']:<16} {g['detalle']}")
        if guardas.entregable(res):
            break
        g = {r["n"]: r for r in res}
        if not g[1]["ok"] or not g[2]["ok"]:
            raise RuntimeError("guarda 1/2 rechaza: es un bug de montaje, no se reintenta")
        cambio = False
        if not g[3]["ok"] and g[3].get("region_lado"):
            i, lado = g[3]["region_lado"]
            from dataclasses import replace
            r = regs[i]
            otros = [o for o in regs if o is not r]
            # la ampliación se frena en la región vecina: nunca se pisan
            if lado == "antes":
                tope = max([0.0] + [o.fin for o in otros if o.fin <= r.inicio])
                nuevo = max(tope, r.inicio - 8.0)
                regs[i] = replace(r, inicio=nuevo, contiguo=(abs(nuevo - tope) < 0.5) if hasattr(r, "contiguo") else False)
            else:
                tope = min([dur] + [o.inicio for o in otros if o.inicio >= r.fin])
                regs[i] = replace(r, fin=min(tope, r.fin + 8.0))
            if regs[i].inicio == r.inicio and regs[i].fin == r.fin:
                log(f"    ->región {i+1}: no se puede ampliar {lado} (pegada a la vecina); se deja")
            else:
                log(f"    ->región {i+1} ampliada {lado}: {mmss(regs[i].inicio)}-{mmss(regs[i].fin)}")
                voz, inst = separar.separar_regiones(mezcla, regs, trabajo, log=log)   # caché
                cambio = True
        if not g[4]["ok"] and g[4].get("region") is not None:
            i = g[4]["region"]
            nivel_i = next((m["nivel_base_db"] for m in detalle if m["region"] == i), 0.0)
            if nivel_i < -45.0:
                log(f"    ->región {i+1}: música a {nivel_i:.0f} dB bajo narración, inaudible en el original también; no se cicla el take")
            else:
                # el tema del grupo de esa pista queda excluido y se genera OTRO (bajo
                # demanda, hasta el máximo); todas las pistas del grupo se reparten de nuevo
                gi = grupo_de[i]
                usado = temas_orden[gi][0]
                excl = probados.setdefault(gi, set())
                excl.add(usado)
                temas_audio[gi], temas_orden[gi], tabla = takes_bajo_demanda(
                    1000 + gi, prompts[gi], largos[gi], refs[gi], trabajo, takes_max=takes_por_region,
                    excluir=excl, log=log)
                for t in informe["temas"]:
                    if t["tema"] == gi + 1:
                        t["takes"], t["elegido"] = tabla, temas_orden[gi][0]
                if temas_orden[gi][0] != usado:
                    _repartir()
                    log(f"    ->tema {gi+1}: ahora va {temas_orden[gi][0]} (pistas {[j+1 for j in grupos[gi].pistas]})")
                    cambio = True
        if not g[5]["ok"]:
            if g[5].get("por_pista"):
                # la nivelación por pista ya iteró hasta 3 veces: si igual no entra en ±3 dB,
                # repetir el montaje no cambia nada; sale marcado REVISAR con el detalle
                log("    ->nivel: la pista no converge tras nivelar; se deja marcado")
            else:
                for i in range(len(regs)):
                    ajuste[i] = ajuste.get(i, 0.0) - g[5]["desvio"]
                log(f"    ->nivel corregido {-g[5]['desvio']:+.1f} dB")
                cambio = True
        if not g[6]["ok"]:
            for i in range(len(regs)):
                ajuste[i] = ajuste.get(i, 0.0) - 1.0
            cambio = True
        if not cambio:
            break

    ok = guardas.entregable(res)
    informe["guardas"] = [{k: v for k, v in g.items() if k in ("n", "nombre", "ok", "detalle")} for g in res]
    informe["montaje"] = detalle
    informe["regiones_finales"] = [asdict(r) for r in regs]
    informe["estado"] = "ENTREGABLE" if ok else "REVISAR"

    # ---------- 6. exportar ----------
    progreso("exportar", 0.95)
    salida_dir.mkdir(parents=True, exist_ok=True)
    pref = C.PREFIJO if ok else "REVISAR"
    wav_sal = trabajo / "audio_nuevo.wav"
    escribir(wav_sal, sal)
    mp4 = salida_dir / f"{pref} {nombre}.mp4"
    subprocess.run([C.FFMPEG, "-y", "-v", "error", "-i", str(video), "-i", str(wav_sal),
                    "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "320k",
                    "-movflags", "+faststart", str(mp4)], check=True)
    dentro = np.zeros(len(mezcla), bool)
    for r in regs:
        dentro[int(r.inicio * C.SR):int(r.fin * C.SR)] = True
    escribir(salida_dir / f"{nombre} - voz.flac", voz, formato="PCM_16")
    escribir(salida_dir / f"{nombre} - musica original.flac", np.where(dentro[:, None], inst, 0.0), formato="PCM_16")
    escribir(salida_dir / f"{nombre} - musica nueva.flac", mus_nueva, formato="PCM_16")
    if separar_completo:
        escribir(salida_dir / f"{nombre} - ambiente.flac", np.where(dentro[:, None], 0.0, inst), formato="PCM_16")
    informe["salidas"] = sorted(p.name for p in salida_dir.glob(f"*{nombre}*"))
    informe["nota_stems"] = ("stems completos" if separar_completo else
                             "voz y música original sólo dentro de las regiones con música (±12 s); "
                             "el resto del stem es silencio. Para stems completos: --completo")

    try:
        creditos_despues = generar.saldo()
        informe["creditos_eleven"] = (creditos_antes - creditos_despues) if creditos_antes is not None else None
    except Exception:
        informe["creditos_eleven"] = None
    informe["segundos"] = round(time.time() - t0, 1)
    informe["fin"] = time.strftime("%Y-%m-%d %H:%M:%S")
    (salida_dir / f"{nombre} - informe.json").write_text(json.dumps(informe, indent=2, ensure_ascii=False), encoding="utf-8")
    progreso("listo", 1.0)
    log(f"  {informe['estado']}  ->{mp4}   ({informe['segundos']/60:.1f} min)")
    return informe
