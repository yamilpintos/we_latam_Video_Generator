r"""
Fase 4 — alineación forzada: de dos transcripciones a coordenadas de Warp Marker.

Qué hace
  Por cada clip con diálogo saca el audio del MP4 de H3, lo transcribe junto con
  la toma de ElevenLabs, cruza las dos listas de palabras y escribe los pares
  (tiempo en ElevenLabs → tiempo en MiniMax) que Ableton necesita para estirar la
  voz hasta calzar con la imagen.

Por qué clip por clip y no sobre el máster
  La deriva. Un error de 40 ms por clip es imperceptible en un clip y son casi
  dos segundos a los diez minutos. Alineando por clip, cada uno arranca con el
  reloj en cero y el error no se acumula.

El emparejamiento no es un zip(), y tampoco es "buscar la palabra igual"
  Las dos transcripciones no traen la misma cantidad de palabras: Whisper agrupa
  distinto, el foley del prompt de H3 le hace inventar cosas, y una toma puede
  tener una muletilla que la otra no. Pero emparejar por texto suelto es peor que
  el zip: en un diálogo, "la" o "que" aparecen ocho veces, y unir la quinta "la"
  de una pista con la segunda de la otra produce **marcadores cruzados** —
  source avanza pero target retrocede. Ableton interpola linealmente entre
  marcadores, así que un cruce no suena raro: suena al revés.

  Por eso el cruce se hace con `difflib.SequenceMatcher`, que busca las
  subsecuencias comunes **respetando el orden**. Devuelve bloques contiguos que
  coinciden, y por construcción nunca cruza. Después igual se verifica que la
  serie sea estrictamente creciente en los dos ejes y se tiran las violaciones.

Ruido y confianza
  El audio de H3 trae foley pedido a propósito, y sobre foley Whisper alucina.
  Cada palabra viene con `confidence`; por debajo de --confianza se descarta y el
  marcador se apoya en la palabra siguiente. Ableton interpola el hueco solo.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import subprocess
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from . import guion

for flujo in (sys.stdout, sys.stderr):
    flujo.reconfigure(encoding="utf-8", errors="replace")

MODELO = "small"          # base o small alcanzan: solo se usan los tiempos
CONFIANZA = 0.35          # por debajo de esto la palabra se descarta
SR = 16000                # Whisper trabaja a 16 kHz mono


class ErrorAlineacion(RuntimeError):
    """Falta un insumo o falló un paso externo."""


@dataclass(frozen=True)
class Palabra:
    texto: str
    inicio: float
    fin: float
    confianza: float

    @property
    def clave(self) -> str:
        """Forma normalizada con la que se compara: sin tildes, sin puntuación."""
        s = unicodedata.normalize("NFD", self.texto.lower())
        s = "".join(c for c in s if unicodedata.category(c) != "Mn")
        return re.sub(r"[^\w]", "", s, flags=re.UNICODE)


# ───────────────────────── paso 1: extraer el audio ─────────────────────────

def extraer_audio(mp4: Path, wav: Path) -> Path:
    """Separa la pista de H3 a WAV mono 16 kHz, que es lo que come Whisper."""
    mp4, wav = Path(mp4), Path(wav)
    if not mp4.exists():
        raise ErrorAlineacion(f"No existe el clip {mp4}")
    wav.parent.mkdir(parents=True, exist_ok=True)

    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(mp4),
         "-vn", "-acodec", "pcm_s16le", "-ar", str(SR), "-ac", "1", str(wav)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        cola = "\n".join((r.stderr or "").strip().splitlines()[-10:])
        raise ErrorAlineacion(f"No pude extraer el audio de {mp4.name}:\n{cola}")
    return wav


# ───────────────────────── paso 2: transcribir ─────────────────────────

class Transcriptor:
    """Envuelve whisper-timestamped. El modelo se carga una sola vez.

    Cargarlo dentro del bucle son varios segundos y varios cientos de MB por
    clip; con 40 clips es la diferencia entre minutos y una tarde.
    """

    def __init__(self, modelo: str = MODELO, idioma: str = "es",
                 device: str | None = None, vad: str | bool = False):
        import whisper_timestamped as wt

        self._wt = wt
        self.idioma = idioma
        self.vad = vad
        if vad == "silero":
            self._preparar_silero()
        print(f"  ·   cargando Whisper «{modelo}»…")
        self.modelo = wt.load_model(modelo, device=device)

    @staticmethod
    def _preparar_silero() -> None:
        """Descarga silero-vad aceptando el repo, y lo deja cacheado.

        whisper-timestamped lo pide por `torch.hub.load` sin `trust_repo`, y esa
        llamada abre un prompt interactivo que en un script es un EOFError. Si lo
        bajamos nosotros primero con trust_repo=True, después lo encuentra en
        caché y no pregunta nada.
        """
        import torch

        try:
            torch.hub.load(repo_or_dir="snakers4/silero-vad", model="silero_vad",
                           onnx=False, trust_repo=True)
        except Exception as e:                       # sin red, o el repo cambió
            raise ErrorAlineacion(
                f"No pude preparar silero-vad: {e}\n"
                "Corré sin --vad, o con --vad auditok, que no necesita descarga.")

    def palabras(self, wav: Path) -> list[Palabra]:
        wav = Path(wav)
        if not wav.exists():
            raise ErrorAlineacion(f"No existe el audio {wav}")
        audio = self._wt.load_audio(str(wav))
        r = self._wt.transcribe(self.modelo, audio, language=self.idioma,
                                verbose=None, vad=self.vad)
        out: list[Palabra] = []
        for seg in r.get("segments", []):
            for w in seg.get("words", []):
                texto = (w.get("text") or "").strip()
                if not texto:
                    continue
                out.append(Palabra(
                    texto=texto,
                    inicio=float(w["start"]),
                    fin=float(w["end"]),
                    confianza=float(w.get("confidence", 1.0))))
        return out


# ───────────────── paso 3: emparejar y armar los marcadores ─────────────────

@dataclass(frozen=True)
class Marcador:
    source_time_sec: float     # dónde está en la pista de ElevenLabs
    target_time_sec: float     # dónde tiene que caer, según MiniMax
    palabra: str = ""

    def json(self) -> dict:
        return {"source_time_sec": round(self.source_time_sec, 3),
                "target_time_sec": round(self.target_time_sec, 3)}


def emparejar(origen: list[Palabra], destino: list[Palabra]) -> list[tuple[Palabra, Palabra]]:
    """Cruza las dos listas respetando el orden. Devuelve pares (origen, destino).

    `autojunk=False` importa: con listas de más de 200 elementos SequenceMatcher
    empieza a tratar como "basura" los elementos frecuentes, y en un diálogo los
    frecuentes son justo los artículos que sostienen la alineación.
    """
    a = [p.clave for p in origen]
    b = [p.clave for p in destino]
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    pares = []
    for i, j, n in sm.get_matching_blocks():
        for k in range(n):
            pares.append((origen[i + k], destino[j + k]))
    return pares


def marcadores(origen: list[Palabra], destino: list[Palabra],
               confianza: float = CONFIANZA,
               anclar_cero: bool = True) -> tuple[list[Marcador], dict]:
    """Arma los Warp Markers. Devuelve (marcadores, estadísticas)."""
    pares = emparejar(origen, destino)
    stats = {"palabras_elevenlabs": len(origen), "palabras_minimax": len(destino),
             "emparejadas": len(pares), "descartadas_confianza": 0,
             "descartadas_orden": 0}

    fiables = []
    for o, d in pares:
        if o.confianza < confianza or d.confianza < confianza:
            stats["descartadas_confianza"] += 1
            continue
        fiables.append((o, d))

    ms: list[Marcador] = []
    # Anclar el arranque evita que Ableton estire todo lo anterior al primer
    # marcador para llegar hasta él; sin esto el primer fonema entra tarde.
    if anclar_cero:
        ms.append(Marcador(0.0, 0.0, "<inicio>"))

    for o, d in fiables:
        ms.append(Marcador(o.inicio, d.inicio, o.texto))

    # El cierre de la frase: sin un ancla en el final, el último tramo se estira
    # contra el fin del clip y la última sílaba queda arrastrada.
    if fiables:
        o, d = fiables[-1]
        ms.append(Marcador(o.fin, d.fin, o.texto + " <fin>"))

    # Monotonía estricta en los dos ejes. Un cruce no suena mal: suena al revés.
    limpios: list[Marcador] = []
    for m in ms:
        if limpios and (m.source_time_sec <= limpios[-1].source_time_sec
                        or m.target_time_sec <= limpios[-1].target_time_sec):
            stats["descartadas_orden"] += 1
            continue
        limpios.append(m)

    stats["marcadores"] = len(limpios)
    return limpios, stats


# ───────────────────────── paso 4: exportar ─────────────────────────

def escribir(clip_id: int, ms: list[Marcador], stats: dict, destino: Path) -> Path:
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps({
        "clip_id": clip_id,
        "markers": [m.json() for m in ms],
        "stats": stats,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    return destino


# ───────────────────────── orquestación ─────────────────────────

def _buscar_eleven(carpeta: Path, clip_id: int) -> Path | None:
    """La toma de ElevenLabs la nombra el usuario a mano: aceptamos varios anchos.

    La Fase 2 escribe clip_001.mp4 pero la spec de audio dice clip_01.wav, así que
    se prueban 2 y 3 dígitos antes de darlo por faltante.
    """
    for ancho in (2, 3):
        for ext in (".wav", ".mp3", ".flac"):
            p = carpeta / f"elevenlabs_clip_{clip_id:0{ancho}d}{ext}"
            if p.exists():
                return p
    return None


def procesar(g: guion.Guion, r, tr: Transcriptor, confianza: float = CONFIANZA,
             anclar_cero: bool = True, force: bool = False) -> int:
    """Recorre los clips con diálogo. Devuelve la cantidad de fallos."""
    con_dialogo = [c for c in g.timeline if (c.texto_dialogo_limpio or "").strip()]
    print(f"── {len(con_dialogo)} clips con diálogo de {len(g.timeline)} ──")

    hechos = fallos = 0
    for c in con_dialogo:
        salida = r.audio / f"warp_markers_clip_{c.clip_id:03d}.json"
        if salida.exists() and not force:
            print(f"  =   clip {c.clip_id:03d} ya tiene marcadores")
            continue

        eleven = _buscar_eleven(r.audio / "elevenlabs_voces", c.clip_id)
        if not eleven:
            print(f"  X   clip {c.clip_id:03d}: falta elevenlabs_clip_"
                  f"{c.clip_id:02d}.wav en {r.audio / 'elevenlabs_voces'}")
            fallos += 1
            continue

        try:
            wav_mm = r.audio / "minimax_original" / f"minimax_clip_{c.clip_id:03d}.wav"
            if not wav_mm.exists() or force:
                extraer_audio(r.mp4(c), wav_mm)

            pal_mm = tr.palabras(wav_mm)
            pal_el = tr.palabras(eleven)
            ms, stats = marcadores(pal_el, pal_mm, confianza, anclar_cero)

            if len(ms) < 2:
                print(f"  X   clip {c.clip_id:03d}: solo {len(ms)} marcadores "
                      f"({stats['emparejadas']} palabras emparejadas de "
                      f"{stats['palabras_elevenlabs']}/{stats['palabras_minimax']}). "
                      "Sin material para warpear.")
                fallos += 1
                continue

            escribir(c.clip_id, ms, stats, salida)
            print(f"  OK  clip {c.clip_id:03d}: {stats['marcadores']} marcadores "
                  f"({stats['emparejadas']} emparejadas, "
                  f"-{stats['descartadas_confianza']} por confianza, "
                  f"-{stats['descartadas_orden']} por orden)")
            hechos += 1
        except ErrorAlineacion as e:
            print(f"  X   clip {c.clip_id:03d}: {e}")
            fallos += 1

    print(f"\n{hechos} clips alineados, {fallos} fallos")
    return fallos


def main(argv=None) -> int:
    from .render import Rutas

    ap = argparse.ArgumentParser(description="Fase 4 — alineación forzada con Whisper")
    ap.add_argument("--proyecto", type=Path, default=Path("Proyecto_Cine_IA"))
    ap.add_argument("--guion", type=Path, help="default: <proyecto>/guion.json")
    ap.add_argument("--modelo", default=MODELO, help="tiny/base/small/medium/large-v3")
    ap.add_argument("--idioma", default="es")
    ap.add_argument("--device", help="cpu o cuda; default lo elige torch")
    ap.add_argument("--vad", choices=("silero", "auditok"), default=None,
                    help="detector de voz antes de transcribir; ayuda con el foley "
                         "de H3 pero silero baja un modelo la primera vez")
    ap.add_argument("--confianza", type=float, default=CONFIANZA,
                    help=f"umbral por palabra (default {CONFIANZA})")
    ap.add_argument("--sin-ancla-cero", dest="ancla", action="store_false",
                    help="no agregar el marcador en 0,0")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)

    r = Rutas(a.proyecto.resolve())
    r.crear()
    g = guion.cargar(a.guion or (r.raiz / "guion.json"))
    tr = Transcriptor(a.modelo, a.idioma, a.device, a.vad or False)
    return 1 if procesar(g, r, tr, a.confianza, a.ancla, a.force) else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ErrorAlineacion, guion.GuionInvalido) as e:
        print(f"\n  X   {e}", file=sys.stderr)
        raise SystemExit(1)
