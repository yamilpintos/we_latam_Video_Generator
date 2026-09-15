"""
Fase 2 — el bucle de render contra ComfyUI en Vast.ai.

Recorre el timeline del guion y por cada clip decide **por dónde entra la imagen**:

    hard_cut          → nodo Ref2VA. Entran la locación y los personajes de la
                        escena como referencias (H3 acepta hasta 9 imágenes).
                        FL2VA queda vacío: el clip arranca de cero.

    continuous_frame  → nodo FL2VA. Se saca el último fotograma del MP4 anterior
                        con OpenCV y va como primer frame. Las referencias no se
                        mandan: la continuidad la da el frame, y sumar referencias
                        encima pelea contra ella.

El estado se guarda clip a clip en `estado_render.json`. Si se corta la conexión,
se cae el pod o lo matás vos, la próxima corrida retoma donde quedó en vez de
volver a pagar GPU por lo ya hecho.

Nota sobre el workflow
  Este módulo no inventa nombres de nodo. Necesita un workflow exportado con
  *Workflow › Export (API)* desde tu ComfyUI. Corré primero:

      python -m cine.render --workflow tools/h3_workflow.json --nodos

  para ver qué trae el grafo, y atá los IDs con --nodo-ref2va / --nodo-fl2va /
  --nodo-prompt si el autodescubrimiento no los encuentra solo.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import comfy, frames, guion

for flujo in (sys.stdout, sys.stderr):
    flujo.reconfigure(encoding="utf-8", errors="replace")

FPS = 24                       # H3 genera siempre a 24 fps
NATIVO = (1344, 768)           # 16:9 al lado corto 768 que valida MiniMax
PRUEBA = (864, 480)            # para el humo, sale rápido y barato

# La duración vive en guion.py porque la comparte con la Fase 3: el SRT calcula
# los tiempos suponiéndola y no midiendo el MP4. Si acá se renderizan clips de
# otro largo, los subtítulos quedan corridos sin que nada avise.
DURACION = guion.SEGUNDOS_POR_CLIP

# H3 genera audio nativo. Sin esto inventa música y voces en inglés que después
# pelean con las pistas de ElevenLabs.
SIN_MUSICA = "NO MUSIC."


# ───────────────────────────── rutas del proyecto ─────────────────────────────

@dataclass(frozen=True)
class Rutas:
    """La estructura de /Proyecto_Cine_IA, resuelta desde una raíz."""
    raiz: Path

    @property
    def assets(self) -> Path: return self.raiz / "1_assets_madre"
    @property
    def personajes(self) -> Path: return self.assets / "personajes"
    @property
    def locaciones(self) -> Path: return self.assets / "locaciones"
    @property
    def clips(self) -> Path: return self.raiz / "2_clips_generados"
    @property
    def audio(self) -> Path: return self.raiz / "3_audio_procesado"
    @property
    def final(self) -> Path: return self.raiz / "4_render_final"
    @property
    def estado(self) -> Path: return self.raiz / "estado_render.json"
    @property
    def temp(self) -> Path: return self.raiz / "2_clips_generados" / "_frames"

    def crear(self) -> None:
        for d in (self.personajes, self.locaciones, self.assets / "estilo",
                  self.clips, self.audio / "minimax_original",
                  self.audio / "elevenlabs_voces", self.final, self.temp):
            d.mkdir(parents=True, exist_ok=True)

    def mp4(self, c: guion.Clip) -> Path:
        return self.clips / f"escena_{c.escena}" / f"clip_{c.clip_id:03d}.mp4"


# ───────────────────────────── checkpoints ─────────────────────────────

@dataclass
class Estado:
    """`estado_render.json` — qué clips ya están y cuánto costaron."""
    ruta: Path
    hechos: dict[str, dict] = field(default_factory=dict)

    @classmethod
    def cargar(cls, ruta: Path) -> "Estado":
        ruta = Path(ruta)
        if ruta.exists():
            try:
                d = json.loads(ruta.read_text(encoding="utf-8"))
                return cls(ruta, d.get("clips", {}))
            except json.JSONDecodeError:
                print(f"  !   {ruta.name} ilegible, se empieza de cero")
        return cls(ruta)

    def guardar(self) -> None:
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        total = sum(c.get("segundos", 0) for c in self.hechos.values())
        self.ruta.write_text(json.dumps({
            "clips": self.hechos,
            "clips_hechos": len(self.hechos),
            "segundos_de_gpu": round(total, 1),
        }, indent=2, ensure_ascii=False), encoding="utf-8")

    def esta(self, clip_id: int, destino: Path) -> bool:
        """Hecho = anotado y con el MP4 todavía en disco."""
        return str(clip_id) in self.hechos and destino.exists()

    def anotar(self, clip_id: int, destino: Path, segundos: float, bytes_: int) -> None:
        self.hechos[str(clip_id)] = {
            "archivo": str(destino),
            "segundos": round(segundos, 1),
            "kb": round(bytes_ / 1024),
        }
        self.guardar()


# ───────────────────────── resolución de nodos ─────────────────────────

@dataclass
class NodosH3:
    """Qué nodos del workflow hay que tocar, resueltos una sola vez."""
    ref2va: str | None = None
    fl2va: str | None = None
    prompt_video: str | None = None
    prompt_audio: str | None = None
    imagenes: list[str] = field(default_factory=list)

    def describir(self) -> str:
        return (f"Ref2VA=[{self.ref2va}] FL2VA=[{self.fl2va}] "
                f"prompt=[{self.prompt_video}] audio=[{self.prompt_audio}] "
                f"LoadImage={self.imagenes or '—'}")


def resolver(wf: dict, forzados: dict) -> NodosH3:
    """Encuentra los nodos que hay que parchar, sin inventar ninguno."""
    n = NodosH3()

    nid_ref, _ = comfy.elegir(wf, comfy.CLASES_REF2VA, forzados.get("ref2va"), "Ref2VA")
    nid_fl, _ = comfy.elegir(wf, comfy.CLASES_FL2VA, forzados.get("fl2va"), "FL2VA")
    n.ref2va, n.fl2va = nid_ref, nid_fl
    if not (nid_ref or nid_fl):
        raise comfy.ErrorComfy(
            "El workflow no tiene ningún nodo de MiniMax H3.\n"
            "Exportá la plantilla oficial (Template Library › Video › MiniMax H3) "
            "con Workflow › Export (API). Corré --nodos para ver qué hay.")

    # El prompt se busca siguiendo el cable desde el nodo de H3: adivinar por
    # clase elige mal cuando el grafo trae positivo y negativo.
    ancla = wf[nid_ref or nid_fl]
    nid_p, _ = comfy.seguir(wf, ancla, ("positive", "prompt", "conditioning"), "text")
    n.prompt_video = forzados.get("prompt") or nid_p
    if not n.prompt_video:
        nid_p, _ = comfy.elegir(wf, comfy.CLASES_PROMPT, None, "prompt")
        n.prompt_video = nid_p

    # El prompt de audio es un segundo campo de texto, si el grafo lo expone.
    nid_a, _ = comfy.seguir(wf, ancla, ("audio_prompt", "audio_text", "audio"), "text")
    n.prompt_audio = forzados.get("audio") or nid_a

    n.imagenes = [nid for nid, _ in comfy.por_clase(wf, comfy.CLASES_IMAGEN)]
    return n


# ───────────────────────────── render ─────────────────────────────

def _referencias(c: guion.Clip, r: Rutas) -> list[Path]:
    """Locación primero, después los personajes. H3 acepta hasta 9."""
    imgs = []
    loc = guion.buscar_asset(r.locaciones, c.locacion_id)
    if loc:
        imgs.append(loc)
    for pid in c.personajes_presentes:
        p = guion.buscar_asset(r.personajes, pid)
        if p:
            imgs.append(p)
    return imgs[:9]


def preparar(wf: dict, c: guion.Clip, r: Rutas, n: NodosH3, cli: comfy.ComfyUI,
             anterior: Path | None, ancho: int, alto: int,
             segundos: int) -> tuple[dict, str]:
    """Parcha una copia del grafo para este clip. Devuelve (workflow, modo)."""
    wf = comfy.copiar(wf)
    frames_n = round(segundos * FPS)

    # Prompts. El de audio lleva siempre NO MUSIC.
    if n.prompt_video:
        wf[n.prompt_video]["inputs"]["text"] = c.prompt_video_minimax
    audio = c.prompt_audio_minimax
    if SIN_MUSICA.rstrip(".").lower() not in audio.lower():
        audio = f"{audio.rstrip()} {SIN_MUSICA}".strip()
    if n.prompt_audio:
        wf[n.prompt_audio]["inputs"]["text"] = audio

    # Ruta de la imagen: encadenado va por FL2VA, corte seco por Ref2VA.
    if c.encadenado:
        if not anterior or not anterior.exists():
            raise comfy.ErrorComfy(
                f"Clip {c.clip_id} pide {guion.CONTINUOUS} pero no encuentro el MP4 "
                f"anterior ({anterior}). ¿Se saltó un clip?")
        if not n.fl2va:
            raise comfy.ErrorComfy(
                f"Clip {c.clip_id} pide {guion.CONTINUOUS} pero el workflow no tiene "
                "nodo FL2VA. Exportá la plantilla de Image-to-Video.")
        semilla = r.temp / f"ultimo_{c.clip_id - 1:03d}.png"
        frames.ultimo_frame(anterior, semilla)
        nodo_h3 = wf[n.fl2va]
        destino_img, _ = comfy.seguir(wf, nodo_h3, ("first_frame", "image", "start_image"), "image")
        if not destino_img:
            raise comfy.ErrorComfy(
                f"El nodo FL2VA [{n.fl2va}] no tiene un LoadImage conectado. Mirá --nodos.")
        wf[destino_img]["inputs"]["image"] = cli.subir_imagen(semilla)
        print(f"      frame de continuidad: {semilla.name} → nodo [{destino_img}]")
        modo = "FL2VA"
    else:
        if not n.ref2va:
            raise comfy.ErrorComfy(
                f"Clip {c.clip_id} pide {guion.HARD_CUT} pero el workflow no tiene "
                "nodo Ref2VA. Exportá la plantilla de Reference-to-Video (R2V).")
        refs = _referencias(c, r)
        if not refs:
            raise comfy.ErrorComfy(
                f"Clip {c.clip_id}: no encontré ninguna imagen para "
                f"{c.locacion_id} ni {c.personajes_presentes} en {r.assets}")
        # Los LoadImage colgados del nodo Ref2VA, en orden de grafo.
        slots = [nid for nid in n.imagenes
                 if comfy.seguir(wf, wf[n.ref2va], list(wf[n.ref2va].get("inputs", {})),
                                 "image", hondura=4)[0]]
        slots = slots or n.imagenes
        if len(refs) > len(slots):
            print(f"      ! {len(refs)} referencias y {len(slots)} slots de imagen "
                  f"en el grafo: se mandan las primeras {len(slots)}")
        for nid, img in zip(slots, refs):
            wf[nid]["inputs"]["image"] = cli.subir_imagen(img)
            print(f"      referencia: {img.name} → nodo [{nid}]")
        modo = "Ref2VA"

    # Dimensiones y duración, solo donde el nodo ya tenga el campo.
    nodo_h3 = wf[n.fl2va if c.encadenado else n.ref2va]
    puestos = comfy.parchar_si_esta(nodo_h3, {
        "width": ancho, "height": alto, "length": frames_n,
        "num_frames": frames_n, "duration": segundos})
    if puestos:
        print(f"      {nodo_h3['class_type']}: {', '.join(puestos)}")

    return wf, modo


def render_timeline(g: guion.Guion, r: Rutas, cli: comfy.ComfyUI, wf: dict,
                    n: NodosH3, ancho: int, alto: int, segundos: int,
                    force: bool = False, solo: list[int] | None = None) -> int:
    """El bucle de la Fase 2. Devuelve la cantidad de fallos.

    `solo` limita qué clips se generan, pero el recorrido sigue siendo el timeline
    completo: un clip encadenado necesita el MP4 del anterior aunque ese anterior
    no esté en la lista, y esa dependencia se resuelve por posición, no por filtro.
    """
    estado = Estado.cargar(r.estado)
    hechos = saltados = fallos = 0
    t0 = time.time()

    for i, c in enumerate(g.timeline):
        if solo and c.clip_id not in solo:
            continue
        destino = r.mp4(c)
        anterior = r.mp4(g.timeline[i - 1]) if i else None

        if estado.esta(c.clip_id, destino) and not force:
            print(f"  =   clip {c.clip_id:03d} ya está ({destino.name})")
            saltados += 1
            continue

        print(f"  ·   clip {c.clip_id:03d}  {c.tipo_transicion:16s} "
              f"{c.locacion_id} {c.personajes_presentes}")
        try:
            grafo, modo = preparar(wf, c, r, n, cli, anterior, ancho, alto, segundos)
            hist, seg = cli.generar(grafo, f"clip {c.clip_id}")
            b = cli.bajar_video(hist, destino)
            estado.anotar(c.clip_id, destino, seg, b)
            print(f"  OK  clip {c.clip_id:03d} [{modo}]  {b / 1024:8.0f} KB  "
                  f"{seg:5.0f}s de GPU  ({seg / segundos:.1f}s por segundo de video)")
            hechos += 1
        except (comfy.ErrorComfy, ValueError) as e:
            print(f"  X   clip {c.clip_id:03d}: {e}")
            fallos += 1
            # Un clip encadenado necesita el MP4 del anterior. Si este falló, los
            # que dependen de él van a fallar igual: mejor cortar y que lo mire.
            if i + 1 < len(g.timeline) and g.timeline[i + 1].encadenado:
                print("      el clip siguiente es encadenado y depende de este. Corto acá.")
                break

    print(f"\n{hechos} generados, {saltados} ya estaban, {fallos} fallos, "
          f"{(time.time() - t0) / 60:.1f} min")
    return fallos


# ───────────────────────────── CLI ─────────────────────────────

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Fase 2 — render de clips con H3 en ComfyUI")
    ap.add_argument("--proyecto", type=Path, default=Path("Proyecto_Cine_IA"),
                    help="raíz del proyecto (default: ./Proyecto_Cine_IA)")
    ap.add_argument("--guion", type=Path, help="JSON del LLM (default: <proyecto>/guion.json)")
    ap.add_argument("--workflow", type=Path, default=Path("tools/h3_workflow.json"))
    ap.add_argument("--url", help="https://<instancia>-8188.proxy.vast.ai")
    ap.add_argument("--nodos", action="store_true", help="lista el workflow y sale")
    ap.add_argument("--validar", action="store_true", help="valida guion y assets, no renderiza")
    ap.add_argument("--prueba", action="store_true", help=f"{PRUEBA[0]}×{PRUEBA[1]}, rápido")
    ap.add_argument("--ancho", type=int)
    ap.add_argument("--alto", type=int)
    ap.add_argument("--duracion", type=int, default=DURACION, help="segundos por clip (4–15)")
    ap.add_argument("--clip", type=int, action="append", dest="clips",
                    help="generar solo estos clip_id (repetible). Para los "
                         "encadenados, el anterior tiene que existir ya.")
    ap.add_argument("--force", action="store_true", help="regenera aunque estén hechos")
    ap.add_argument("--nodo-ref2va", dest="ref2va")
    ap.add_argument("--nodo-fl2va", dest="fl2va")
    ap.add_argument("--nodo-prompt", dest="prompt")
    ap.add_argument("--nodo-audio", dest="audio")
    a = ap.parse_args(argv)

    # --nodos solo mira el grafo; --validar solo mira el guion. Ninguno de los
    # dos necesita lo del otro, y pedirlo obliga a tener ComfyUI resuelto para
    # revisar un JSON.
    if a.nodos:
        comfy.listar_nodos(comfy.cargar_workflow(a.workflow))
        return 0

    r = Rutas(a.proyecto.resolve())
    r.crear()
    g = guion.cargar(a.guion or (r.raiz / "guion.json"))

    falta = guion.faltantes(g, r.assets)
    print(f"── {len(g.timeline)} clips · {len(g.locaciones)} locaciones · "
          f"{len(g.personajes)} personajes ──")
    if falta:
        print(f"  X   faltan {len(falta)} assets madre en {r.assets}:")
        for f in falta:
            print(f"        {f}")
        return 1
    # Los clip_id se chequean acá, antes de tocar el workflow o la red: es gratis
    # y evita descubrir un id mal tipeado después de conectarse.
    if a.clips:
        ids = {c.clip_id for c in g.timeline}
        raros = [i for i in a.clips if i not in ids]
        if raros:
            ap.error(f"el guion no tiene los clip_id {raros}; hay {sorted(ids)}")
        print(f"  solo los clips {sorted(a.clips)}")

    if a.validar:
        print("  OK  guion válido y todos los assets presentes")
        return 0

    if not a.url:
        ap.error("indicá --url, la del puerto 8188 de tu instancia")

    wf = comfy.cargar_workflow(a.workflow)
    n = resolver(wf, {"ref2va": a.ref2va, "fl2va": a.fl2va,
                      "prompt": a.prompt, "audio": a.audio})
    print(f"  nodos: {n.describir()}")
    if not n.prompt_audio:
        print("  !   no encontré nodo de prompt de audio: el audio sale con el "
              "default del grafo (revisá que no meta música)")

    ancho, alto = (PRUEBA if a.prueba else NATIVO)
    if a.ancho:
        ancho, alto = a.ancho, a.alto or round(a.ancho * 9 / 16)

    cli = comfy.ComfyUI(a.url)
    if not cli.vivo():
        print(f"  X   ComfyUI no contesta en {cli.url}")
        return 1
    print(f"── ComfyUI en {cli.url} · {ancho}×{alto} · {a.duracion}s por clip ──")

    return 1 if render_timeline(g, r, cli, wf, n, ancho, alto, a.duracion,
                                a.force, a.clips) else 0


if __name__ == "__main__":
    # Los errores de contrato (guion mal, workflow ausente, nodo que no está) son
    # cosas que el usuario tiene que corregir, no bugs: se imprimen como mensaje,
    # no como traceback.
    try:
        raise SystemExit(main())
    except (comfy.ErrorComfy, guion.GuionInvalido) as e:
        print(f"\n  X   {e}", file=sys.stderr)
        raise SystemExit(1)
