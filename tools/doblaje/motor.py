# -*- coding: utf-8 -*-
"""v5: el alineador que preserva el tono y topa el alargue. No pisa el v4."""
import json, re, subprocess, sys
from pathlib import Path
import numpy as np, soundfile as sf
from scipy.ndimage import uniform_filter1d
sys.path.insert(0, ".")
from alinear import sintetizar_con_tiempos, alinear
import ventana as V
import seleccion as SEL

FF = Path(r"c:/Users/Yamil/Desktop/youtube proyect/.venv-depthflow/Scripts/ffmpeg.exe").resolve()
SR, DUR = 48000, 304.07
N = int(DUR*SR)
VOZ = {"mago":"oqO5cdAzjE5Ik5xWIZRL","aladino":"p7cwnUviDFhhX9y8sG2Q",
       "genio":"t3eeeqhBjrUqcrPvDqUn","princesa":"br0MPoLVxuslVxf61qHn"}

# (onset, fin real, personaje, texto)  — ESCRITA marca lo que no dice el original
# (onset ASR, fin ASR, personaje, [redacciones candidatas])
#
# Varias redacciones por linea: se sintetizan todas, se miden, y entra la que
# mejor calza en la ventana medida. Ver seleccion.py para el criterio.
F = [
 (  4.83,   5.20, "aladino",  ["Perdon.", "Perdon", "Disculpa."]),
 ( 20.95,  21.31, "aladino",  ["¿Ah?", "¿Eh?", "Ah."]),
 ( 44.66,  44.97, "mago",     ["Toma.", "Ten.", "Toma"]),
 ( 46.35,  48.53, "mago",     ["Ven conmigo, muchacho.", "Acompaname, muchacho.",
                               "Ven conmigo, chico."]),
 ( 48.52,  52.28, "mago",     ["Tengo algo mejor que una moneda.", "Tengo algo mucho mejor.",
                               "Algo mejor que una moneda, mira."]),
 ( 53.36,  54.46, "mago",     ["Sigueme, muchacho.", "Sigueme.", "Ven, sigueme."]),
 (127.73, 130.35, "mago",     ["Dame la lampara, muchacho.", "Dame esa lampara ahora.",
                               "Dame la lampara. Ahora."]),
 (130.33, 131.92, "mago",     ["Despues te saco de ahi.", "Luego te saco de ahi.",
                               "Despues te saco de alli."]),
 (135.57, 135.93, "aladino",  ["No.", "No", "Nunca."]),
 (137.42, 139.10, "aladino",  ["Primero sacame de aqui.", "Sacame de aqui primero.",
                               "Primero sacame tu a mi."]),
 (177.24, 182.65, "genio",    ["[sighs] Mil anos... || y me despierta un muchacho con una lampara sucia.",
                               "[sighs] Mil anos durmiendo... || y me despierta un muchacho con una lampara sucia.",
                               "[yawns] Mil anos... || y me despierta un muchacho con una lampara sucia."]),
 (210.18, 212.16, "genio",    ["Cuidado. || ", "Ten cuidado. || "]),
 # El chico es quien pregunta primero; estaba mal asignado a la princesa y
 # salia con voz de mujer. La diarizacion no sirve para esto (ver ESTADO): el
 # reparto se asigna por contenido y escena, y se verifica escuchando.
 (217.90, 219.93, "aladino",  ["[curious] ¿Y tu quien eres?", "¿Quien eres?",
                               "¿Tu quien eres?"]),
 (222.81, 223.57, "princesa", ["¿Quien eres?", "¿Y tu?", "¿Quien eres tu?"]),
 (225.80, 227.62, "aladino",  ["Nadie importante todavia.", "Nadie importante.", "Nadie, todavia."]),
 (258.36, 266.99, "mago",     ["¡Lamparas nuevas por lamparas viejas! ¡Cambio lo viejo por lo nuevo! || No le cuesta nada, senora.",
                               "¡Lamparas nuevas por lamparas viejas, senora! ¡Se las cambio! || El cambio no cuesta nada."]),
 (279.68, 282.49, "mago",     ["Todo esto era mio antes de ser tuyo.", "Esto era mio antes que tuyo.",
                               "Todo esto era mio mucho antes de ser tuyo."]),
 (295.97, 297.77, "aladino",  ["Oi algo.", "Oi.", "Algo."]),
 (302.39, 304.23, "aladino",  ["Una luz. || Ya la veo.", "Ahi. Una luz. || Ya veo.", "Una luz. || Ahi."]),
]


# Corrimiento manual por frase, en segundos. Negativo = adelantar el doblaje.
#
# H3 no sincroniza su propia boca con su propio audio. En el plano del genio la
# boca empieza a moverse en 176,5 (verificado fotograma a fotograma) y su voz
# recien arranca en 177,2: 0,7 s de diferencia. Como las anclas salen de Scribe,
# que transcribe el AUDIO, heredamos ese error entero. La boca manda sobre el
# audio, asi que se corrige a mano por plano.
AJUSTE = {}            # corrimiento manual por plano, en segundos

# Adelanto fijo de todas las lineas. DubAI usa SYNC_LEAD = 0.1 por la misma
# razon: entre llegar un pelo antes o un pelo tarde, antes es preferible —
# tarde se ve como boca moviendose muda, que es justo lo que hay que evitar.
LEAD = 0.10

# Un hueco interno de al menos esto parte la linea: la boca PARA ahi, y meterle
# voz encima desincroniza todo lo que sigue. Se marca en el texto con "||".
PARTIR = 0.45

# Segundos que la BOCA se mueve antes de que H3 emita sonido. No se puede medir
# sobre la onda —ahi esta en cero— ni detectar en la imagen: lo intentamos y la
# region de mayor cambio entre fotogramas resulta ser el humo, no la boca. Se
# mide por ojo con hojas de contacto, una vez por plano, y se carga aca.
# El primer bloque de la linea se extiende hacia atras esa cantidad.
PRE = {11: 0.70,   # genio:    boca abre 176.54, su voz recien 177.24
       16: 0.85}   # vendedor: boca habla desde 257.50, su voz recien 258.37

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

def capa_no_verbal(guarda=0.15, min_dur=0.18, fusion=0.20):
    """Devuelve la voz de H3 SOLO donde no hay palabra transcrita.

    H3 hace bien lo que nace y muere dentro del plano: risas, gruñidos,
    exclamaciones. Eso vivia en vocals.wav y se descartaba entero junto con el
    habla. Aca se recupera enmascarando todo lo que Scribe transcribio —el
    habla que reemplazamos y el balbuceo en ingles que queda mudo a proposito—
    y dejando pasar el resto. Son 7 tramos, 4,6 s en total.
    """
    v, _ = sf.read("vocals.wav", dtype="float32")
    if v.ndim == 1: v = np.stack([v, v], 1)
    v = v[:N] if len(v) >= N else np.pad(v, ((0, N-len(v)), (0, 0)))
    r = uniform_filter1d(np.abs(v.mean(1)).astype(np.float32), int(0.03*SR))
    piso, pico = np.percentile(r, 20), np.percentile(r, 99.5)
    umb = piso + 0.10*(pico - piso)
    hab = np.zeros(N, bool)
    for w in PAL:
        a = max(0, int((w["start"]-guarda)*SR)); b = min(N, int((w["end"]+guarda)*SR))
        hab[a:b] = True
    cand = (r > umb) & (~hab)
    d = np.diff(cand.astype(np.int8))
    ini = np.where(d == 1)[0]+1; fin = np.where(d == -1)[0]+1
    if cand[0]: ini = np.r_[0, ini]
    if cand[-1]: fin = np.r_[fin, N]
    seg = [(i, j) for i, j in zip(ini, fin) if (j-i)/SR >= min_dur]
    fus = []
    for a, b in seg:
        if fus and (a - fus[-1][1])/SR < fusion: fus[-1] = (fus[-1][0], b)
        else: fus.append((a, b))
    out = np.zeros((N, 2), np.float32); nf = int(0.02*SR)
    for a, b in fus:
        x = v[a:b].copy()
        f = min(nf, len(x)//2)
        if f:
            ramp = np.linspace(0, 1, f, dtype=np.float32)[:, None]
            x[:f] *= ramp; x[-f:] *= ramp[::-1]
        out[a:b] = x
    print(f"capa no verbal: {len(fus)} tramos, {sum(b-a for a,b in fus)/SR:.1f}s")
    return out, fus


D = Path("voz4"); D.mkdir(exist_ok=True)
voz = np.zeros((N,2), np.float32); act = np.zeros(N, np.float32)
VOZ_ORIG = V.cargar("vocals.wav")
TMPD = Path(".")
for i,(t0,t1,pers,txts) in enumerate(F,1):
    if isinstance(txts, str): txts = [txts]
    sig = F[i][0] if i < len(F) else DUR
    bl = V.bloques(VOZ_ORIG, max(0.0, t0 - V.BACK), t1 + V.END_FWD)
    bl = [(x, min(y, sig - 0.06)) for x, y in bl if x < sig - 0.06]
    bl = [b for b in bl if min(b[1], t1) - max(b[0], t0) > 0] or [(t0, t1)]
    # Bloques separados por menos de PARTIR son pausas dentro de la misma
    # frase: se fusionan. Los demas son cortes reales de la boca.
    grupos = [[bl[0]]]
    for b in bl[1:]:
        (grupos[-1].append(b) if b[0] - grupos[-1][-1][1] < PARTIR else grupos.append([b]))
    tramos = [(g[0][0], g[-1][1]) for g in grupos]
    if i in PRE:
        # Se extiende el primer tramo hacia atras, no se crea uno nuevo.
        # Probado a crear un tramo propio para el suspiro y midio PEOR: en
        # 0,70 s ElevenLabs no dice nada —pedia 2,19x— mientras que el suspiro
        # pegado a la primera frase entra en 1,56x. El hueco de boca muda se
        # cubre con el arranque de la linea, no con un clip aparte.
        tramos[0] = (tramos[0][0] - PRE[i], tramos[0][1])

    partes = [t.split("||") for t in txts]
    if len(tramos) > 1 and not all(len(x) == len(tramos) for x in partes):
        print(f"{i:3d} !! {len(tramos)} bloques y el texto no esta partido en {len(tramos)}: "
              f"se coloca corrido (va a desincronizar despues de la pausa)")
        tramos = [(tramos[0][0], tramos[-1][1])]
        partes = [["".join(x)] for x in partes]

    print(f"{i:3d} {pers:9s} {len(tramos)} tramo(s)  " +
          " | ".join(f"{x:.2f}-{y:.2f}" for x, y in tramos))
    for m, (bx, by) in enumerate(tramos):
        span = max(0.2, by - bx)
        cand = [x[m].strip() for x in partes if x[m].strip()]
        # ElevenLabs rechaza con 400 un texto que sea SOLO una etiqueta: la
        # etiqueta dirige la entrega de algo, no es contenido. Necesita al
        # menos una vocalizacion.
        cand = [c for c in cand if re.sub(r"\[[^\]]*\]", "", c).strip()]
        if not cand:
            print(f"      (tramo {m} sin texto: queda el original)")
            continue
        mp3, txt, factor, tabla = SEL.elegir(cand, VOZ[pers], span,
            sintetizar_con_tiempos, D, f"H{i:02d}p{m}", FF, TMPD)
        a = wav(mp3, D/f"_x{i}_{m}.wav")
        tope = (tramos[m+1][0] if m+1 < len(tramos) else sig) - bx - 0.06
        a2, k = alinear(a, span, max(0.2, tope))
        pk = np.abs(a2).max()
        if pk > 0: a2 = a2 * (0.72/pk)
        j = max(0, int((bx - LEAD + AJUSTE.get(i, 0.0))*SR)); e = min(j+len(a2), N)
        voz[j:e] += a2[:e-j]
        g = int(0.4*SR); act[max(0,j-g):min(N,e+g)] = 1.0

nov, fus_nv = capa_no_verbal()
for a, b in fus_nv:                      # la musica tambien baja bajo una risa
    act[max(0,a-int(0.3*SR)):min(N,b+int(0.3*SR))] = 1.0

act = uniform_filter1d(act, int(0.25*SR), mode="constant")[:N]
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
mix = amb*0.85 + nov*0.85 + mus*0.42 + voz*1.0
p=np.abs(mix).max()
if p>0.99: mix*=0.99/p
sf.write("mezcla13.wav", mix, SR)
print(f"\nmezcla13.wav {len(mix)/SR:.2f}s", flush=True)
subprocess.run([str(FF),"-y","-loglevel","error",
    "-i", r"c:/Users/Yamil/Desktop/youtube proyect/pruebas video 2/Mejor H3/PELICULA.mp4",
    "-i","mezcla13.wav","-map","0:v:0","-map","1:a:0","-c:v","copy",
    "-af","loudnorm=I=-14:TP=-1.0:LRA=11","-c:a","aac","-b:a","256k","-ar","48000",
    "-movflags","+faststart","-shortest",
    r"C:/Users/Yamil/Desktop/Aladino doblado/Aladino - doblado v13.mp4"],
    check=True, stdin=subprocess.DEVNULL)
print("video listo")

# --- muestras para juzgar por oido, en los mismos puntos que las del v4 ---
V5 = Path(r"C:/Users/Yamil/Desktop/Aladino doblado/Aladino - doblado v13.mp4")
for t in (44, 127, 176, 216, 257, 279):
    subprocess.run([str(FF), "-y", "-loglevel", "error", "-ss", str(t), "-t", "14",
                    "-i", str(V5), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-c:a", "aac", "-b:a", "192k",
                    str(V5.parent / f"MUESTRA13_{t}s.mp4")], check=True, stdin=subprocess.DEVNULL)
    print(f"  MUESTRA13_{t}s.mp4")
