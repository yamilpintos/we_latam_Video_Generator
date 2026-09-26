# -*- coding: utf-8 -*-
"""
Lectura de Google Drive con CUENTA DE SERVICIO, limitada a UNA carpeta.

Por qué así: la máquina de Vast es de un tercero. Mandarle el token OAuth del usuario
le daría acceso a TODO su Drive durante una hora. En cambio, una cuenta de servicio a
la que el usuario compartió una sola carpeta **como Lector** puede bajar los videos de
esa carpeta y nada más: no lista el resto del Drive, no borra, no modifica.

★ Y NO PUEDE ESCRIBIR. Verificado en la documentación de Google: una cuenta de servicio
no tiene cuota de almacenamiento propia, así que no puede crear archivos en un Drive
personal ("Service Accounts do not have storage quota"). Para escribir haría falta una
unidad compartida (Workspace). Por eso los resultados van al bucket, nunca de vuelta a
Drive desde la máquina — lo cual, de paso, es más seguro.

Alta (una vez):
  1. console.cloud.google.com → APIs → habilitar Google Drive API
  2. Credenciales → Crear → Cuenta de servicio → Claves → Agregar clave JSON
  3. En Drive, compartir la carpeta de la serie con el email de la cuenta de servicio,
     como **Lector**
  4. El JSON va en GOOGLE_SA_JSON_B64 (base64) o GOOGLE_SA_JSON (ruta)

Sólo pide el scope `drive.readonly`.
"""
from __future__ import annotations

import base64
import io
import json
import os
from dataclasses import dataclass
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
VIDEO_MIMES = ("video/",)


class DriveError(RuntimeError):
    pass


def _credenciales():
    from google.oauth2 import service_account
    b64 = os.getenv("GOOGLE_SA_JSON_B64")
    ruta = os.getenv("GOOGLE_SA_JSON")
    if b64:
        info = json.loads(base64.b64decode(b64).decode("utf-8"))
    elif ruta and Path(ruta).exists():
        info = json.loads(Path(ruta).read_text(encoding="utf-8"))
    else:
        raise DriveError("falta GOOGLE_SA_JSON_B64 (o GOOGLE_SA_JSON con la ruta al JSON)")
    return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)


def cliente():
    from googleapiclient.discovery import build
    return build("drive", "v3", credentials=_credenciales(), cache_discovery=False)


def email_cuenta() -> str:
    """El mail con el que el usuario tiene que compartir la carpeta."""
    return _credenciales().service_account_email


@dataclass
class Archivo:
    id: str
    nombre: str
    tamano: int
    duracion_s: float
    mime: str


def listar_videos(carpeta_id: str, d=None) -> list[Archivo]:
    """Videos de la carpeta compartida. Falla claro si no está compartida."""
    d = d or cliente()
    campos = "nextPageToken, files(id,name,size,mimeType,videoMediaMetadata(durationMillis))"
    out, page = [], None
    try:
        while True:
            r = d.files().list(q=f"'{carpeta_id}' in parents and trashed = false", fields=campos,
                               pageSize=200, pageToken=page, orderBy="name",
                               supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
            for f in r.get("files", []):
                if f["mimeType"].startswith(VIDEO_MIMES):
                    vm = f.get("videoMediaMetadata") or {}
                    out.append(Archivo(f["id"], f["name"], int(f.get("size", 0) or 0),
                                       int(vm.get("durationMillis", 0) or 0) / 1000, f["mimeType"]))
            page = r.get("nextPageToken")
            if not page:
                return out
    except Exception as e:
        if "404" in str(e) or "notFound" in str(e):
            raise DriveError(f"la cuenta de servicio no ve la carpeta {carpeta_id}. "
                             f"Compartila con {email_cuenta()} como Lector.")
        raise


def verificar_acceso(carpeta_id: str) -> dict:
    """Para que la web avise ANTES de alquilar una máquina. Nunca lanza."""
    try:
        d = cliente()
        meta = d.files().get(fileId=carpeta_id, fields="id,name,mimeType",
                             supportsAllDrives=True).execute()
        vids = listar_videos(carpeta_id, d)
        return dict(ok=True, carpeta=meta.get("name"), videos=len(vids),
                    bytes=sum(v.tamano for v in vids), email=email_cuenta())
    except Exception as e:
        try:
            mail = email_cuenta()
        except Exception:
            mail = None
        return dict(ok=False, error=str(e)[:300], email=mail,
                    ayuda=(f"Compartí la carpeta con {mail} como Lector" if mail else
                           "Falta GOOGLE_SA_JSON_B64"))


def bajar(file_id: str, dst: Path, progreso=None, d=None) -> Path:
    """Baja un archivo por id. Esto corre EN la máquina de Vast."""
    from googleapiclient.http import MediaIoBaseDownload
    d = d or cliente()
    dst.parent.mkdir(parents=True, exist_ok=True)
    req = d.files().get_media(fileId=file_id, supportsAllDrives=True)
    with open(dst, "wb") as f:
        dl = MediaIoBaseDownload(f, req, chunksize=64 * 1024 * 1024)
        hecho = False
        while not hecho:
            st, hecho = dl.next_chunk()
            if st and progreso:
                progreso(st.progress())
    return dst


def nombre(file_id: str, d=None) -> str:
    d = d or cliente()
    return d.files().get(fileId=file_id, fields="name", supportsAllDrives=True).execute()["name"]
