# -*- coding: utf-8 -*-
"""
Bucket S3-compatible (Cloudflare R2, Backblaze B2, MinIO, AWS) para los RESULTADOS.

Por qué existe: la cuenta de servicio de Drive no puede escribir (no tiene cuota), así
que los resultados no vuelven a Drive desde la máquina. Van acá, y desde acá los baja
el usuario con un link firmado.

DOS FORMAS DE ESCRIBIR, según el tamaño:

  · `firmar_subida()` → URL firmada, un solo PUT, una sola ruta, con vencimiento.
    La máquina NO recibe ninguna credencial. Límite: 5 GB por archivo (un PUT simple).
    Es lo que se usa para episodios (~4 GB) y para todos los stems.

  · token del bucket de SALIDA, cuando un archivo supera los 5 GB (películas largas).
    Ese token sólo alcanza al bucket de resultados — el material fuente nunca está ahí.

Recomendado: **Cloudflare R2** — el egreso es gratis, que con video es lo que manda.
Variables: S3_ENDPOINT, S3_KEY, S3_SECRET, S3_BUCKET, (opcional S3_REGION).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

LIMITE_PUT_SIMPLE = 5 * 1024 ** 3        # 5 GB: tope de un PUT sin multipart


class BucketError(RuntimeError):
    pass


def _cliente(endpoint=None, key=None, secret=None, region=None):
    try:
        import boto3
        from botocore.config import Config
    except ImportError:
        raise BucketError("hace falta boto3 (pip install boto3)")
    ep = endpoint or os.getenv("S3_ENDPOINT")
    k = key or os.getenv("S3_KEY")
    s = secret or os.getenv("S3_SECRET")
    if not (k and s):
        raise BucketError("faltan S3_KEY / S3_SECRET")
    return boto3.client("s3", endpoint_url=ep or None, aws_access_key_id=k,
                        aws_secret_access_key=s, region_name=region or os.getenv("S3_REGION") or "auto",
                        config=Config(signature_version="s3v4", retries={"max_attempts": 5, "mode": "standard"}))


def bucket_por_defecto() -> str:
    b = os.getenv("S3_BUCKET")
    if not b:
        raise BucketError("falta S3_BUCKET")
    return b


@dataclass
class Firmadas:
    """Las URLs que se le pasan a la máquina. No son credenciales: cada una sirve para
    UNA operación sobre UN objeto y vence."""
    subidas: dict[str, str]              # nombre de archivo -> URL de PUT
    horas: float


# nombres que el motor deja en la carpeta de salida, para firmarlos por anticipado
def nombres_salida(nombre_video: str, completo: bool = False) -> list[str]:
    base = Path(nombre_video).stem
    n = [f"re-musical {base}.mp4", f"REVISAR {base}.mp4",       # sale uno u otro
         f"{base} - voz.flac", f"{base} - musica original.flac",
         f"{base} - musica nueva.flac", f"{base} - informe.json"]
    if completo:
        n.append(f"{base} - ambiente.flac")
    return n


def firmar_subida(clave: str, horas: float = 6, bucket: str | None = None, cli=None) -> str:
    cli = cli or _cliente()
    return cli.generate_presigned_url("put_object",
                                      Params={"Bucket": bucket or bucket_por_defecto(), "Key": clave},
                                      ExpiresIn=int(horas * 3600))


def firmar_bajada(clave: str, horas: float = 24, bucket: str | None = None, cli=None) -> str:
    cli = cli or _cliente()
    return cli.generate_presigned_url("get_object",
                                      Params={"Bucket": bucket or bucket_por_defecto(), "Key": clave},
                                      ExpiresIn=int(horas * 3600))


def firmar_salidas(prefijo: str, nombre_video: str, completo: bool = False,
                   horas: float = 6, bucket: str | None = None) -> Firmadas:
    """Todas las URLs de subida que la máquina va a necesitar para un video."""
    cli = _cliente()
    b = bucket or bucket_por_defecto()
    return Firmadas({n: firmar_subida(f"{prefijo.strip('/')}/{n}", horas, b, cli)
                     for n in nombres_salida(nombre_video, completo)}, horas)


def subir_con_url(url: str, archivo: Path, log=print) -> bool:
    """Sube por URL firmada. Esto corre EN la máquina: sin credenciales."""
    import requests
    tam = archivo.stat().st_size
    if tam > LIMITE_PUT_SIMPLE:
        log(f"    {archivo.name}: {tam/1e9:.1f} GB supera el PUT simple (5 GB); hace falta token de bucket")
        return False
    with open(archivo, "rb") as f:
        r = requests.put(url, data=f, timeout=3600,
                         headers={"Content-Length": str(tam), "Content-Type": "application/octet-stream"})
    if r.status_code not in (200, 201, 204):
        raise BucketError(f"subida de {archivo.name} → HTTP {r.status_code}: {r.text[:200]}")
    return True


# ------------------------------------------------------------------ lado servidor
def subir(archivo: Path, clave: str, bucket: str | None = None) -> str:
    """Con credenciales (esto corre en Render o en tu máquina, no en Vast)."""
    cli = _cliente()
    b = bucket or bucket_por_defecto()
    cli.upload_file(str(archivo), b, clave)
    return f"s3://{b}/{clave}"


def listar(prefijo: str, bucket: str | None = None) -> list[dict]:
    cli = _cliente()
    b = bucket or bucket_por_defecto()
    out, tok = [], None
    while True:
        kw = dict(Bucket=b, Prefix=prefijo)
        if tok:
            kw["ContinuationToken"] = tok
        r = cli.list_objects_v2(**kw)
        out += [dict(clave=o["Key"], bytes=o["Size"], fecha=str(o["LastModified"])) for o in r.get("Contents", [])]
        if not r.get("IsTruncated"):
            return out
        tok = r.get("NextContinuationToken")


def borrar(prefijo: str, bucket: str | None = None) -> int:
    """Borra todo lo que cuelga del prefijo. Para limpiar una tanda ya descargada."""
    cli = _cliente()
    b = bucket or bucket_por_defecto()
    n = 0
    objs = [{"Key": o["clave"]} for o in listar(prefijo, b)]
    for i in range(0, len(objs), 1000):
        cli.delete_objects(Bucket=b, Delete={"Objects": objs[i:i + 1000]})
        n += len(objs[i:i + 1000])
    return n


def verificar() -> dict:
    """Prueba de vida: escribe un objeto chico, lo lee y lo borra."""
    try:
        cli = _cliente()
        b = bucket_por_defecto()
        k = "_remusical/prueba.txt"
        cli.put_object(Bucket=b, Key=k, Body=b"ok")
        cli.get_object(Bucket=b, Key=k)["Body"].read()
        cli.delete_object(Bucket=b, Key=k)
        return dict(ok=True, bucket=b, endpoint=os.getenv("S3_ENDPOINT"))
    except Exception as e:
        return dict(ok=False, error=str(e)[:300], bucket=os.getenv("S3_BUCKET"),
                    endpoint=os.getenv("S3_ENDPOINT"))
