"""Prueba de motores de imagen para la réplica de «danza peligrosa» (14/9/2026).

La competencia se decide en las caras, y la cara la pone el primer fotograma,
no H3. Antes de dibujar 72 encuadres se comparan los modelos de imagen de
OpenAI con los mismos cuatro cuadros:

  1. hoja de Hannah (sin referencias)
  2. hoja de Jack   (sin referencias)
  3. encuadre B: Hannah en contrapicado con el cuchillo en el cuello (ref: su hoja)
  4. los dos de perfil, cara a cara                     (ref: las dos hojas)

Guarda cada PNG, el tiempo y el `usage` que devuelve la API (para sacar el
costo real), y anota los rechazos del filtro en vez de reventar.

    /c/Python314/python -X utf8 -u mis-videos/replica-danza/prueba-motores/prueba.py [modelo ...]
"""
import base64, json, mimetypes, secrets, ssl, sys, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

AQUI = Path(__file__).parent
RAIZ = AQUI.parents[2]
ENV = {k.strip(): v.strip().strip('"') for k, v in
       (l.split("=", 1) for l in (RAIZ / ".env").read_text(encoding="utf-8").splitlines() if "=" in l)}
CTX = ssl.create_default_context(cafile=str(RAIZ / "certs" / "ca-bundle-avast.pem"))
API = "https://api.openai.com/v1/images"
MODELOS = sys.argv[1:] or ["gpt-image-2", "gpt-image-2.5-flare", "gpt-image-2.5-sunburst"]

ESTILO = ("Photorealistic still from a premium streaming romance-thriller series, shot on a "
          "full-frame digital cinema camera with an 85mm lens, shallow depth of field, natural "
          "skin texture with pores and fine peach fuzz, no beauty retouching, believable "
          "performances, warm practical light, subtle film grain.")
SIN_TEXTO = "A single film frame: no text, no captions, no borders, no watermark, no logo."

HANNAH = ("Hannah, 22, a slim ballet dancer with a delicate oval face, light freckles across the "
          "nose, hazel-green eyes, honey-brown hair in a messy low bun with loose strands around "
          "her face, a faint smudge of farm dirt on one cheekbone, soft red lips; she wears an "
          "oversized worn brown-and-cream plaid flannel shirt hanging open over a pale pink "
          "camisole leotard, frayed light-blue denim cut-off shorts over pale pink tights, and "
          "chunky pink ribbed leg warmers")
JACK = ("Jack, 32, a tall lean man, dangerously handsome, dark brown hair swept back with short "
        "sides, a trimmed dark beard, pale blue-grey eyes, a fresh spray of blood across the "
        "left side of his forehead and cheekbone, black ink tattoos creeping up the side of his "
        "neck; he wears a crisp white dress shirt with the sleeves rolled to the forearm, a black "
        "leather shoulder-holster harness over it, and black fingerless leather driving gloves")

HOJA = ("{estilo} CHARACTER REFERENCE SHEET on a plain mid-grey studio background with even soft "
        "light: the same person shown four times side by side, full body, head to toe — front "
        "view, three-quarter view, side profile, and back view — with identical face, hair and "
        "clothing in all four. {quien}. Neutral standing pose, arms relaxed. Every detail sharp: "
        "this sheet is the reference for every other shot. {sin_texto}")

CUADROS = {
    "1-hoja-hannah": (HOJA.format(estilo=ESTILO, quien=HANNAH, sin_texto=SIN_TEXTO), []),
    "2-hoja-jack": (HOJA.format(estilo=ESTILO, quien=JACK, sin_texto=SIN_TEXTO), []),
    "3-encuadre-B": (
        f"{ESTILO} Use the first image as the character reference: same face, hair and clothes. "
        f"VERTICAL 9:16 frame. CLOSE UP from a LOW ANGLE of {HANNAH}, inside a vintage luxury "
        "train compartment: dark mahogany ceiling beams and cream ceiling panels above her, a "
        "bright window behind. Her face fills the upper half of the frame, tilted back, eyes "
        "glossy with tears, lips parted in fear. A man's black-gloved hand holds the flat of a "
        "black tactical knife against the side of her neck; his shoulder in a white shirt is a "
        "soft out-of-focus shape at the lower left edge. Tense, frightened, not injured. "
        f"{SIN_TEXTO}", ["1-hoja-hannah"]),
    "4-perfiles": (
        f"{ESTILO} Use the first image for the woman and the second image for the man: same "
        "faces, hair and clothes. VERTICAL 9:16 frame. CLOSE TWO-SHOT IN PROFILE inside a vintage "
        "luxury train compartment, a window with white lace curtains glowing with daylight behind "
        f"them. On the left, {JACK}, facing right; on the right, {HANNAH}, facing left. Their "
        "faces are a hand's width apart, both framed from the chest up. He holds a black tactical "
        "knife upright between them in his gloved hand, blade pointing up, not touching her; she "
        "stares back at him, breath held, defiant and scared. "
        f"{SIN_TEXTO}", ["1-hoja-hannah", "2-hoja-jack"]),
}


def pedir(modelo, prompt, refs):
    if refs:
        borde = "----rd-" + secrets.token_hex(12)
        partes = []
        for campo, valor in (("model", modelo), ("prompt", prompt), ("size", "1024x1536"), ("n", "1")):
            partes += [f"--{borde}\r\n".encode(),
                       f'Content-Disposition: form-data; name="{campo}"\r\n\r\n'.encode(),
                       f"{valor}\r\n".encode()]
        for r in refs:
            partes += [f"--{borde}\r\n".encode(),
                       f'Content-Disposition: form-data; name="image[]"; filename="{r.name}"\r\n'.encode(),
                       f"Content-Type: {mimetypes.guess_type(r.name)[0] or 'image/png'}\r\n\r\n".encode(),
                       r.read_bytes(), b"\r\n"]
        partes.append(f"--{borde}--\r\n".encode())
        req = urllib.request.Request(API + "/edits", data=b"".join(partes), method="POST", headers={
            "Authorization": f"Bearer {ENV['openai']}",
            "Content-Type": f"multipart/form-data; boundary={borde}"})
    else:
        req = urllib.request.Request(API + "/generations", method="POST", data=json.dumps(
            {"model": modelo, "prompt": prompt, "size": "1024x1536", "n": 1}).encode(), headers={
            "Authorization": f"Bearer {ENV['openai']}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, context=CTX, timeout=600) as r:
        return json.load(r)


def correr(modelo):
    d = AQUI / modelo
    d.mkdir(exist_ok=True)
    reg = []
    for nombre, (prompt, refs) in CUADROS.items():
        png = d / f"{nombre}.png"
        faltan = [d / f"{x}.png" for x in refs if not (d / f"{x}.png").exists()]
        if png.exists():
            reg.append({"cuadro": nombre, "estado": "ya estaba"})
            continue
        if faltan:
            reg.append({"cuadro": nombre, "estado": "sin referencia", "falta": [f.name for f in faltan]})
            continue
        t0 = time.time()
        try:
            r = pedir(modelo, prompt, [d / f"{x}.png" for x in refs])
            dato = r["data"][0]
            png.write_bytes(base64.b64decode(dato["b64_json"]) if dato.get("b64_json")
                            else urllib.request.urlopen(dato["url"], context=CTX).read())
            reg.append({"cuadro": nombre, "estado": "ok", "segundos": round(time.time() - t0, 1),
                        "usage": r.get("usage")})
        except urllib.error.HTTPError as e:
            reg.append({"cuadro": nombre, "estado": f"HTTP {e.code}",
                        "detalle": e.read().decode("utf-8", "replace")[:500]})
            if e.code in (401, 429) or "billing" in reg[-1]["detalle"] or "quota" in reg[-1]["detalle"]:
                break
        print(f"[{modelo}] {nombre}: {reg[-1]['estado']} {reg[-1].get('segundos', '')}", flush=True)
    (d / "registro.json").write_text(json.dumps(reg, indent=1, ensure_ascii=False), encoding="utf-8")
    return modelo, reg


if __name__ == "__main__":
    with ThreadPoolExecutor(len(MODELOS)) as ex:
        for modelo, reg in ex.map(correr, MODELOS):
            print(f"\n== {modelo}")
            for x in reg:
                print("  ", json.dumps(x, ensure_ascii=False)[:600])
