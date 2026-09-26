# -*- coding: utf-8 -*-
# ★ 26-sep: las pruebas NUNCA tocan vast ni ElevenLabs. Una prueba que llamó a media.separar con las credenciales de
#   la PC alquiló una RTX 4090 real (USD 0,03, destruida a mano). Acá se apaga la GPU antes de importar config;
#   test_gpu_vast la vuelve a prender sobre una API falsa.
import os

os.environ["DOBLAJE_GPU"] = "off"
