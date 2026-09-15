# -*- coding: utf-8 -*-
"""v4: isocronia por alineacion de palabras. Ver alinear.py para el porque."""
import json, subprocess, sys
from pathlib import Path
import numpy as np, soundfile as sf
sys.path.insert(0, ".")
from alinear import sintetizar_con_tiempos, alinear

FF = Path(r"c:/Users/Yamil/Desktop/youtube proyect/.venv-depthflow/Scripts/ffmpeg.exe").resolve()
SR, DUR = 48000, 304.07
N = int(DUR*SR)
VOZ = {"mago":"oqO5cdAzjE5Ik5xWIZRL","aladino":"p7cwnUviDFhhX9y8sG2Q",
       "genio":"t3eeeqhBjrUqcrPvDqUn","princesa":"br0MPoLVxuslVxf61qHn"}

# (onset, fin real, personaje, texto)  — ESCRITA marca lo que no dice el original
F = [
 (  4.83,   5.20, "aladino",  "Perdón."),
 ( 20.95,  21.31, "aladino",  "¿Ah?"),
 ( 44.66,  44.97, "mago",     "Tomá."),
 ( 46.35,  48.53, "mago",     "Ven conmigo, muchacho."),
 ( 48.52,  52.28, "mago",     "Tengo algo mucho mejor que una moneda."),
 ( 53.36,  54.46, "mago",     "Seguime."),                       # ESCRITA (0:53)
 (127.73, 130.35, "mago",     "Dame la lámpara, muchacho."),
 (130.33, 131.92, "mago",     "Después te saco de ahí."),
 (135.57, 135.93, "aladino",  "No."),
 (137.42, 139.10, "aladino",  "Primero sacame de acá."),
 (177.24, 182.65, "genio",    "Mil años durmiendo y me despierta un muchacho con una lámpara sucia."),
 (210.18, 212.16, "genio",    "Tené cuidado."),
 (217.90, 219.93, "princesa", "¿Y tú quién eres?"),
 (222.81, 223.57, "princesa", "¿Y tú quién eres?"),
 (225.80, 227.62, "aladino",  "Nadie importante todavía."),
 (258.36, 266.99, "mago",     "Lámparas nuevas por lámparas viejas, señora. El cambio no cuesta nada."),
 (279.68, 282.49, "mago",     "Todo esto era mío antes de ser tuyo."),
 (295.97, 297.77, "aladino",  "Escuché algo."),
 (302.39, 304.23, "aladino",  "Una luz. Ya veo."),
]

sc = json.loads(Path("scribe_auto.json").read_text(encoding="utf-8"))
PAL = [{"w":w["text"],"start":w["start"],"end":w["end"]}
       for w in sc["words"] if w.get("type")=="word"]

def wav(src, dst):
    subprocess.run([str(FF),"-y","-v","error","-i",str(src),"-ac","2","-ar",str(SR),
                    "-c:a","pcm_f32le",str(dst)], check=True, stdin=subprocess.DEVNULL)
    a,_ = sf.read(dst, dtype="float32")
    return a if a.ndim>1 else np.stack([a,a],1)

def rampa(a,n):
    n=min(n,len(a)//2)
    if n<=0: return a
    v=np.linspace(0,1,n)[:,None]; a[:n]*=v; a[-n:]*=v[::-1]; return a

D = Path("voz4"); D.mkdir(exist_ok=True)
voz = np.zeros((N,2), np.float32); act = np.zeros(N, np.float32)
print(f"{'onset':>7} {'hueco':>6} {'nat':>6} {'final':>6} {'anclas':>7}  personaje / texto")
for i,(t0,t1,pers,txt) in enumerate(F,1):
    mp3, js = D/f"H{i:02d}.mp3", D/f"H{i:02d}.json"
    if mp3.exists() and js.exists():
        pg = [tuple(x) for x in json.loads(js.read_text(encoding="utf-8"))]
    else:
        audio, pg = sintetizar_con_tiempos(txt, VOZ[pers])
        mp3.write_bytes(audio); js.write_text(json.dumps(pg), encoding="utf-8")
    a = wav(mp3, D/f"_x{i}.wav"); dn = len(a)/SR
    orig = [p for p in PAL if t0-0.15 <= p["start"] <= t1+0.15]
    a2, k = alinear(a, pg, orig, t0) if orig else (a, 0)
    df = len(a2)/SR
    p = np.abs(a2).max()
    if p>0: a2 *= 0.72/p
    j = int(t0*SR); e = min(j+len(a2), N)
    voz[j:e] += a2[:e-j]
    g = int(0.4*SR); act[max(0,j-g):min(N,e+g)] = 1.0
    print(f"{t0:7.2f} {t1-t0:6.2f} {dn:6.2f} {df:6.2f} {k:7d}  {pers}: {txt[:38]}")

k = int(0.25*SR); act = np.convolve(act, np.ones(k)/k, mode="same")[:N]
amb,_ = sf.read("ambiente.wav", dtype="float32")
amb = amb[:N] if len(amb)>=N else np.pad(amb, ((0,N-len(amb)),(0,0)))
mus = np.zeros((N,2), np.float32)
for nom,a0,b0 in [("M1_bazar",0,60.8),("M2_cueva",60.8,152.0),("M3_genio",152.0,212.8),
                  ("M4_palacio",212.8,243.3),("M5_final",243.3,304.1)]:
    a = wav(Path("musica")/f"{nom}.mp3", Path(f"_q_{nom}.wav"))
    L = int((b0-a0)*SR)
    a = a[:L] if len(a)>=L else np.pad(a,((0,L-len(a)),(0,0)))
    a = rampa(a,int(1.5*SR)); i0=int(a0*SR); j0=min(i0+len(a),N); mus[i0:j0]+=a[:j0-i0]
p=np.abs(mus).max()
if p>0: mus*=0.5/p
mus *= (1.0-0.62*act)[:,None]
mix = amb*0.85 + mus*0.42 + voz*1.0
p=np.abs(mix).max()
if p>0.99: mix*=0.99/p
sf.write("mezcla4.wav", mix, SR)
print(f"\nmezcla4.wav {len(mix)/SR:.2f}s", flush=True)
subprocess.run([str(FF),"-y","-loglevel","error",
    "-i", r"c:/Users/Yamil/Desktop/youtube proyect/pruebas video 2/Mejor H3/PELICULA.mp4",
    "-i","mezcla4.wav","-map","0:v:0","-map","1:a:0","-c:v","copy",
    "-af","loudnorm=I=-14:TP=-1.0:LRA=11","-c:a","aac","-b:a","256k","-ar","48000",
    "-movflags","+faststart","-shortest",
    r"C:/Users/Yamil/Desktop/Aladino doblado/Aladino - doblado v4.mp4"],
    check=True, stdin=subprocess.DEVNULL)
print("video listo")
