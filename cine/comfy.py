"""
Envoltorio de la API de ComfyUI para el orquestador de cortometrajes.

Levanta a clase la lógica HTTP que ya estaba probada en `tools/h3_comfy.py`
contra el pod de RunPod: subida de imagen, encolado, polling y descarga. La
diferencia es que acá no hay nada del proyecto MCO — la clase recibe la URL y
el workflow, y no sabe ni le importa qué se está generando.

Principio que se hereda y no se negocia
  **Nunca se inventan nombres de nodo ni de campo.** El workflow lo exportás vos
  desde ComfyUI (Workflow › Export (API)) y el código parcha únicamente las claves
  que ese grafo ya tiene. Si un nodo no expone `duration`, no se le escribe
  `duration`. Los nodos de H3 son nuevos y sus nombres de entrada todavía se
  mueven entre versiones; adivinar rompe en silencio.

  Corré `ComfyUI.listar_nodos(wf)` la primera vez contra tu workflow real para
  ver qué IDs y qué campos hay, y atá los que haga falta a mano.
"""

from __future__ import annotations

import json
import mimetypes
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# Clases de nodo de las plantillas oficiales de ComfyUI para H3. Son pistas para
# el autodescubrimiento, no una lista cerrada: si tu grafo usa otras, pasás el ID.
CLASES_PROMPT = ("CLIPTextEncode",)
CLASES_IMAGEN = ("LoadImage",)
CLASES_SALIDA = ("SaveVideo", "CreateVideo", "SaveAnimatedWEBP", "VHS_VideoCombine")

# Ref2VA (omni-referencia, hasta 9 imágenes) y FL2VA (primer/último frame).
CLASES_REF2VA = ("MiniMaxH3ReferenceToVideo",)
CLASES_FL2VA = ("MiniMaxH3ImageToVideo", "MiniMaxH3TextToVideo")
CLASES_H3 = CLASES_REF2VA + CLASES_FL2VA


class ErrorComfy(RuntimeError):
    """Algo falló del lado de ComfyUI o del transporte."""


class ComfyUI:
    """Cliente HTTP de una instancia de ComfyUI (Vast.ai, RunPod o local).

        comfy = ComfyUI("https://x-8188.proxy.vast.ai")
        nombre = comfy.subir_imagen(Path("locacion.png"))
        hist, seg = comfy.generar(workflow, etiqueta="clip 1")
        comfy.bajar_video(hist, Path("clip_01.mp4"))
    """

    def __init__(self, url: str, cliente: str | None = None,
                 espera_max: int = 3600, poll: int = 5, timeout: int = 120):
        self.url = url.rstrip("/")
        self.cliente = cliente or "cine-" + secrets.token_hex(6)
        self.espera_max = espera_max
        self.poll = poll
        self.timeout = timeout

    # ───────────────────────────── transporte ─────────────────────────────

    def _abrir(self, req, timeout: int | None = None) -> bytes:
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            detalle = e.read().decode("utf-8", "replace")[:600]
            raise ErrorComfy(f"ComfyUI respondió {e.code} en {req.full_url}\n{detalle}")
        except urllib.error.URLError as e:
            raise ErrorComfy(
                f"No pude hablar con ComfyUI en {req.full_url}\n  {e.reason}\n"
                "  ¿La instancia está prendida y el puerto 8188 expuesto?")

    def get(self, ruta: str, params: dict | None = None, crudo: bool = False):
        full = f"{self.url}{ruta}" + (f"?{urllib.parse.urlencode(params)}" if params else "")
        data = self._abrir(urllib.request.Request(full, headers={"User-Agent": "cine/1.0"}))
        return data if crudo else json.loads(data.decode("utf-8"))

    def post(self, ruta: str, cuerpo: dict) -> dict:
        req = urllib.request.Request(
            f"{self.url}{ruta}", data=json.dumps(cuerpo).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json", "User-Agent": "cine/1.0"})
        return json.loads(self._abrir(req).decode("utf-8"))

    def vivo(self) -> bool:
        """¿Contesta? Sirve para fallar temprano antes de un lote largo."""
        try:
            self.get("/system_stats")
            return True
        except ErrorComfy:
            return False

    # ───────────────────────────── assets ─────────────────────────────

    def subir_imagen(self, ruta: Path, subcarpeta: str = "") -> str:
        """POST /upload/image. Devuelve el nombre con el que ComfyUI la guardó.

        Ese nombre es el que va en el campo `image` del LoadImage, no la ruta local.
        """
        ruta = Path(ruta)
        if not ruta.exists():
            raise ErrorComfy(f"No existe la imagen {ruta}")

        borde = "----cine-" + secrets.token_hex(12)
        tipo = mimetypes.guess_type(ruta.name)[0] or "image/png"
        partes = [
            f"--{borde}\r\n".encode(),
            f'Content-Disposition: form-data; name="image"; filename="{ruta.name}"\r\n'.encode(),
            f"Content-Type: {tipo}\r\n\r\n".encode(),
            ruta.read_bytes(),
            f"\r\n--{borde}\r\n".encode(),
            b'Content-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n',
        ]
        if subcarpeta:
            partes += [
                f"--{borde}\r\n".encode(),
                f'Content-Disposition: form-data; name="subfolder"\r\n\r\n{subcarpeta}\r\n'.encode(),
            ]
        partes.append(f"--{borde}--\r\n".encode())

        req = urllib.request.Request(
            f"{self.url}/upload/image", data=b"".join(partes), method="POST",
            headers={"Content-Type": f"multipart/form-data; boundary={borde}"})
        r = json.loads(self._abrir(req, timeout=300).decode("utf-8"))
        return f"{r['subfolder']}/{r['name']}" if r.get("subfolder") else r["name"]

    # ───────────────────────────── generación ─────────────────────────────

    def encolar(self, workflow: dict) -> str:
        r = self.post("/prompt", {"prompt": workflow, "client_id": self.cliente})
        if "error" in r:
            det = json.dumps(r.get("node_errors", r["error"]), ensure_ascii=False)[:600]
            raise ErrorComfy(f"ComfyUI rechazó el grafo:\n{det}")
        return r["prompt_id"]

    def esperar(self, pid: str, etiqueta: str = "", progreso=True) -> tuple[dict, float]:
        """Bloquea hasta que el prompt termina. Devuelve (historial, segundos)."""
        t0 = time.time()
        while True:
            hist = self.get(f"/history/{pid}")
            if pid in hist:
                estado = hist[pid].get("status", {})
                if estado.get("status_str") == "error" or not estado.get("completed", True):
                    msgs = json.dumps(estado.get("messages", []), ensure_ascii=False)[:600]
                    raise ErrorComfy(f"{etiqueta} falló en ComfyUI:\n{msgs}")
                return hist[pid], time.time() - t0

            t = time.time() - t0
            if t > self.espera_max:
                raise ErrorComfy(
                    f"{etiqueta}: {self.espera_max / 60:.0f} min sin terminar. "
                    "¿Se cayó el worker o la GPU se quedó sin VRAM?")
            if progreso:
                cola = self.get("/queue")
                corriendo = len(cola.get("queue_running", []))
                print(f"      {'generando' if corriendo else 'en cola'}… {t:5.0f}s",
                      end="\r", flush=True)
            time.sleep(self.poll)

    def generar(self, workflow: dict, etiqueta: str = "") -> tuple[dict, float]:
        """Encola y espera. Azúcar sobre encolar() + esperar()."""
        return self.esperar(self.encolar(workflow), etiqueta)

    def bajar_video(self, hist: dict, destino: Path) -> int:
        """Busca el primer video en las salidas y lo escribe. Devuelve bytes."""
        destino = Path(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        for _nid, salida in hist.get("outputs", {}).items():
            for clave in ("videos", "gifs", "images"):
                for archivo in salida.get(clave, []):
                    nombre = str(archivo.get("filename", ""))
                    if not nombre.lower().endswith((".mp4", ".webm", ".mkv", ".gif", ".webp")):
                        continue
                    data = self.get("/view", {
                        "filename": archivo["filename"],
                        "subfolder": archivo.get("subfolder", ""),
                        "type": archivo.get("type", "output")}, crudo=True)
                    destino.write_bytes(data)
                    return len(data)
        raise ErrorComfy(
            "La generación terminó pero no encontré un video en la salida.\n"
            f"Nodos de salida: {json.dumps(hist.get('outputs', {}))[:400]}")


# ───────────────────────── manipulación del workflow ─────────────────────────
#
# Funciones sueltas y no métodos: operan sobre un dict de workflow, no sobre la
# conexión. Así se pueden testear sin ComfyUI prendido.


def cargar_workflow(ruta: Path) -> dict:
    ruta = Path(ruta)
    if not ruta.exists():
        raise ErrorComfy(
            f"No existe {ruta}.\n"
            "Exportalo desde ComfyUI: abrí la plantilla de MiniMax H3, hacela andar\n"
            "una vez a mano, y después Workflow › **Export (API)**. Guardá ese JSON acá.")
    try:
        wf = json.loads(ruta.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ErrorComfy(f"{ruta} no es JSON válido: {e}")
    if not isinstance(wf, dict):
        raise ErrorComfy(
            f"{ruta.name} no tiene forma de workflow: se esperaba un objeto de "
            f"nodos y vino {type(wf).__name__}.")
    if "nodes" in wf and "last_node_id" in wf:
        raise ErrorComfy(
            f"{ruta.name} está en formato de editor, no de API.\n"
            "Volvé a exportarlo con Workflow › **Export (API)**, no con Save.")
    return wf


def copiar(workflow: dict) -> dict:
    """Copia profunda. Cada clip parte de un grafo limpio, sin arrastrar parches."""
    return json.loads(json.dumps(workflow))


def por_clase(wf: dict, clases) -> list[tuple[str, dict]]:
    return [(nid, n) for nid, n in wf.items() if n.get("class_type") in clases]


def elegir(wf: dict, clases, forzado: str | None, que: str):
    """Encuentra un nodo por clase. Si hay más de uno, exige que lo desempaten."""
    if forzado:
        if forzado not in wf:
            raise ErrorComfy(f"El workflow no tiene un nodo {forzado}. Mirá listar_nodos().")
        return forzado, wf[forzado]
    hallados = por_clase(wf, clases)
    if not hallados:
        return None, None
    if len(hallados) > 1:
        ids = ", ".join(n for n, _ in hallados)
        raise ErrorComfy(
            f"Hay {len(hallados)} nodos de {que} ({ids}) y no sé cuál usar.\n"
            "Pasá el ID a mano.")
    return hallados[0]


def seguir(wf: dict, nodo: dict, entradas, tiene: str, hondura: int = 3):
    """Camina desde `nodo` por las entradas nombradas hasta uno que tenga `tiene`.

    Un grafo de video suele traer dos CLIPTextEncode, el positivo y el negativo,
    y adivinar por clase elige mal. Seguir el cable desde el nodo de H3 no.
    """
    for clave in entradas:
        enlace = nodo.get("inputs", {}).get(clave)
        if not (isinstance(enlace, list) and enlace):
            continue
        destino = wf.get(str(enlace[0]))
        if not destino:
            continue
        if tiene in destino.get("inputs", {}):
            return str(enlace[0]), destino
        if hondura > 1:                    # el cable puede pasar por un nodo intermedio
            hallado = seguir(wf, destino, list(destino.get("inputs", {})), tiene, hondura - 1)
            if hallado[0]:
                return hallado
    return None, None


def parchar_si_esta(nodo: dict, valores: dict) -> list[str]:
    """Escribe solo las claves que el nodo ya tiene. Nunca inventa campos.

    Ignora las entradas que son una conexión a otro nodo (listas): pisar un cable
    con un literal desconecta el grafo.
    """
    puestos = []
    for clave, valor in valores.items():
        if valor is None:
            continue
        actual = nodo.get("inputs", {}).get(clave, ...)
        if actual is not ... and not isinstance(actual, list):
            nodo["inputs"][clave] = valor
            puestos.append(f"{clave}={valor}")
    return puestos


def listar_nodos(wf: dict) -> None:
    """Imprime el grafo. Correlo una vez contra tu workflow antes de automatizar."""
    print(f"── {len(wf)} nodos ──")
    for nid, n in sorted(wf.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 0):
        titulo = n.get("_meta", {}).get("title", "")
        print(f"  {nid:>4}  {n.get('class_type', '?'):34s} {titulo}")
        for clave, valor in n.get("inputs", {}).items():
            if isinstance(valor, list):
                print(f"        {clave:22s} ← nodo [{valor[0]}]")
                continue
            print(f"        {clave:22s} = {str(valor).replace(chr(10), ' ')[:70]}")
