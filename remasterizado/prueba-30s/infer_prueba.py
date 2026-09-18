#!/usr/bin/env python3
# FlashVSR v1.1 Full sobre UN video: python infer_prueba.py entrada.mp4 salida.mp4
# Copia del infer_flashvsr_v1.1_full.py oficial con entrada/salida por argumentos,
# calidad de grabación alta y medición de tiempo y VRAM. Debe vivir en examples/WanVSR.
import os, sys, time
import numpy as np
from PIL import Image
import imageio
from tqdm import tqdm
import torch
from einops import rearrange
from diffsynth import ModelManager, FlashVSRFullPipeline
from utils.utils import Causal_LQ4x_Proj
import importlib.util
spec = importlib.util.spec_from_file_location("oficial", os.path.join(os.path.dirname(os.path.abspath(__file__)), "infer_flashvsr_v1.1_full.py"))
oficial = importlib.util.module_from_spec(spec); spec.loader.exec_module(oficial)

def main():
    entrada, salida = sys.argv[1], sys.argv[2]
    seed, scale, dtype, device = 0, 4, torch.bfloat16, 'cuda'
    sparse_ratio = 2.0   # 2.0 = más estable (recomendado por los autores)
    local_range = 11     # 11 = más estable; 9 = más nítido
    t0 = time.time()
    pipe = oficial.init_pipeline()
    print(f"[tiempo] modelo cargado en {time.time()-t0:.0f} s", flush=True)
    LQ, th, tw, F, fps = oficial.prepare_input_tensor(entrada, scale=scale, dtype=dtype, device=device)
    print(f"[entrada] frames={F} fps={fps} salida={tw}x{th}", flush=True)
    torch.cuda.reset_peak_memory_stats()
    t1 = time.time()
    video = pipe(
        prompt="", negative_prompt="", cfg_scale=1.0, num_inference_steps=1, seed=seed,
        tiled=False, LQ_video=LQ, num_frames=F, height=th, width=tw, is_full_block=False, if_buffer=True,
        topk_ratio=sparse_ratio*768*1280/(th*tw), kv_ratio=3.0, local_range=local_range, color_fix=True,
    )
    dt = time.time() - t1
    print(f"[tiempo] inferencia {dt:.1f} s para {F} frames = {F/dt:.2f} fps · VRAM pico {torch.cuda.max_memory_allocated()/1e9:.1f} GB", flush=True)
    frames = oficial.tensor2video(video)
    os.makedirs(os.path.dirname(os.path.abspath(salida)), exist_ok=True)
    w = imageio.get_writer(salida, fps=fps, codec="libx264", quality=None, pixelformat="yuv420p",
                           output_params=["-crf", "8", "-preset", "medium"])
    for f in tqdm(frames, desc="grabando"):
        w.append_data(np.array(f))
    w.close()
    print(f"[listo] {salida} · {os.path.getsize(salida)/1e6:.0f} MB · total {time.time()-t0:.0f} s", flush=True)

if __name__ == "__main__":
    main()
