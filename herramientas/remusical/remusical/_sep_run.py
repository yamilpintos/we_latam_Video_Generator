# -*- coding: utf-8 -*-
"""
Separación voz / música-efectos (audio-separator, py3.11). Devuelve vocals + instrumental.

★ CORRECCIÓN 21-jul: este archivo DECÍA "separacion con BS-Roformer" en su docstring desde
hace un mes, pero cargaba `UVR-MDX-NET-Inst_HQ_3.onnx`, que es MDX-Net. O sea que veníamos
usando el modelo anterior creyendo que usábamos el bueno — y la conclusión escrita entonces
sobre el fondo enterrado ("el problema es la CALIDAD del stem, no el nivel"; subir ganancia
+6 dB con ducking quedó 'peor o igual') apuntaba justo a esto sin que nadie mirara el código.

BS-Roformer (Band-Split RoPE Transformer, de ByteDance) separa netamente mejor con música
densa —el caso de una película con score permanente— que es donde MDX-Net deja la música
fina y llena de artefactos. Se prueba en orden y se cae al anterior si el modelo no baja.

El SDR del nombre es la métrica de calidad de separación: 12.98 (BS-Roformer) contra ~11 de
MDX-Net Inst HQ3.

Uso: python sep_run.py <audio.wav> <outdir>   (requiere ffmpeg en PATH)
"""
import sys

from audio_separator.separator import Separator

inp, outdir = sys.argv[1], sys.argv[2]
sep = Separator(output_dir=outdir)

# orden: mejor primero. El último (None) usa el default de la librería como red de seguridad.
MODELOS = [
    "model_bs_roformer_ep_317_sdr_12.9755.ckpt",   # BS-Roformer Viperx-1297 (ByteDance)
    "model_bs_roformer_ep_368_sdr_12.9628.ckpt",   # BS-Roformer Viperx-1296
    "melband_roformer_instvox_duality_v2.ckpt",    # Mel-Band Roformer, alternativa fuerte
    "UVR-MDX-NET-Inst_HQ_3.onnx",                  # el que se usaba de verdad hasta hoy
    None,
]
elegido = None
for model in MODELOS:
    try:
        sep.load_model(model_filename=model) if model else sep.load_model()
        elegido = model or "default"
        print("modelo:", elegido, flush=True)
        break
    except Exception as e:
        print("fallo modelo", model, str(e)[:120], flush=True)
if elegido is None:
    raise SystemExit("no se pudo cargar ningún modelo de separación")

out = sep.separate(inp)
print("SALIDAS:", out, flush=True)
