#!/usr/bin/env python3
"""FlashVSR v1.1 Full por trozos con solapamiento, leyendo el video por ventana.

    python infer_trozos.py entrada.mp4 salida.mp4 [--trozo 125] [--solape 21] [--cuadros N] [--crf 8]

Cada trozo entra al modelo con `solape` cuadros de contexto previo, cuya salida se descarta
(el modelo es causal y arranca "frio"). El tamano de trozo debe cumplir trozo+4 = 8n+1.
Si un trozo se queda sin VRAM, se reintenta con tiles mas chicos en el VAE.

Es la version del 18/9/2026 (remasterizado/prueba-30s/infer_trozos.py, 750/750 cuadros
verificados) con un cambio para capitulos enteros: los cuadros NO se cargan todos a RAM,
se leen a medida que hacen falta y se sueltan los que ya no sirven (una ventana de
~trozo+solape cuadros). Vive en examples/WanVSR junto al script oficial.

Marcas en el log, que la web parsea:
    [entrada] ...     [tiempo] modelo cargado ...     [trozo k] ... escritos a/N
    [listo] ruta . MB . cuadros . total s          Traceback si falla
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


class Lector:
    """Cuadros por indice absoluto, leyendo hacia adelante y soltando lo viejo."""

    def __init__(self, path):
        self.rdr = imageio.get_reader(path)
        meta = self.rdr.get_meta_data()
        self.fps = int(round(meta.get("fps", 25)))
        self.size = meta.get("size")
        n = meta.get("nframes")
        dur = meta.get("duration")
        self.estimado = int(n) if isinstance(n, (int, float)) and n not in (float("inf"),) and n > 0 else (int(round(dur * self.fps)) if dur else None)
        self.it = iter(self.rdr)
        self.buf = []          # cuadros desde self.base
        self.base = 0
        self.eof = False

    def asegurar(self, hasta):
        while not self.eof and self.base + len(self.buf) < hasta:
            try:
                f = next(self.it)
            except StopIteration:
                self.eof = True
                break
            self.buf.append(Image.fromarray(f).convert("RGB"))

    def tramo(self, desde, cuantos):
        self.asegurar(desde + cuantos)
        fin = min(desde + cuantos, self.base + len(self.buf))
        return [self.buf[i - self.base] for i in range(desde, fin)]

    def soltar_antes_de(self, idx):
        k = idx - self.base
        if k > 0:
            del self.buf[:k]
            self.base = idx

    @property
    def leidos(self):
        return self.base + len(self.buf)

    def cerrar(self):
        try:
            self.rdr.close()
        except Exception:
            pass


def tensor_de(frames, scale, tW, tH, dtype, device):
    ts = [oficial.pil_to_tensor_neg1_1(oficial.upscale_then_center_crop(f, scale, tW, tH), dtype, device) for f in frames]
    return torch.stack(ts, 0).permute(1, 0, 2, 3).unsqueeze(0)


# Modos de decodificacion del VAE, del mas rapido al mas seguro. A 2816x2304 el modo sin
# tiling no entra ni en 80 GB (cuDNN "unable to find an engine"), asi que se arranca tileado.
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
    ap.add_argument("--cuadros", type=int, default=0, help="total de cuadros, para el avance (si no, se estima del contenedor)")
    ap.add_argument("--crf", type=int, default=8, help="crf del intermedio (se recodifica despues con el audio)")
    a = ap.parse_args()
    assert (a.trozo + 4 - 1) % 8 == 0, "trozo+4 debe ser 8n+1"
    dtype, device = torch.bfloat16, "cuda"
    t0 = time.time()
    lector = Lector(a.entrada)
    N = a.cuadros or lector.estimado or 0
    lector.asegurar(1)
    if not lector.buf:
        raise RuntimeError("no pude leer ningun cuadro de " + a.entrada)
    w0, h0 = lector.buf[0].size
    sW, sH, tW, tH = oficial.compute_scaled_and_target_dims(w0, h0, scale=a.scale, multiple=128)
    print(f"[entrada] {N or '?'} frames {w0}x{h0} @ {lector.fps} fps -> x{a.scale} = {sW}x{sH} -> recorte a {tW}x{tH}", flush=True)
    pipe = oficial.init_pipeline()
    print(f"[tiempo] modelo cargado en {time.time()-t0:.0f} s", flush=True)
    os.makedirs(os.path.dirname(os.path.abspath(a.salida)), exist_ok=True)
    w = imageio.get_writer(a.salida, fps=lector.fps, codec="libx264", quality=None, pixelformat="yuv420p",
                           output_params=["-crf", str(a.crf), "-preset", "medium"])
    escritos = 0
    k = 0
    while True:
        s = 0 if escritos == 0 else escritos - a.solape
        descartar = 0 if escritos == 0 else a.solape
        sel = lector.tramo(s, a.trozo)
        if lector.eof and s + len(sel) >= lector.leidos and escritos >= lector.leidos:
            break
        if not sel:
            break
        k += 1
        faltan = a.trozo - len(sel)
        sel = sel + [sel[-1]] * faltan                              # ultimo trozo: rellenar con el ultimo cuadro
        sel = sel + [sel[-1]] * 4                                   # los 4 de relleno del script oficial
        F = oficial.largest_8n1_leq(len(sel)); sel = sel[:F]
        t1 = time.time()
        LQ = tensor_de(sel, a.scale, tW, tH, dtype, device)
        torch.cuda.empty_cache(); torch.cuda.reset_peak_memory_stats()
        video = None
        modo = "?"
        for nombre, kw in MODOS:
            try:
                video = correr(pipe, LQ, F, tH, tW, kw); modo = nombre; break
            except (torch.OutOfMemoryError, RuntimeError) as e:
                print(f"[trozo {k}] fallo '{nombre}': {str(e)[:120]}; pruebo el siguiente modo", flush=True)
                del LQ; torch.cuda.empty_cache()
                LQ = tensor_de(sel, a.scale, tW, tH, dtype, device)
        if video is None:
            raise RuntimeError("ningun modo de decodificacion entro en la VRAM")
        out = oficial.tensor2video(video)          # F-4 cuadros
        del video, LQ; torch.cuda.empty_cache()
        utiles = out[descartar:]
        tope = lector.leidos if lector.eof else s + a.trozo
        utiles = utiles[:max(0, tope - escritos)]
        for f in utiles:
            w.append_data(np.array(f))
        escritos += len(utiles)
        total = lector.leidos if lector.eof else (N or "?")
        print(f"[trozo {k}] frames {s}-{s+min(a.trozo, len(sel))-1} -> salida {len(out)} cuadros, utiles {len(utiles)} ({modo}) . "
              f"{time.time()-t1:.0f} s . VRAM pico {torch.cuda.max_memory_allocated()/1e9:.1f} GB . escritos {escritos}/{total}", flush=True)
        if lector.eof and escritos >= lector.leidos:
            break
        lector.soltar_antes_de(max(0, escritos - a.solape))
    w.close()
    lector.cerrar()
    print(f"[listo] {a.salida} . {os.path.getsize(a.salida)/1e6:.0f} MB . {escritos} cuadros . total {time.time()-t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()
