#!/usr/bin/env python3
"""FlashVSR v1.1 Full por trozos con solapamiento, para clips que no entran enteros en la VRAM.

    python infer_trozos.py entrada.mp4 salida.mp4 [--trozo 173] [--solape 25]

Cada trozo entra al modelo con `solape` cuadros de contexto previo, cuya salida se descarta
(el modelo es causal y arranca "frío"). El tamaño de trozo debe cumplir trozo+4 = 8n+1.
Si un trozo se queda sin VRAM, se reintenta con tiling del VAE. Vive en examples/WanVSR.
"""
import os, sys, time, argparse
import numpy as np
from PIL import Image
import imageio
import torch
from diffsynth import ModelManager, FlashVSRFullPipeline
from utils.utils import Causal_LQ4x_Proj
import importlib.util
_spec = importlib.util.spec_from_file_location("oficial", os.path.join(os.path.dirname(os.path.abspath(__file__)), "infer_flashvsr_v1.1_full.py"))
oficial = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(oficial)

def leer_frames(path):
    rdr = imageio.get_reader(path)
    fps = rdr.get_meta_data().get("fps", 25)
    frames = [Image.fromarray(f).convert("RGB") for f in rdr]
    rdr.close()
    return frames, int(round(fps))

def tensor_de(frames, scale, tW, tH, dtype, device):
    ts = [oficial.pil_to_tensor_neg1_1(oficial.upscale_then_center_crop(f, scale, tW, tH), dtype, device) for f in frames]
    return torch.stack(ts, 0).permute(1, 0, 2, 3).unsqueeze(0)

# Modos de decodificación del VAE, del más rápido al más seguro. A 2816x2304 el modo sin
# tiling no entra ni en 80 GB (cuDNN "unable to find an engine"), así que se arranca tileado.
MODOS = [("tiles grandes", dict(tiled=True, tile_size=(80, 128), tile_stride=(60, 96))),
         ("tiles chicos",  dict(tiled=True, tile_size=(60, 104), tile_stride=(30, 52)))]

def correr(pipe, LQ, F, th, tw, modo, seed=0, sparse_ratio=2.0, local_range=11):
    return pipe(prompt="", negative_prompt="", cfg_scale=1.0, num_inference_steps=1, seed=seed,
                LQ_video=LQ, num_frames=F, height=th, width=tw, is_full_block=False, if_buffer=True,
                topk_ratio=sparse_ratio * 768 * 1280 / (th * tw), kv_ratio=3.0, local_range=local_range, color_fix=True,
                **modo)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("entrada"); ap.add_argument("salida")
    ap.add_argument("--trozo", type=int, default=125)   # 125+4 = 129 = 8*16+1
    ap.add_argument("--solape", type=int, default=21)
    ap.add_argument("--scale", type=int, default=4)
    a = ap.parse_args()
    assert (a.trozo + 4 - 1) % 8 == 0, "trozo+4 debe ser 8n+1"
    dtype, device = torch.bfloat16, "cuda"
    t0 = time.time()
    frames, fps = leer_frames(a.entrada)
    N = len(frames); w0, h0 = frames[0].size
    sW, sH, tW, tH = oficial.compute_scaled_and_target_dims(w0, h0, scale=a.scale, multiple=128)
    print(f"[entrada] {N} frames {w0}x{h0} @ {fps} fps → x{a.scale} = {sW}x{sH} → recorte a {tW}x{tH}", flush=True)
    pipe = oficial.init_pipeline()
    print(f"[tiempo] modelo cargado en {time.time()-t0:.0f} s", flush=True)
    os.makedirs(os.path.dirname(os.path.abspath(a.salida)), exist_ok=True)
    w = imageio.get_writer(a.salida, fps=fps, codec="libx264", quality=None, pixelformat="yuv420p",
                           output_params=["-crf", "8", "-preset", "medium"])
    escritos = 0
    nuevos = a.trozo - a.solape
    ini = 0
    k = 0
    while escritos < N:
        k += 1
        s = 0 if ini == 0 else ini - a.solape
        descartar = 0 if ini == 0 else a.solape
        idx = list(range(s, min(s + a.trozo, N)))
        faltan = a.trozo - len(idx)
        sel = [frames[i] for i in idx] + [frames[-1]] * faltan   # último trozo: rellenar con el último cuadro
        sel = sel + [sel[-1]] * 4                                 # los 4 de relleno del script oficial
        F = oficial.largest_8n1_leq(len(sel)); sel = sel[:F]
        t1 = time.time()
        LQ = tensor_de(sel, a.scale, tW, tH, dtype, device)
        torch.cuda.empty_cache(); torch.cuda.reset_peak_memory_stats()
        video = None
        for nombre, kw in MODOS:
            try:
                video = correr(pipe, LQ, F, tH, tW, kw); modo = nombre; break
            except (torch.OutOfMemoryError, RuntimeError) as e:
                print(f"[trozo {k}] falló '{nombre}': {str(e)[:120]}; pruebo el siguiente modo", flush=True)
                del LQ; torch.cuda.empty_cache()
                LQ = tensor_de(sel, a.scale, tW, tH, dtype, device)
        if video is None:
            raise RuntimeError("ningún modo de decodificación entró en la VRAM")
        out = oficial.tensor2video(video)          # F-4 cuadros
        del video, LQ; torch.cuda.empty_cache()
        utiles = out[descartar:]
        utiles = utiles[:N - escritos]
        for f in utiles:
            w.append_data(np.array(f))
        escritos += len(utiles)
        print(f"[trozo {k}] frames {s}-{s+len(idx)-1} → salida {len(out)} cuadros, útiles {len(utiles)} ({modo}) · "
              f"{time.time()-t1:.0f} s · VRAM pico {torch.cuda.max_memory_allocated()/1e9:.1f} GB · escritos {escritos}/{N}", flush=True)
        ini += nuevos if ini else a.trozo
        ini = min(ini, escritos)
    w.close()
    print(f"[listo] {a.salida} · {os.path.getsize(a.salida)/1e6:.0f} MB · {escritos} cuadros · total {time.time()-t0:.0f} s", flush=True)

if __name__ == "__main__":
    main()
