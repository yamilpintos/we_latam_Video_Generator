"""Enlaza en FL2VA/ los componentes que son byte-identicos a los de Ref2VA.

Verificado por sha256 contra el Hub: text_encoder, video_vae y audio_vae son
exactamente los mismos archivos en ambas variantes. Usamos hardlinks para no
gastar 77 GB de disco duplicandolos (NTFS los soporta dentro del mismo volumen).
Si el hardlink falla, cae a copia.
"""
import os
import shutil

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "models", "MiniMax-H3")
SHARED = ["text_encoder", "video_vae", "audio_vae", "tokenizer", "processor"]

linked = copied = skipped = 0
freed = 0

for comp in SHARED:
    src_root = os.path.join(BASE, "Ref2VA", comp)
    dst_root = os.path.join(BASE, "FL2VA", comp)
    if not os.path.isdir(src_root):
        print(f"[skip] no existe {src_root}")
        continue

    for root, _, files in os.walk(src_root):
        rel = os.path.relpath(root, src_root)
        dst_dir = os.path.join(dst_root, rel) if rel != "." else dst_root
        os.makedirs(dst_dir, exist_ok=True)

        for name in files:
            src = os.path.join(root, name)
            dst = os.path.join(dst_dir, name)
            if os.path.exists(dst):
                skipped += 1
                continue
            size = os.path.getsize(src)
            try:
                os.link(src, dst)
                linked += 1
                freed += size
            except OSError:
                shutil.copy2(src, dst)
                copied += 1

print(f"hardlinks: {linked} | copias: {copied} | ya existian: {skipped}")
print(f"disco ahorrado por hardlinks: {freed / 1_073_741_824:.1f} GiB")
