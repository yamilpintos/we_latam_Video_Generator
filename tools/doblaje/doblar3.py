# -*- coding: utf-8 -*-
"""Doblaje v3: anclado al ONSET, a velocidad natural, sin estirar.

Que cambio respecto de v2 y por que:
  · v2 usaba atempo hasta 1,35x. Aunque el clip arrancara en su lugar, comprimirlo
    corre TODAS las silabas hacia adelante y a mitad de frase ya no sigue la boca.
    Ahora se sintetiza a velocidad natural y se ancla el inicio. El desborde del
    final se anota y se resuelve despues.
  · Los tiempos salen de una transcripcion SIN forzar idioma (la anterior forzaba
    'es' y machacaba el ingles) y del detector de onset de sync.py.
  · Se dobla TODO, en cualquier idioma. Lo que H3 balbuceo en ingles sin sentido
    se reemplaza por una linea en espanol que encaja en la escena y en la duracion;
    esas van marcadas ESCRITA en el informe.
"""
import json, subprocess, urllib.request
from pathlib import Path
import numpy as np, soundfile as sf

FF = Path(r"c:/Users/Yamil/Desktop/youtube proyect/.venv-depthflow/Scripts/ffmpeg.exe").resolve()
KEY = next(l.split("=",1)[1].strip() for l in
           Path(r"C:/Users/Yamil/Desktop/Foton/dubai_v2/.env").read_text(encoding="utf-8").splitlines()
           if l.strip().startswith("ELEVENLABS_API_KEY="))
SR, DUR = 48000, 304.07
VOZ = {"mago":"oqO5cdAzjE5Ik5xWIZRL","aladino":"p7cwnUviDFhhX9y8sG2Q",
       "genio":"t3eeeqhBjrUqcrPvDqUn","princesa":"br0MPoLVxuslVxf61qHn"}

# (onset, fin real, personaje, texto en espanol, origen)
#   TRAD = traduccion directa de lo que se oye
#   ESP  = ya estaba en espanol
#   ESCR = H3 balbuceo algo sin sentido; linea escrita para la escena
F = [
 (  4.83,   5.20, "aladino",  "Perdón.",                                              "TRAD"),
 ( 20.95,  21.31, "aladino",  "¿Ah?",                                                 "ESP"),
 ( 44.66,  44.97, "mago",     "Tomá.",                                                "ESP"),
 ( 46.35,  48.53, "mago",     "Ven conmigo, muchacho.",                               "ESP"),
 ( 48.52,  52.28, "mago",     "Tengo algo mucho mejor que una moneda.",               "ESP"),
 ( 53.15,  54.40, "aladino",  "¿Y qué es?",                                           "ESCR"),
 ( 82.30,  84.60, "mago",     "Ahora bajá conmigo.",                                  "ESCR"),
 ( 84.61,  85.30, "mago",     "Con cuidado.",                                         "ESCR"),
 (127.73, 130.35, "mago",     "Dame la lámpara, muchacho.",                           "ESP"),
 (130.33, 131.92, "mago",     "Después te saco de ahí.",                              "ESP"),
 (135.57, 135.93, "aladino",  "No.",                                                  "ESP"),
 (137.42, 139.10, "aladino",  "Primero sacame de acá.",                               "ESP"),
 (177.24, 182.65, "genio",    "Mil años durmiendo, y me despierta un muchacho con una lámpara sucia.", "ESP"),
 (194.69, 195.91, "genio",    "Ah…",                                                  "TRAD"),
 (195.80, 200.64, "genio",    "Vas a aprender lo que se aprende cavando en la oscuridad.", "ESCR"),
 (201.41, 201.73, "genio",    "Ah.",                                                  "TRAD"),
 (202.82, 203.17, "genio",    "Perlas.",                                              "TRAD"),
 (210.18, 212.16, "genio",    "Tené cuidado.",                                        "TRAD"),
 (217.90, 219.93, "princesa", "¿Y tú quién eres?",                                    "ESP"),
 (222.81, 223.57, "princesa", "¿Y tú quién eres?",                                    "ESP"),
 (225.80, 227.62, "aladino",  "Nadie importante, todavía.",                           "ESP"),
 (258.36, 266.99, "mago",     "Lámparas nuevas por lámparas viejas, señora. El cambio no cuesta nada.", "ESP"),
 (273.14, 274.44, "mago",     "No es esto.",                                          "ESCR"),
 (279.68, 282.49, "mago",     "Todo esto era mío antes de ser tuyo.",                 "ESP"),
 (290.48, 291.04, "mago",     "Bueno…",                                               "TRAD"),
 (291.89, 293.22, "mago",     "él ya no la necesita.",                                "ESCR"),
 (295.97, 297.77, "aladino",  "Escuché algo.",                                        "TRAD"),
 (302.39, 304.23, "aladino",  "Una luz. Ya veo.",                                     "TRAD"),
]

D = Path("voz3"); D.mkdir(exist_ok=True)
def sint(txt, vid, dst):
    b = json.dumps({"text":txt,"model_id":"eleven_v3",
        "voice_settings":{"stability":0.5,"similarity_boost":0.8,"use_speaker_boost":True}}).encode()
    r = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{vid}?output_format=mp3_44100_192",
        data=b, headers={"xi-api-key":KEY,"Content-Type":"application/json"})
    dst.write_bytes(urllib.request.urlopen(r, timeout=180).read())

def wav(src, dst):
    subprocess.run([str(FF),"-y","-v","error","-i",str(src),"-ac","2","-ar",str(SR),
                    "-c:a","pcm_f32le",str(dst)], check=True, stdin=subprocess.DEVNULL)
    a,_ = sf.read(dst, dtype="float32")
    return a if a.ndim>1 else np.stack([a,a],1)

N = int(DUR*SR)
voz = np.zeros((N,2), np.float32); act = np.zeros(N, np.float32)
print(f"{'onset':>7} {'hueco':>6} {'nat':>6} {'sobra':>7} {'or':>5}  personaje / texto")
for i,(t0,t1,pers,txt,org) in enumerate(F,1):
    mp3 = D/f"G{i:02d}_{pers}.mp3"
    if not mp3.exists(): sint(txt, VOZ[pers], mp3)
    a = wav(mp3, D/f"_w{i}.wav")
    dn = len(a)/SR; hueco = t1-t0; sobra = dn-hueco
    p = np.abs(a).max()
    if p>0: a *= 0.72/p
    j = int(t0*SR); k = min(j+len(a), N)
    voz[j:k] += a[:k-j]
    g = int(0.4*SR); act[max(0,j-g):min(N,k+g)] = 1.0
    marca = "  <-- se pasa" if sobra > 0.4 else ("  (queda corta)" if sobra < -0.6 else "")
    print(f"{t0:7.2f} {hueco:6.2f} {dn:6.2f} {sobra:+7.2f} {org:>5}  {pers}: {txt[:40]}{marca}")

k = int(0.25*SR); act = np.convolve(act, np.ones(k)/k, mode="same")[:N]
np.save("voz3.npy", voz); np.save("act3.npy", act)
print("\nvoz3 lista")
