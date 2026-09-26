# -*- coding: utf-8 -*-
"""
Prueba el camino Drive → Vast → bucket sin credenciales reales ni alquilar nada.

  A. la máquina baja de `drive://<id>` usando la cuenta de servicio (no el token del usuario)
  B. sube cada resultado con la URL FIRMADA que venía en el manifiesto: sin credenciales
  C. un archivo de más de 5 GB no se puede subir por PUT simple → se marca, no se pierde
  D. si el manifiesto no trae URLs firmadas, cae al camino viejo (s3:// con credenciales)
  E. `nombres_salida` firma los dos prefijos posibles (re-musical y REVISAR)
  F. el video se borra de la máquina al terminar (no queda material del cliente)

Correr:  cd apps/remusical && python -m tests.test_drive_bucket
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from remusical.nube import tanda as T, bucket as B  # noqa: E402

fallos = []


def check(c, m):
    print(("  OK   " if c else "  FALLA") + " " + m)
    if not c:
        fallos.append(m)


print("\nE. nombres de salida que hay que firmar")
n = B.nombres_salida("Ep 1.mp4")
check("re-musical Ep 1.mp4" in n and "REVISAR Ep 1.mp4" in n and "Ep 1 - voz.flac" in n,
      f"{len(n)} nombres, incluye los dos prefijos posibles")
check("Ep 1 - ambiente.flac" not in n and "Ep 1 - ambiente.flac" in B.nombres_salida("Ep 1.mp4", completo=True),
      "el ambiente sólo se firma con --completo")

# ---------------------------------------------------------------- dobles
bajados, subidos, con_credencial = [], [], []


class DriveFalso:
    @staticmethod
    def bajar(file_id, dst, progreso=None):
        bajados.append(file_id)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(b"video")
        return dst


def subir_con_url_falso(url, archivo, log=print):
    if archivo.stat().st_size > B.LIMITE_PUT_SIMPLE:
        return False
    subidos.append((archivo.name, url))
    return True


def procesar_falso(video, salida_dir, separar_completo=False, takes_por_region=3, log=None, progreso=None):
    salida_dir.mkdir(parents=True, exist_ok=True)
    base = Path(video).stem
    (salida_dir / f"re-musical {base}.mp4").write_bytes(b"x" * 100)
    (salida_dir / f"{base} - voz.flac").write_bytes(b"x" * 50)
    (salida_dir / f"{base} - informe.json").write_text("{}")
    return dict(estado="ENTREGABLE", creditos_eleven=1234, segundos=42, regiones_finales=[])


def correr(video_extra: dict, con_firmas: bool, subidor=None) -> dict:
    bajados.clear(); subidos.clear(); con_credencial.clear()
    tmp = Path(tempfile.mkdtemp())
    v = dict(id="v001", origen="drive://ABC123", nombre="Ep 1.mp4", **video_extra)
    m = dict(nombre="t", destino=str(tmp / "salida"), videos=[v])
    import remusical.nube.drive_sa as ds
    orig_bajar, orig_subir_url, orig_subir = ds.bajar, B.subir_con_url, T.subir
    ds.bajar = DriveFalso.bajar
    B.subir_con_url = subidor or subir_con_url_falso
    T.subir = lambda p, d, log=print: (con_credencial.append(p.name), f"{d}/{p.name}")[1]
    sys.modules["remusical.orquestador"].procesar = procesar_falso
    try:
        t = T.Tanda(m, trabajo=tmp / "trabajo", log=lambda x: None)
        t.correr(workers=1)
        est = t.estado["videos"]["v001"]
        est["_wdir_existe"] = (tmp / "trabajo" / "v001").exists()
        return est
    finally:
        ds.bajar, B.subir_con_url, T.subir = orig_bajar, orig_subir_url, orig_subir
        shutil.rmtree(tmp, ignore_errors=True)


import remusical.orquestador  # noqa: E402  (para poder reemplazar procesar)

print("\nA+B. baja de Drive por cuenta de servicio y sube por URL firmada")
firmas = {n: f"https://bucket.ejemplo/{n}?firma=xyz" for n in B.nombres_salida("Ep 1.mp4")}
est = correr(dict(subidas=firmas), con_firmas=True)
check(bajados == ["ABC123"], f"bajó de Drive el id {bajados}")
check(len(subidos) == 3 and all(u.startswith("https://bucket.ejemplo/") for _, u in subidos),
      f"subió {len(subidos)} archivos, todos por URL firmada")
check(not con_credencial, "no se usó ninguna credencial de bucket en la máquina")
check(est["estado"] == "listo", f"estado {est['estado']}")

print("\nC. archivo de más de 5 GB: se marca, no se pierde en silencio")
est = correr(dict(subidas=firmas), con_firmas=True,
             subidor=lambda url, archivo, log=print: False)   # simula el tope de 5 GB
check(est.get("sin_subir") and len(est["sin_subir"]) == 3, f"marcados sin subir: {est.get('sin_subir')}")

print("\nD. sin URLs firmadas cae al camino con credenciales")
est = correr({}, con_firmas=False)
check(len(con_credencial) == 3 and not subidos, f"{len(con_credencial)} subidos con credencial (camino viejo)")

print("\nF. el video se borra de la máquina")
check(est["_wdir_existe"] is False, "la carpeta de trabajo del video se borró al terminar")

print()
if fallos:
    print(f"FALLARON {len(fallos)}:", *fallos, sep="\n  ")
    sys.exit(1)
print("DRIVE -> BUCKET: TODO PASA")
