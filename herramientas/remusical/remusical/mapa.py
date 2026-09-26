# -*- coding: utf-8 -*-
"""
DÓNDE hay música: clasificador AudioSet (AST) sobre la MEZCLA cruda.

Cuatro detectores hechos a mano fallaron antes de éste, todos por lo mismo: un motor
también es tonal, tiene armónicos y no tiene agudos. AudioSet tiene clases separadas
para Music, Engine, Wind y Speech. Validado contra dos videos con verdad de
referencia: separación 40x música/motor, recall 95-99 %.

No hace falta separar para clasificar: se corre sobre la mezcla, y después se separa
SÓLO las regiones con música. En un vlog de 10 min eso es 2 min en vez de 10.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np

from . import config as C

_MODELO = None


def modelo():
    """Singleton: el AST se carga una vez y lo comparten mapa, estilo, elegir y guardas."""
    global _MODELO
    if _MODELO is None:
        import torch
        from transformers import AutoFeatureExtractor, ASTForAudioClassification
        fe = AutoFeatureExtractor.from_pretrained(C.AST_MODELO)
        mo = ASTForAudioClassification.from_pretrained(C.AST_MODELO).eval()
        if torch.cuda.is_available():                 # en Replicate: 1,6 s/ventana en CPU → ~20 ms en GPU
            mo = mo.to("cuda")
        L = mo.config.id2label
        grupos = {
            "musica": [i for i, n in L.items() if "music" in n.lower()],
            "motor": [i for i, n in L.items() if any(k in n.lower() for k in
                      ("engine", "motor vehicle", "motorboat", "vehicle", "idling", "accelerating"))],
            "viento": [i for i, n in L.items() if any(k in n.lower() for k in
                       ("wind", "rustling", "ocean", "waves", "water"))],
            "habla": [i for i, n in L.items() if any(k in n.lower() for k in
                      ("speech", "narration", "conversation"))],
        }
        _MODELO = (fe, mo, grupos, L)
    return _MODELO


def probabilidades(y16: np.ndarray) -> np.ndarray:
    """Vector de 527 probabilidades AudioSet para un trozo a 16 kHz."""
    import torch
    fe, mo, _, _ = modelo()
    with torch.no_grad():
        inp = fe(y16, sampling_rate=16000, return_tensors="pt")
        inp = {k: v.to(mo.device) for k, v in inp.items()}
        return torch.sigmoid(mo(**inp).logits)[0].cpu().numpy()


def curva(y16: np.ndarray, paso: float = C.AST_PASO, progreso=None) -> list[dict]:
    """p(música), p(motor), p(viento), p(habla) por ventana. t = INICIO de la ventana."""
    _, _, g, _ = modelo()
    sr = 16000
    v, h = int(C.AST_VENTANA * sr), int(paso * sr)
    n = max(0, (len(y16) - v) // h + 1)
    out = []
    for k in range(n):
        p = probabilidades(y16[k * h:k * h + v])
        out.append(dict(t=round(k * paso, 2),
                        musica=float(p[g["musica"]].max()), motor=float(p[g["motor"]].max()),
                        viento=float(p[g["viento"]].max()), habla=float(p[g["habla"]].max())))
        if progreso and k % 25 == 0:
            progreso(k / max(1, n))
    return out


def p_musica_media(y16: np.ndarray) -> float | None:
    """p(música) media sobre ventanas de 4 s. None si el trozo es demasiado corto."""
    if len(y16) < 16000:
        return None
    _, _, g, _ = modelo()
    v = int(C.AST_VENTANA * 16000)
    ps = []
    for k in range(0, max(1, len(y16) - 16000), v):
        seg = y16[k:k + v]
        if len(seg) < 2 * 16000:
            break
        ps.append(float(probabilidades(seg)[g["musica"]].max()))
    return float(np.mean(ps)) if ps else None


@dataclass
class Region:
    inicio: float
    fin: float
    etiqueta: str           # INTRO / OUTRO / CORTINA / CAMA
    p_musica: float

    @property
    def largo(self):
        return self.fin - self.inicio


def regiones(cur: list[dict], dur: float, umbral: float = C.U_MUSICA) -> list[Region]:
    """Regiones de música a partir de la curva. Rellena huecos cortos, tira islas cortas,
    funde vecinas. La ventana se atribuye a su CENTRO."""
    t = np.array([r["t"] for r in cur]) + C.AST_VENTANA / 2
    p = np.array([r["musica"] for r in cur])
    paso = float(t[1] - t[0]) if len(t) > 1 else C.AST_PASO
    es = p > umbral

    hueco = int(C.HUECO_MAX / paso)
    i = 0
    while i < len(es):
        if not es[i]:
            j = i
            while j < len(es) and not es[j]:
                j += 1
            if 0 < i < j < len(es) and (j - i) <= hueco:
                es[i:j] = True
            i = j
        else:
            i += 1

    minimo = max(1, int(C.REGION_MIN / paso))
    crudas = []
    i = 0
    while i < len(es):
        if es[i]:
            j = i
            while j + 1 < len(es) and es[j + 1]:
                j += 1
            if (j - i + 1) >= minimo:
                a = max(0.0, float(t[i] - C.AST_VENTANA / 2))
                b = min(dur, float(t[j] + C.AST_VENTANA / 2))
                crudas.append([a, b])
            i = j + 1
        else:
            i += 1

    fus = []
    for a, b in crudas:
        if fus and a - fus[-1][1] < C.FUSION_MAX:
            fus[-1][1] = b
        else:
            fus.append([a, b])

    out = []
    for a, b in fus:
        m = (t >= a) & (t < b)
        pm = float(p[m].mean()) if m.any() else 0.0
        et = ("INTRO" if a < 1.5 else "OUTRO" if b > dur - 3.0 else
              "CORTINA" if (b - a) < 10 else "CAMA")
        out.append(Region(round(a, 2), round(b, 2), et, round(pm, 3)))
    return out


def guardar(ruta: Path, cur, regs, dur):
    ruta.write_text(json.dumps(dict(duracion=dur, umbral=C.U_MUSICA,
                                    regiones=[asdict(r) for r in regs], curva=cur),
                               indent=1), encoding="utf-8")


def cargar_regiones(ruta: Path) -> list[Region]:
    d = json.loads(ruta.read_text(encoding="utf-8"))
    return [Region(**r) for r in d["regiones"]]
