"""
El guion técnico que devuelve el LLM, tipado y validado.

El JSON de la Fase 1 es la fuente de verdad de todo el pipeline: de acá salen los
prompts que van a H3, los subtítulos de la Fase 3 y los textos que se alinean
contra ElevenLabs en la Fase 4. Un campo mal escrito no se nota hasta tres fases
después, cuando ya gastaste GPU. Por eso se valida al cargar y no en el camino.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

# Extensiones que aceptamos como asset madre, en orden de preferencia.
EXTENSIONES = (".png", ".jpg", ".jpeg", ".webp")

# Duración fija de todo clip, en segundos. Es el contrato del pipeline entero:
# la Fase 2 le pide exactamente esto a H3, la Fase 3 calcula los tiempos del SRT
# como (clip_id-1)*15 → clip_id*15 sin medir nada, y el LLM ya escribe la
# `hoja_de_ruta_sonora` asumiéndolo. Si esto cambia, cambia en un solo lugar —
# tenerlo duplicado hace que los subtítulos se corran y no se note hasta el máster.
SEGUNDOS_POR_CLIP = 15

HARD_CUT = "hard_cut"
CONTINUOUS = "continuous_frame"
TRANSICIONES = (HARD_CUT, CONTINUOUS)


class GuionInvalido(ValueError):
    """El JSON no cumple el contrato. El mensaje dice qué clip y qué campo."""


@dataclass(frozen=True)
class Clip:
    clip_id: int
    locacion_id: str
    personajes_presentes: list[str]
    prompt_video_minimax: str
    prompt_audio_minimax: str
    texto_dialogo_limpio: str
    tipo_transicion: str

    @property
    def encadenado(self) -> bool:
        """¿Arranca en el último frame del clip anterior? Decide FL2VA vs Ref2VA."""
        return self.tipo_transicion == CONTINUOUS

    @property
    def escena(self) -> str:
        """Carpeta de salida. Agrupamos por locación, que es lo que corta escena."""
        return self.locacion_id


@dataclass
class Guion:
    personajes: dict[str, str] = field(default_factory=dict)
    locaciones: dict[str, str] = field(default_factory=dict)
    timeline: list[Clip] = field(default_factory=list)
    hoja_de_ruta_sonora: list[dict] = field(default_factory=list)

    def clip(self, clip_id: int) -> Clip:
        for c in self.timeline:
            if c.clip_id == clip_id:
                return c
        raise KeyError(f"No hay clip {clip_id} en el timeline")


def cargar(ruta: Path) -> Guion:
    """Lee y valida el JSON del LLM. Lanza GuionInvalido con el detalle."""
    ruta = Path(ruta)
    if not ruta.exists():
        raise GuionInvalido(f"No existe el guion {ruta}")
    try:
        crudo = json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise GuionInvalido(f"{ruta.name} no es JSON válido: {e}")

    assets = crudo.get("assets_requeridos", {})
    personajes = assets.get("personajes", {}) or {}
    locaciones = assets.get("locaciones", {}) or {}

    bruto = crudo.get("timeline")
    if not isinstance(bruto, list) or not bruto:
        raise GuionInvalido("El guion no tiene un `timeline` con al menos un clip")

    obligatorios = ("clip_id", "locacion_id", "prompt_video_minimax",
                    "prompt_audio_minimax", "texto_dialogo_limpio", "tipo_transicion")

    timeline: list[Clip] = []
    vistos: set[int] = set()
    for i, c in enumerate(bruto):
        faltan = [k for k in obligatorios if k not in c]
        if faltan:
            raise GuionInvalido(
                f"El clip #{i} (posición en el timeline) no trae: {', '.join(faltan)}")

        cid = c["clip_id"]
        if not isinstance(cid, int):
            raise GuionInvalido(f"clip_id debe ser entero, vino {cid!r}")
        if cid in vistos:
            raise GuionInvalido(f"clip_id {cid} está repetido en el timeline")
        vistos.add(cid)

        if c["tipo_transicion"] not in TRANSICIONES:
            raise GuionInvalido(
                f"Clip {cid}: tipo_transicion {c['tipo_transicion']!r} no es "
                f"ninguno de {TRANSICIONES}")

        # El primer clip no tiene de dónde heredar un frame: encadenarlo es un
        # error del LLM, y si no se corta acá revienta recién en el render.
        if i == 0 and c["tipo_transicion"] == CONTINUOUS:
            raise GuionInvalido(
                f"Clip {cid} es el primero del timeline y pide {CONTINUOUS}, "
                "pero no hay clip anterior del que sacar el frame.")

        if c["locacion_id"] not in locaciones:
            raise GuionInvalido(
                f"Clip {cid}: locacion_id {c['locacion_id']!r} no está declarada "
                "en assets_requeridos.locaciones")

        presentes = c.get("personajes_presentes", []) or []
        for p in presentes:
            if p not in personajes:
                raise GuionInvalido(
                    f"Clip {cid}: el personaje {p!r} no está en "
                    "assets_requeridos.personajes")

        timeline.append(Clip(
            clip_id=cid,
            locacion_id=c["locacion_id"],
            personajes_presentes=list(presentes),
            prompt_video_minimax=c["prompt_video_minimax"],
            prompt_audio_minimax=c["prompt_audio_minimax"],
            texto_dialogo_limpio=c["texto_dialogo_limpio"],
            tipo_transicion=c["tipo_transicion"]))

    return Guion(personajes=personajes, locaciones=locaciones, timeline=timeline,
                 hoja_de_ruta_sonora=crudo.get("hoja_de_ruta_sonora", []) or [])


def buscar_asset(carpeta: Path, asset_id: str) -> Path | None:
    """Encuentra `asset_id` con cualquiera de las extensiones aceptadas."""
    for ext in EXTENSIONES:
        p = carpeta / f"{asset_id}{ext}"
        if p.exists():
            return p
    return None


def faltantes(g: Guion, assets_madre: Path) -> list[str]:
    """Qué PNGs hay que generar antes de poder renderizar. Vacío = todo listo.

    Es la verificación de la Fase 1, pero vive acá porque la regla de qué asset
    corresponde a qué id es del guion, no del orquestador.
    """
    falta = []
    for pid in g.personajes:
        if not buscar_asset(assets_madre / "personajes", pid):
            falta.append(f"personajes/{pid}")
    for lid in g.locaciones:
        if not buscar_asset(assets_madre / "locaciones", lid):
            falta.append(f"locaciones/{lid}")
    return falta
