"""
Genera los clips de video en Replicate con MiniMax H3 (`minimax/h3`).

    python tools/h3_generate.py --esquema            # el esquema real del modelo
    python tools/h3_generate.py --plan               # qué se generaría y cuánto cuesta
    python tools/h3_generate.py --id S01-P04         # un plano, con su imagen semilla
    python tools/h3_generate.py --id S01-P04 --t2v   # el mismo, sin imagen: solo texto
    python tools/h3_generate.py --todos --2k         # los 10, en 2K
    python tools/h3_generate.py --suelto "un prompt" --out prueba.mp4

Los dos modos
  **Con imagen semilla** (por defecto): busca `IMG_<id>.png` en `--imagenes`, la
  sube y manda solo el prompt de movimiento. El encuadre, la paleta y el grano
  los hereda de la imagen. Es el flujo del pipeline y el que da continuidad.
  **Sin imagen** (`--t2v`): manda ESTILO + escena + movimiento. No necesita
  generar nada en ChatGPT antes, pero cada clip inventa su propio look: sirve
  para probar el modelo, no para planos que tienen que casar entre sí.

Cuidados
  Antes de gastar un peso valida contra el esquema **real** del modelo, que baja
  una vez y cachea en `tools/.h3_esquema.json`. Si Replicate cambia un campo o
  un valor permitido, el error sale acá y no después de pagar.

  Cada predicción lanzada se anota en `.predicciones.json` en la carpeta de
  salida **antes** de esperarla. Si se corta la conexión, volvés a correr el
  mismo comando y retoma la que ya está pagada en vez de lanzar otra.

  Las imágenes se validan a 16:9, que es lo que H3 hereda de la semilla. Con
  `--recortar` recorta al centro las 3:2 que salen de ChatGPT (1536×1024 →
  1536×864) y deja el recorte al lado con sufijo `-169`.

Precio (2026-08): 768P 0,08 US$/s · 2K 0,13 US$/s. Un clip de 10 s son 0,80 o
1,30 US$; los 10 planos, 8 o 13 US$.
"""

import argparse
import json
import mimetypes
import secrets
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import h3_plan  # noqa: E402

# La consola de Windows es cp1252 y este archivo habla castellano con flechas.
for flujo in (sys.stdout, sys.stderr):
    flujo.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
MCO = ROOT / "output" / "mars-climate-orbiter"
IMAGENES = MCO / "img"        # semillas, nombradas IMG_<id>.png
SALIDA = MCO / "h3"           # carpeta propia: `veo/` tiene los clips de Veo 3
MODELO = "minimax/h3"
API = "https://api.replicate.com/v1"
CACHE_ESQUEMA = Path(__file__).parent / ".h3_esquema.json"

PRECIO = {"768P": 0.08, "2K": 0.13}   # US$ por segundo de video
ESPERA_MAX = 1800                     # s de poll antes de rendirse
POLL = 6                              # s entre consultas


# ─────────────────────────────── HTTP ───────────────────────────────

def key() -> str:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("replicate="):
                v = line.split("=", 1)[1].strip()
                if v:
                    return v
    raise SystemExit(
        "Falta la key de Replicate.\n"
        "Agregá una línea así al .env de la raíz del proyecto:\n"
        "    replicate=r8_...\n"
        "La sacás de https://replicate.com/account/api-tokens")


def pedir(k: str, metodo: str, url: str, cuerpo=None, reintentos: int = 4):
    """Llamada JSON a la API, con reintento en 429 y 5xx."""
    if not url.startswith("http"):
        url = API + url
    data = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
    for intento in range(reintentos):
        req = urllib.request.Request(url, data=data, method=metodo, headers={
            "Authorization": f"Bearer {k}",
            "Content-Type": "application/json",
            "User-Agent": "mco-pipeline/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detalle = e.read().decode("utf-8", "replace")[:400]
            if e.code in (429, 500, 502, 503, 504) and intento < reintentos - 1:
                espera = 5 * (intento + 1)
                print(f"      {e.code}, reintento en {espera}s")
                time.sleep(espera)
                continue
            if e.code == 401:
                raise SystemExit(f"Replicate rechazó la key (401): {detalle}")
            raise SystemExit(f"Error {e.code} en {metodo} {url}\n{detalle}")
        except urllib.error.URLError as e:
            if intento < reintentos - 1:
                print(f"      red: {e.reason}, reintento")
                time.sleep(5 * (intento + 1))
                continue
            raise
    raise SystemExit("sin respuesta de Replicate")


def subir(k: str, ruta: Path) -> str:
    """Sube un archivo por la Files API y devuelve su URL."""
    borde = "----h3-" + secrets.token_hex(12)
    tipo = mimetypes.guess_type(ruta.name)[0] or "application/octet-stream"
    cuerpo = b"".join([
        f"--{borde}\r\n".encode(),
        f'Content-Disposition: form-data; name="content"; filename="{ruta.name}"\r\n'.encode(),
        f"Content-Type: {tipo}\r\n\r\n".encode(),
        ruta.read_bytes(),
        f"\r\n--{borde}--\r\n".encode()])
    req = urllib.request.Request(f"{API}/files", data=cuerpo, method="POST", headers={
        "Authorization": f"Bearer {k}",
        "Content-Type": f"multipart/form-data; boundary={borde}"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read().decode("utf-8"))["urls"]["get"]
    except urllib.error.HTTPError as e:
        raise SystemExit(f"No pude subir {ruta.name}: {e.code} "
                         f"{e.read().decode('utf-8', 'replace')[:300]}")


def bajar(url: str, destino: Path) -> int:
    tmp = destino.with_suffix(destino.suffix + ".parcial")
    with urllib.request.urlopen(url, timeout=600) as r, tmp.open("wb") as f:
        while chunk := r.read(1 << 16):
            f.write(chunk)
    tmp.replace(destino)
    return destino.stat().st_size


# ──────────────────────────── esquema real ────────────────────────────

def esquema(k: str, refrescar: bool = False) -> dict:
    """Esquema de entrada del modelo. Cacheado: la API cambia poco."""
    if CACHE_ESQUEMA.exists() and not refrescar:
        return json.loads(CACHE_ESQUEMA.read_text(encoding="utf-8"))
    m = pedir(k, "GET", f"/models/{MODELO}")
    comp = (m.get("latest_version", {}).get("openapi_schema", {})
             .get("components", {}).get("schemas", {}))
    entrada = comp.get("Input", {})
    # Los enum viven en esquemas aparte referenciados por $ref; los traemos acá
    # para no tener que caminar referencias en cada validación.
    for nombre, campo in entrada.get("properties", {}).items():
        ref = campo.get("allOf", [{}])[0].get("$ref") if "allOf" in campo else campo.get("$ref")
        if ref:
            destino = comp.get(ref.rsplit("/", 1)[-1], {})
            if "enum" in destino:
                campo["enum"] = destino["enum"]
            campo.setdefault("type", destino.get("type", "string"))
        entrada["properties"][nombre] = campo
    CACHE_ESQUEMA.write_text(json.dumps(entrada, indent=2, ensure_ascii=False), encoding="utf-8")
    return entrada


def validar(entrada: dict, esq: dict) -> list[str]:
    props = esq.get("properties", {})
    if not props:
        return []                      # sin esquema no inventamos reglas
    fallos = []
    for campo, valor in entrada.items():
        if campo not in props:
            fallos.append(f"el modelo no acepta el campo «{campo}» "
                          f"(acepta: {', '.join(sorted(props))})")
            continue
        spec = props[campo]
        if "enum" in spec and valor not in spec["enum"]:
            fallos.append(f"«{campo}»={valor!r} no está permitido "
                          f"(permitidos: {spec['enum']})")
        if isinstance(valor, str) and "maxLength" in spec and len(valor) > spec["maxLength"]:
            fallos.append(f"«{campo}» tiene {len(valor)} caracteres y el máximo "
                          f"es {spec['maxLength']}")
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            if "minimum" in spec and valor < spec["minimum"]:
                fallos.append(f"«{campo}»={valor} es menor que el mínimo {spec['minimum']}")
            if "maximum" in spec and valor > spec["maximum"]:
                fallos.append(f"«{campo}»={valor} pasa el máximo {spec['maximum']}")
    for obligatorio in esq.get("required", []):
        if obligatorio not in entrada:
            fallos.append(f"falta el campo obligatorio «{obligatorio}»")
    return fallos


# ───────────────────────────── imágenes ─────────────────────────────

def revisar_imagen(ruta: Path, recortar: bool) -> Path:
    """Devuelve una imagen 16:9. H3 hereda el encuadre de la semilla."""
    try:
        from PIL import Image
    except ImportError:
        print("      (sin Pillow: no verifico el encuadre)")
        return ruta
    with Image.open(ruta) as im:
        an, al = im.size
        rel = an / al
        if abs(rel - 16 / 9) < 0.01:
            return ruta
        if not recortar:
            raise SystemExit(
                f"{ruta.name} es {an}×{al} ({rel:.2f}:1) y H3 hereda el encuadre de la "
                f"semilla. Recortá a 16:9 o pasá --recortar.")
        nueva_al = round(an * 9 / 16)
        if nueva_al > al:                       # más ancha que 16:9: recorto a lo ancho
            nuevo_an = round(al * 16 / 9)
            x = (an - nuevo_an) // 2
            caja = (x, 0, x + nuevo_an, al)
        else:
            y = (al - nueva_al) // 2
            caja = (0, y, an, y + nueva_al)
        destino = ruta.with_name(ruta.stem + "-169.png")
        im.crop(caja).save(destino)
        print(f"      recorté {an}×{al} → {caja[2]-caja[0]}×{caja[3]-caja[1]}  {destino.name}")
        return destino


def buscar_imagen(pid: str, carpeta: Path) -> Path | None:
    for patron in (f"IMG_{pid}-169.png", f"IMG_{pid}.png", f"IMG_{pid}.jpg", f"{pid}.png"):
        cand = carpeta / patron
        if cand.exists():
            return cand
    return None


# ──────────────────────────── predicciones ────────────────────────────

def registro(carpeta: Path) -> Path:
    return carpeta / ".predicciones.json"


def leer_registro(carpeta: Path) -> dict:
    f = registro(carpeta)
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def guardar_registro(carpeta: Path, reg: dict) -> None:
    registro(carpeta).write_text(json.dumps(reg, indent=2), encoding="utf-8")


def esperar(k: str, url: str, etiqueta: str) -> dict:
    t0 = time.time()
    while True:
        p = pedir(k, "GET", url)
        if p["status"] in ("succeeded", "failed", "canceled"):
            print(f"      {p['status']} en {time.time()-t0:.0f}s" + " " * 12)
            return p
        if time.time() - t0 > ESPERA_MAX:
            raise SystemExit(f"{etiqueta}: {ESPERA_MAX}s sin terminar. Sigue viva en {url}")
        print(f"      {p['status']}… {time.time()-t0:4.0f}s", end="\r", flush=True)
        time.sleep(POLL)


def url_de_salida(pred: dict) -> str:
    out = pred.get("output")
    if isinstance(out, str):
        return out
    if isinstance(out, list) and out:
        return out[0]
    if isinstance(out, dict):
        for c in ("video", "url", "output"):
            if c in out:
                return out[c]
    raise SystemExit(f"No entiendo la salida de la predicción: {out!r}")


def generar(k, esq, clave, prompt, imagen, duracion, resolucion, ratio,
            carpeta, destino, force, recortar) -> bool:
    if destino.exists() and not force:
        print(f"  =   {destino.name} ya existe")
        return True

    modo = "i2v" if imagen else "t2v"
    print(f"  ·   {clave}  {duracion}s {resolucion} {modo}  →  {destino.name}")

    # ¿quedó una predicción viva de una corrida anterior? no se paga dos veces
    reg = leer_registro(carpeta)
    if clave in reg and not force:
        print(f"      retomo la predicción {reg[clave]['id']}")
        pred = esperar(k, reg[clave]["url"], clave)
    else:
        entrada = {"prompt": prompt, "duration": duracion, "resolution": resolucion}
        if imagen:
            entrada["first_frame_image"] = subir(k, revisar_imagen(imagen, recortar))
            print(f"      semilla subida: {imagen.name}")
        else:
            entrada["ratio"] = ratio
        fallos = validar(entrada, esq)
        if fallos:
            for f in fallos:
                print(f"  X   {f}")
            return False
        pred = pedir(k, "POST", f"/models/{MODELO}/predictions", {"input": entrada})
        reg[clave] = {"id": pred["id"], "url": pred["urls"]["get"]}
        guardar_registro(carpeta, reg)     # anotada ANTES de esperarla
        pred = esperar(k, pred["urls"]["get"], clave)

    if pred["status"] != "succeeded":
        print(f"  X   {clave}: {pred['status']} — {pred.get('error')}")
        return False

    kb = bajar(url_de_salida(pred), destino) / 1024
    print(f"  OK  {destino.name:22s} {kb:8.0f} KB")
    reg = leer_registro(carpeta)
    reg.pop(clave, None)
    guardar_registro(carpeta, reg)
    return True


# ─────────────────────────────── modos ───────────────────────────────

def mostrar_plan(planos, carpeta_img, salida, resolucion, t2v, duracion) -> int:
    seg = sum(duracion or p.dur for p in planos)
    print(f"── plan · {len(planos)} clips · {seg} s · {resolucion} · "
          f"{'sin imagen semilla (t2v)' if t2v else 'con imagen semilla (i2v)'} ──")
    faltan = []
    for p in planos:
        dur = duracion or p.dur
        vid = salida / f"VID_{p.id}.mp4"
        img = buscar_imagen(p.id, carpeta_img)
        if vid.exists():
            estado = "ya generado"
        elif t2v:
            estado = f"t2v, {len(h3_plan.prompt_t2v(p))} caracteres de prompt"
        elif img:
            estado = img.name
        else:
            estado = "SIN IMAGEN SEMILLA"
            faltan.append(p.id)
        print(f"  {p.id}  {p.ini}→{p.out}  cám {p.camara}  {dur:2d}s  "
              f"{dur*PRECIO[resolucion]:5.2f} US$   {estado}")
    print(f"\n  total: {seg*PRECIO[resolucion]:.2f} US$ "
          f"({PRECIO[resolucion]:.2f} US$/s en {resolucion})")
    if faltan:
        print(f"\n  faltan {len(faltan)} semillas en {carpeta_img}")
        print(f"  nombralas IMG_<id>.png — IMG_{faltan[0]}.png, etc.")
        print("  o generá sin semilla con --t2v")
    return 0


def mostrar_esquema(esq) -> int:
    print(f"── entradas de {MODELO} ──")
    req = set(esq.get("required", []))
    for nombre, spec in sorted(esq.get("properties", {}).items(),
                               key=lambda kv: kv[1].get("x-order", 99)):
        det = []
        if "enum" in spec:
            det.append(str(spec["enum"]))
        if "default" in spec:
            det.append(f"default={spec['default']!r}")
        if "minimum" in spec or "maximum" in spec:
            det.append(f"[{spec.get('minimum', '')}..{spec.get('maximum', '')}]")
        if "maxLength" in spec:
            det.append(f"máx {spec['maxLength']} car")
        print(f" {'*' if nombre in req else ' '} {nombre:24s} "
              f"{spec.get('type', '?'):8s} {'  '.join(det)}")
        if spec.get("description"):
            print(f"     {spec['description'][:110]}")
    print("\n  * = obligatorio")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="MiniMax H3 en Replicate")
    ap.add_argument("--esquema", action="store_true", help="baja y muestra el esquema del modelo")
    ap.add_argument("--refrescar", action="store_true", help="ignora el esquema cacheado")
    ap.add_argument("--plan", action="store_true", help="qué se generaría y cuánto sale")
    ap.add_argument("--todos", action="store_true", help="los 10 planos")
    ap.add_argument("--id", action="append", help="solo este plano (repetible)")
    ap.add_argument("--suelto", metavar="PROMPT", help="un clip fuera del plan")
    ap.add_argument("--imagen", type=Path, help="imagen semilla para --suelto")
    ap.add_argument("--out", type=Path, help="archivo de salida para --suelto")
    ap.add_argument("--t2v", action="store_true", help="sin imagen semilla: solo texto")
    ap.add_argument("--imagenes", type=Path, default=IMAGENES, help="carpeta de semillas")
    ap.add_argument("--salida", type=Path, default=SALIDA, help="carpeta de salida")
    ap.add_argument("--duracion", type=int, help="segundos; por defecto los del plan")
    ap.add_argument("--2k", dest="dos_k", action="store_true", help="2K en vez de 768P")
    ap.add_argument("--ratio", default="16:9", help="encuadre cuando no hay semilla")
    ap.add_argument("--recortar", action="store_true", help="recorta las semillas a 16:9")
    ap.add_argument("--force", action="store_true", help="regenera lo que ya existe")
    args = ap.parse_args()

    resolucion = "2K" if args.dos_k else "768P"
    planos = [p for p in h3_plan.PLANOS if args.todos or not args.id or p.id in args.id]

    if args.plan:
        return mostrar_plan(planos, args.imagenes, args.salida, resolucion,
                            args.t2v, args.duracion)

    k = key()

    if args.esquema:
        return mostrar_esquema(esquema(k, refrescar=True))

    if not (args.todos or args.id or args.suelto):
        ap.error("indicá --plan, --todos, --id, --suelto o --esquema")

    esq = esquema(k, refrescar=args.refrescar)
    args.salida.mkdir(parents=True, exist_ok=True)

    if args.suelto:
        if not args.out:
            ap.error("--suelto necesita --out")
        ok = generar(k, esq, args.out.stem, args.suelto, args.imagen,
                     args.duracion or 10, resolucion, args.ratio,
                     args.salida, args.out, args.force, args.recortar)
        return 0 if ok else 1

    if args.id:
        planos = [p for p in h3_plan.PLANOS if p.id in args.id]
        if not planos:
            raise SystemExit("No conozco ese id. Los que hay: "
                             + ", ".join(p.id for p in h3_plan.PLANOS))

    seg = sum(args.duracion or p.dur for p in planos)
    print(f"── {len(planos)} clips · {seg} s · {resolucion} · "
          f"{'t2v' if args.t2v else 'i2v'} · ~{seg*PRECIO[resolucion]:.2f} US$ ──")

    hechos = fallos = 0
    for p in planos:
        img = None
        if not args.t2v:
            img = buscar_imagen(p.id, args.imagenes)
            if not img:
                print(f"  X   {p.id}: no encontré IMG_{p.id}.png en {args.imagenes}")
                fallos += 1
                continue
        prompt = h3_plan.prompt_t2v(p) if args.t2v else h3_plan.prompt_i2v(p)
        ok = generar(k, esq, p.id, prompt, img, args.duracion or p.dur,
                     resolucion, args.ratio, args.salida,
                     args.salida / f"VID_{p.id}.mp4", args.force, args.recortar)
        hechos += ok
        fallos += not ok

    print(f"\n{hechos} clips generados, {fallos} fallos")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
