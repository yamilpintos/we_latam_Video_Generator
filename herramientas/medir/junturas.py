"""Las junturas: último cuadro del clip N contra primer cuadro del clip N+1,
con el tramo que el montaje usó de verdad. Distingue los dos tipos de corte:

  MISMO DIBUJO  — los dos clips salen de la misma imagen: el personaje vuelve
                  a la pose inicial («rebobina»).
  DIBUJO NUEVO  — otra generación del mismo lugar: puede moverse el set.
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

PC = Path(r"C:\Users\Yamil\Desktop\youtube proyect\mis-videos\sangre")
S = Path(__file__).parent
W = 330

d = json.loads((PC / "proyecto.json").read_text(encoding="utf-8"))
planos = d["planos"]
dib = {p["id"]: (p.get("dibujo") or f"sb_{p['id']}.png") for p in planos}


def cuadro(pid: str, t: float) -> np.ndarray | None:
    f = next(iter((PC / "clips").glob(f"{pid}_*.mp4")), None)
    if not f:
        return None
    cap = cv2.VideoCapture(str(f))
    cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, t) * 1000)
    ok, fr = cap.read()
    cap.release()
    return fr if ok else None


filas, notas = [], []
for a, b in zip(planos, planos[1:]):
    if a["funcion"].split(" · ")[0] != b["funcion"].split(" · ")[0]:
        continue                      # cambio de escena: ahí el corte es legítimo
    mismo = dib[a["id"]] == dib[b["id"]]
    usa_a = a.get("usa") or [0, a["segundos"]]
    usa_b = b.get("usa") or [0, b["segundos"]]
    fa, fb = cuadro(a["id"], usa_a[1] - 0.08), cuadro(b["id"], usa_b[0] + 0.02)
    if fa is None or fb is None:
        continue
    dif = float(np.abs(cv2.resize(fa, (160, 90)).astype(float)
                       - cv2.resize(fb, (160, 90)).astype(float)).mean())
    notas.append((f"{a['id']}→{b['id']}", "mismo dibujo" if mismo else "DIBUJO NUEVO", dif))
    if len(filas) < 6 and (dif > 12 or not mismo):
        par = []
        for im, et in ((fa, f"{a['id']} último"), (fb, f"{b['id']} primero")):
            im = cv2.resize(im, (W, int(W * im.shape[0] / im.shape[1])))
            cv2.putText(im, et, (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 4)
            cv2.putText(im, et, (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
            par.append(im)
        sep = np.full((par[0].shape[0], 6, 3), (0, 200, 255), np.uint8)
        etiqueta = np.zeros((par[0].shape[0], 150, 3), np.uint8)
        cv2.putText(etiqueta, "mismo" if mismo else "DIBUJO", (6, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.putText(etiqueta, "dibujo" if mismo else "NUEVO", (6, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.putText(etiqueta, f"dif {dif:.0f}", (6, 92), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 220, 255), 1)
        filas.append(np.hstack([etiqueta] + [par[0], sep, par[1]]))

mismos = [x[2] for x in notas if x[1] == "mismo dibujo"]
nuevos = [x[2] for x in notas if x[1] != "mismo dibujo"]
print(f"junturas dentro de una escena: {len(notas)}")
print(f"  mismo dibujo: {len(mismos)} · salto visual promedio {np.mean(mismos):.1f}" if mismos else "")
print(f"  dibujo nuevo: {len(nuevos)} · salto visual promedio {np.mean(nuevos):.1f}" if nuevos else "")
print("\npeores:")
for n, t, v in sorted(notas, key=lambda x: -x[2])[:8]:
    print(f"  {n:12s} {t:14s} {v:5.1f}")
if filas:
    cv2.imwrite(str(S / "junturas.jpg"), np.vstack(filas), [cv2.IMWRITE_JPEG_QUALITY, 82])
    print("\n", S / "junturas.jpg")
