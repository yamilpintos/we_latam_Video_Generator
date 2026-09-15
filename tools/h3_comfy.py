"""
Genera los clips en un ComfyUI remoto con MiniMax H3 — el pod de RunPod.

    python tools/h3_comfy.py --url URL --nodos           # qué hay en el workflow
    python tools/h3_comfy.py --url URL --id S01-P04      # un plano
    python tools/h3_comfy.py --url URL --todos           # los 10
    python tools/h3_comfy.py --url URL --todos --prueba  # 864×480, 10 pasos, barato

La URL es la que te da RunPod para el puerto 8188, del estilo
`https://abc123def-8188.proxy.runpod.net` (sin barra al final).

Por qué no trae el workflow adentro
  Los nodos de H3 tienen diez días. En vez de inventarte un grafo que capaz no
  carga, el script usa **el que exportás vos** desde ComfyUI: abrís la plantilla
  oficial (Template Library › Video › MiniMax H3), la hacés andar a mano una vez,
  y la exportás con *Workflow › Export (API)*. Ese JSON va a `tools/h3_workflow.json`.

  De ahí en adelante el script lo lee, le mete el prompt, la imagen semilla y la
  duración de cada plano, lo encola y baja el mp4. Nunca inventa nombres de
  nodos: parcha solo las claves que **ya existen** en el grafo que exportaste.

  Corré `--nodos` la primera vez: te lista qué hay y con qué IDs, y así atamos
  los que haga falta con --nodo-prompt / --nodo-imagen / --nodo-video.

Lo que mide
  Imprime los segundos que tardó cada clip. Ese es el número que no está en
  ninguna página y que decide si el pod conviene o no.
"""

import argparse
import json
import mimetypes
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import h3_plan  # noqa: E402

for flujo in (sys.stdout, sys.stderr):
    flujo.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
MCO = ROOT / "output" / "mars-climate-orbiter"
IMAGENES = MCO / "img"
SALIDA = MCO / "h3"
WORKFLOW = Path(__file__).parent / "h3_workflow.json"

FPS = 24                      # H3 genera siempre a 24 fps
NATIVO = (1344, 768)          # 16:9 a 0,98 MP — la resolución de calidad
PRUEBA = (864, 480)           # 16:9 a 0,4 MP — para el humo, sale rápido
ESPERA_MAX = 3600
POLL = 5

# Clases de nodo de la plantilla oficial. Si tu grafo usa otras, pasá los IDs
# a mano con --nodo-prompt / --nodo-imagen / --nodo-video.
CLASES_PROMPT = ("CLIPTextEncode",)
CLASES_IMAGEN = ("LoadImage",)
CLASES_H3 = ("MiniMaxH3ImageToVideo", "MiniMaxH3TextToVideo", "MiniMaxH3ReferenceToVideo")
CLASES_SALIDA = ("SaveVideo", "CreateVideo", "SaveAnimatedWEBP", "VHS_VideoCombine")


# ───────────────────────────── ComfyUI HTTP ─────────────────────────────

def _abrir(req, timeout=120):
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        detalle = e.read().decode("utf-8", "replace")[:600]
        raise SystemExit(f"ComfyUI respondió {e.code} en {req.full_url}\n{detalle}")
    except urllib.error.URLError as e:
        raise SystemExit(
            f"No pude hablar con ComfyUI en {req.full_url}\n  {e.reason}\n"
            "  ¿El pod está prendido y el puerto 8188 expuesto?")


def get(url: str, ruta: str, params: dict | None = None, crudo=False):
    full = f"{url}{ruta}" + (f"?{urllib.parse.urlencode(params)}" if params else "")
    data = _abrir(urllib.request.Request(full, headers={"User-Agent": "mco/1.0"}))
    return data if crudo else json.loads(data.decode("utf-8"))


def post(url: str, ruta: str, cuerpo: dict):
    req = urllib.request.Request(
        f"{url}{ruta}", data=json.dumps(cuerpo).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "mco/1.0"})
    return json.loads(_abrir(req).decode("utf-8"))


def subir_imagen(url: str, ruta: Path) -> str:
    """POST /upload/image. Devuelve el nombre con el que ComfyUI la guardó."""
    borde = "----h3-" + secrets.token_hex(12)
    tipo = mimetypes.guess_type(ruta.name)[0] or "image/png"
    cuerpo = b"".join([
        f"--{borde}\r\n".encode(),
        f'Content-Disposition: form-data; name="image"; filename="{ruta.name}"\r\n'.encode(),
        f"Content-Type: {tipo}\r\n\r\n".encode(),
        ruta.read_bytes(),
        f"\r\n--{borde}\r\n".encode(),
        b'Content-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n',
        f"--{borde}--\r\n".encode()])
    req = urllib.request.Request(
        f"{url}/upload/image", data=cuerpo, method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={borde}"})
    r = json.loads(_abrir(req, timeout=300).decode("utf-8"))
    return f"{r['subfolder']}/{r['name']}" if r.get("subfolder") else r["name"]


# ───────────────────────────── el workflow ─────────────────────────────

def cargar_workflow(ruta: Path) -> dict:
    if not ruta.exists():
        raise SystemExit(
            f"No existe {ruta}.\n"
            "Exportalo desde ComfyUI: abrí la plantilla de MiniMax H3, hacela andar\n"
            "una vez a mano, y después Workflow › Export (API). Guardá ese JSON acá.")
    wf = json.loads(ruta.read_text(encoding="utf-8"))
    if "nodes" in wf and "last_node_id" in wf:
        raise SystemExit(
            f"{ruta.name} está en formato de editor, no de API.\n"
            "Volvé a exportarlo con Workflow › **Export (API)**, no con Save.")
    return wf


def por_clase(wf: dict, clases) -> list[tuple[str, dict]]:
    return [(nid, n) for nid, n in wf.items() if n.get("class_type") in clases]


def listar_nodos(wf: dict) -> int:
    print(f"── {len(wf)} nodos ──")
    for nid, n in sorted(wf.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 0):
        titulo = n.get("_meta", {}).get("title", "")
        print(f"  {nid:>4}  {n.get('class_type','?'):32s} {titulo}")
        for clave, valor in n.get("inputs", {}).items():
            if isinstance(valor, list):
                continue                      # es una conexión a otro nodo
            texto = str(valor).replace("\n", " ")
            print(f"        {clave:22s} = {texto[:70]}")
    print("\n  Los que importan: el de prompt, el que carga la imagen y el de H3.")
    print("  Si el script no los adivina, pasalos con --nodo-prompt / --nodo-imagen.")
    return 0


def parchar_si_esta(nodo: dict, valores: dict) -> list[str]:
    """Escribe solo las claves que el nodo ya tiene. Nunca inventa campos."""
    puestos = []
    for clave, valor in valores.items():
        if clave in nodo.get("inputs", {}) and not isinstance(nodo["inputs"][clave], list):
            nodo["inputs"][clave] = valor
            puestos.append(f"{clave}={valor}")
    return puestos


def elegir(wf, clases, forzado, que) -> tuple[str, dict] | tuple[None, None]:
    if forzado:
        if forzado not in wf:
            raise SystemExit(f"El workflow no tiene un nodo {forzado}. Mirá --nodos.")
        return forzado, wf[forzado]
    hallados = por_clase(wf, clases)
    if not hallados:
        return None, None
    if len(hallados) > 1:
        ids = ", ".join(n for n, _ in hallados)
        raise SystemExit(
            f"Hay {len(hallados)} nodos de {que} ({ids}) y no sé cuál usar.\n"
            f"Corré --nodos y elegí uno con el flag correspondiente.")
    return hallados[0]


def seguir(wf, nodo, entradas, tiene, hondura=3) -> tuple[str, dict] | tuple[None, None]:
    """Camina desde `nodo` por las entradas nombradas hasta uno que tenga `tiene`.

    Un grafo de video suele traer dos CLIPTextEncode, el positivo y el negativo,
    y adivinar por clase elige mal. Seguir el cable desde el nodo de H3 no.
    """
    for clave in entradas:
        enlace = nodo.get("inputs", {}).get(clave)
        if not (isinstance(enlace, list) and enlace):
            continue
        nid = str(enlace[0])
        destino = wf.get(nid)
        if not destino:
            continue
        if tiene in destino.get("inputs", {}):
            return nid, destino
        if hondura > 1:                       # el cable puede pasar por un nodo intermedio
            hallado = seguir(wf, destino, list(destino.get("inputs", {})), tiene, hondura - 1)
            if hallado[0]:
                return hallado
    return None, None


# ───────────────────────────── generación ─────────────────────────────

def encolar(url, wf, cliente) -> str:
    r = post(url, "/prompt", {"prompt": wf, "client_id": cliente})
    if "error" in r:
        det = json.dumps(r.get("node_errors", r["error"]), ensure_ascii=False)[:600]
        raise SystemExit(f"ComfyUI rechazó el grafo:\n{det}")
    return r["prompt_id"]


def esperar(url, pid, etiqueta) -> tuple[dict, float]:
    t0 = time.time()
    while True:
        hist = get(url, f"/history/{pid}")
        if pid in hist:
            estado = hist[pid].get("status", {})
            if estado.get("status_str") == "error" or not estado.get("completed", True):
                msgs = json.dumps(estado.get("messages", []), ensure_ascii=False)[:600]
                raise SystemExit(f"{etiqueta} falló en ComfyUI:\n{msgs}")
            return hist[pid], time.time() - t0
        t = time.time() - t0
        if t > ESPERA_MAX:
            raise SystemExit(f"{etiqueta}: {ESPERA_MAX/60:.0f} min sin terminar.")
        cola = get(url, "/queue")
        corriendo = len(cola.get("queue_running", []))
        print(f"      {'generando' if corriendo else 'en cola'}… {t:5.0f}s",
              end="\r", flush=True)
        time.sleep(POLL)


def bajar_salida(url, hist, destino: Path) -> int:
    for _nid, salida in hist.get("outputs", {}).items():
        for clave in ("videos", "gifs", "images"):
            for archivo in salida.get(clave, []):
                if not str(archivo.get("filename", "")).lower().endswith(
                        (".mp4", ".webm", ".mkv", ".gif", ".webp")):
                    continue
                data = get(url, "/view", {
                    "filename": archivo["filename"],
                    "subfolder": archivo.get("subfolder", ""),
                    "type": archivo.get("type", "output")}, crudo=True)
                destino.write_bytes(data)
                return len(data)
    raise SystemExit(
        "La generación terminó pero no encontré un video en la salida.\n"
        f"Nodos de salida: {json.dumps(hist.get('outputs', {}))[:400]}")


def generar(url, base, args, clave, prompt, imagen, segundos, destino) -> bool:
    if destino.exists() and not args.force:
        print(f"  =   {destino.name} ya existe")
        return True

    wf = json.loads(json.dumps(base))          # copia limpia por plano
    an, al = (PRUEBA if args.prueba else NATIVO)
    if args.ancho:
        an, al = args.ancho, args.alto or round(args.ancho * 9 / 16)
    frames = round(segundos * FPS)

    # Primero el nodo de H3: desde él salen los cables al texto y a la imagen,
    # y seguirlos es más confiable que buscar por clase.
    nid_h3, nodo_h3 = elegir(wf, CLASES_H3, args.nodo_video, "H3")
    if not nodo_h3:
        raise SystemExit("No encontré el nodo de MiniMax H3. Mirá --nodos.")

    nid, nodo = (elegir(wf, CLASES_PROMPT, args.nodo_prompt, "prompt")
                 if args.nodo_prompt else
                 seguir(wf, nodo_h3, ("positive", "prompt", "conditioning"), "text"))
    if not nodo:
        nid, nodo = elegir(wf, CLASES_PROMPT, None, "prompt")
    if not nodo:
        raise SystemExit("El workflow no tiene nodo de texto. Mirá --nodos.")
    nodo["inputs"]["text"] = prompt

    if imagen:
        nid_img, nodo_img = (elegir(wf, CLASES_IMAGEN, args.nodo_imagen, "imagen")
                             if args.nodo_imagen else
                             seguir(wf, nodo_h3, ("first_frame", "image", "start_image"), "image"))
        if not nodo_img:
            nid_img, nodo_img = elegir(wf, CLASES_IMAGEN, None, "imagen")
        if not nodo_img:
            raise SystemExit(
                "Pasaste imagen semilla pero el workflow no carga ninguna.\n"
                "Exportá la plantilla de Image-to-Video, no la de Text-to-Video.")
        nodo_img["inputs"]["image"] = subir_imagen(url, imagen)
        print(f"      semilla subida: {imagen.name} → nodo [{nid_img}]")
    puestos = parchar_si_esta(nodo_h3, {
        "width": an, "height": al, "length": frames, "num_frames": frames,
        "duration": segundos, "steps": args.pasos} if args.pasos else {
        "width": an, "height": al, "length": frames, "num_frames": frames,
        "duration": segundos})

    print(f"  ·   {clave}  {an}×{al}  {frames} frames ({segundos}s)  →  {destino.name}")
    if puestos:
        print(f"      {nodo_h3['class_type']} [{nid_h3}]: {', '.join(puestos)}")

    pid = encolar(url, wf, args.cliente)
    hist, t = esperar(url, pid, clave)
    kb = bajar_salida(url, hist, destino) / 1024
    real = frames / FPS
    print(f"  OK  {destino.name:22s} {kb:8.0f} KB   {t:5.0f}s de generación"
          f"   ({t/real:.1f}s de cómputo por segundo de video)")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="MiniMax H3 en un ComfyUI remoto")
    ap.add_argument("--url", help="https://<pod>-8188.proxy.runpod.net")
    ap.add_argument("--workflow", type=Path, default=WORKFLOW)
    ap.add_argument("--nodos", action="store_true", help="lista el workflow y sale")
    ap.add_argument("--todos", action="store_true")
    ap.add_argument("--id", action="append")
    ap.add_argument("--suelto", metavar="PROMPT")
    ap.add_argument("--imagen", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--t2v", action="store_true", help="sin imagen semilla")
    ap.add_argument("--imagenes", type=Path, default=IMAGENES)
    ap.add_argument("--salida", type=Path, default=SALIDA)
    ap.add_argument("--duracion", type=int, help="segundos; por defecto los del plan")
    ap.add_argument("--prueba", action="store_true", help=f"{PRUEBA[0]}×{PRUEBA[1]} en vez de nativo")
    ap.add_argument("--ancho", type=int)
    ap.add_argument("--alto", type=int)
    ap.add_argument("--pasos", type=int, help="pasos de sampleo, si el nodo lo expone")
    ap.add_argument("--nodo-prompt", dest="nodo_prompt")
    ap.add_argument("--nodo-imagen", dest="nodo_imagen")
    ap.add_argument("--nodo-video", dest="nodo_video")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    args.cliente = "mco-" + secrets.token_hex(6)

    wf = cargar_workflow(args.workflow)
    if args.nodos:
        return listar_nodos(wf)

    if not args.url:
        ap.error("indicá --url, la del puerto 8188 del pod")
    args.url = args.url.rstrip("/")
    if not (args.todos or args.id or args.suelto):
        ap.error("indicá --todos, --id o --suelto")

    args.salida.mkdir(parents=True, exist_ok=True)
    an, al = (PRUEBA if args.prueba else NATIVO)
    print(f"── ComfyUI en {args.url} · {an}×{al} · "
          f"{'t2v' if args.t2v else 'i2v'} ──")

    if args.suelto:
        if not args.out:
            ap.error("--suelto necesita --out")
        ok = generar(args.url, wf, args, args.out.stem, args.suelto,
                     args.imagen, args.duracion or 10, args.out)
        return 0 if ok else 1

    planos = [p for p in h3_plan.PLANOS if args.todos or p.id in (args.id or [])]
    if not planos:
        raise SystemExit("No conozco ese id. Los que hay: "
                         + ", ".join(p.id for p in h3_plan.PLANOS))

    hechos = fallos = 0
    t0 = time.time()
    for p in planos:
        img = None
        if not args.t2v:
            img = next((c for c in (args.imagenes / f"IMG_{p.id}-169.png",
                                    args.imagenes / f"IMG_{p.id}.png",
                                    args.imagenes / f"IMG_{p.id}.jpg") if c.exists()), None)
            if not img:
                print(f"  X   {p.id}: no encontré IMG_{p.id}.png en {args.imagenes}")
                fallos += 1
                continue
        prompt = h3_plan.prompt_t2v(p) if args.t2v else h3_plan.prompt_i2v(p)
        hechos += generar(args.url, wf, args, p.id, prompt, img,
                          args.duracion or p.dur, args.salida / f"VID_{p.id}.mp4")

    print(f"\n{hechos} clips, {fallos} fallos, {(time.time()-t0)/60:.1f} min de pod")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
