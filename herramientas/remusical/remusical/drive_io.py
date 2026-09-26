# -*- coding: utf-8 -*-
"""
Google Drive: bajar el video, crear `re-musical/` y subir los resultados.

Lo usan dos lugares con credenciales distintas:
  · la web (modo local): con las credenciales OAuth de la sesión
  · el contenedor de Replicate: con un access_token de una hora que la web le pasa
    como Secret. El video NUNCA pasa por el servidor web.
"""
from __future__ import annotations

from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from google.oauth2.credentials import Credentials

PREFIJO = "re-musical"
CHUNK = 32 * 1024 * 1024


def drive_con_token(access_token: str):
    return build("drive", "v3", credentials=Credentials(token=access_token), cache_discovery=False)


def drive_con_creds(creds: Credentials):
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def meta(d, file_id: str) -> dict:
    return d.files().get(fileId=file_id, fields="id,name,parents,size,mimeType",
                         supportsAllDrives=True).execute()


def bajar(d, file_id: str, dst: Path, progreso=None) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    req = d.files().get_media(fileId=file_id, supportsAllDrives=True)
    with open(dst, "wb") as f:
        dl = MediaIoBaseDownload(f, req, chunksize=CHUNK)
        done = False
        while not done:
            st, done = dl.next_chunk()
            if st and progreso:
                progreso(st.progress())
    return dst


def carpeta_salida(d, padre: str, nombre: str = PREFIJO) -> str:
    """La carpeta `re-musical/` dentro del padre; la crea si no está."""
    q = (f"'{padre}' in parents and name = '{nombre}' and "
         f"mimeType = 'application/vnd.google-apps.folder' and trashed = false")
    r = d.files().list(q=q, fields="files(id)", supportsAllDrives=True,
                       includeItemsFromAllDrives=True).execute()
    if r.get("files"):
        return r["files"][0]["id"]
    body = {"name": nombre, "mimeType": "application/vnd.google-apps.folder", "parents": [padre]}
    return d.files().create(body=body, fields="id", supportsAllDrives=True).execute()["id"]


def subir(d, ruta: Path, carpeta_id: str) -> str:
    """Sube (o reemplaza si ya existe con ese nombre). Devuelve el id."""
    mime = {".mp4": "video/mp4", ".flac": "audio/flac", ".json": "application/json"}.get(
        ruta.suffix.lower(), "application/octet-stream")
    nombre_q = ruta.name.replace("\\", "\\\\").replace("'", "\\'")
    q = f"'{carpeta_id}' in parents and name = '{nombre_q}' and trashed = false"
    r = d.files().list(q=q, fields="files(id)", supportsAllDrives=True,
                       includeItemsFromAllDrives=True).execute()
    media = MediaFileUpload(str(ruta), mimetype=mime, resumable=True, chunksize=CHUNK)
    if r.get("files"):
        req = d.files().update(fileId=r["files"][0]["id"], media_body=media,
                               supportsAllDrives=True, fields="id")
    else:
        req = d.files().create(body={"name": ruta.name, "parents": [carpeta_id]},
                               media_body=media, supportsAllDrives=True, fields="id")
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    return resp["id"]
