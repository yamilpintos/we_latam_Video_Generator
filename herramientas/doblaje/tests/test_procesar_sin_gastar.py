# -*- coding: utf-8 -*-
"""web._procesar de punta a punta con ElevenLabs, Drive y el separador FALSOS: 0 créditos, 0 USD, nada prendido.

  P1  camino feliz por pistas: sube el PROVISORIO por mezcla antes de separar, separa (falso), mezcla, verifica,
      sube el definitivo + informe y BORRA el provisorio; el libro tiene proyecto e idioma con origen "web";
      el informe trae cobro_medido y nivel.modo == "pistas"
  P2  guarda 7 al momento de crear el proyecto: con la reserva imposible el trabajo queda FRENADO y no se crea nada
  P3  cobro medido muy por encima del estimado: el trabajo termina, pero el gasto queda PAUSADO y el trabajo lo dice
  P4  sin separador ni GPU: modo mezcla, sin provisorio

Correr: cd plataforma/apps/doblaje && python -m tests.test_procesar_sin_gastar
"""
import json, shutil, subprocess, sys, tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from doblaje import config as C, creditos as K, drive, media, web    # noqa: E402
from doblaje.dubbing import Cuenta                                    # noqa: E402

F = []


def ok(c, e, d=""):
    print(("  OK   " if c else "  MAL  ") + e + (f"  ({d})" if d else ""))
    if not c:
        F.append(e)


tmp = Path(tempfile.mkdtemp())
C.TRABAJO = tmp / "trabajo"
K.LEDGER, K.PAUSA = C.TRABAJO / "ledger.jsonl", C.TRABAJO / "pausa.json"
web.TRABAJOS_JSON = C.TRABAJO / "trabajos.json"
C.GPU_MODO = "off"
C.MAX_CR_POR_TRABAJO, C.MAX_CR_POR_DIA, C.RESERVA_CR, C.TOLERANCIA_COBRO = 1_200_000, 2_000_000, 50_000, 0.25

# un clip sintético de 8 s (mira de video + "voz" de tonos con ruido) para que ffmpeg y la verificación tengan con
# qué trabajar en cualquier máquina (antes usaba un mp4 de Videos de Prueba, que en La Fábrica no existe)
clip = tmp / "clip.mp4"
subprocess.run([C.FFMPEG, "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=25",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100", "-f", "lavfi", "-i", "anoisesrc=color=pink:sample_rate=44100:amplitude=0.05",
                "-filter_complex", "[1:a]tremolo=f=3:d=0.8,volume=0.4[v];[v][2:a]amix=inputs=2:normalize=0,aformat=channel_layouts=stereo[a]",
                "-map", "0:v", "-map", "[a]", "-t", "8", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(clip)], check=True)
SEGS = [dict(start_s=0.5, end_s=3.0, text="hola"), dict(start_s=4.0, end_s=7.0, text="chau")]


class ElevenFalso(Cuenta):
    """La misma clase que usa la web, con el HTTP reemplazado: el saldo baja lo que digamos al crear proyecto/idioma."""
    def __init__(self, saldo=1_000_000, cobro_proyecto=0, cobro_idioma=1800):
        super().__init__("sk_falsa_c114", "principal", origen="web")
        self._saldo, self.cp, self.ci, self.creados = saldo, cobro_proyecto, cobro_idioma, []

    def _req(self, metodo, ruta, reintentos=6, **kw):
        if ruta == "/v1/user/subscription":
            return dict(character_limit=2_000_000, character_count=2_000_000 - self._saldo, tier="scale")
        if ruta == "/v1/dubbing/project":
            self._saldo -= self.cp; self.creados.append("proyecto"); return dict(project_id="proj_f")
        if ruta == "/v1/dubbing/project/proj_f":
            return dict(status="ready")
        if ruta == "/v1/dubbing/project/proj_f/language":
            self._saldo -= self.ci; self.creados.append("idioma"); return dict(language_id="lang_f")
        if ruta == "/v1/dubbing/project/proj_f/language/lang_f":
            return dict(status="completed", outputs=dict(lossless_audio="fake://audio"))
        if ruta == "/v1/dubbing/project/proj_f/transcript":
            return dict(segments=SEGS)
        if ruta == "/v1/dubbing/project/proj_f/language/lang_f/transcript":
            return dict(segments=[dict(start_s=s["start_s"], end_s=s["end_s"], source_text=s["text"], translation="x") for s in SEGS])
        raise AssertionError(ruta)

    @staticmethod
    def bajar_audio(url, dst):
        # "el doblado": el mismo audio del clip, 3 dB más fuerte (v2 sube la voz), como wav
        subprocess.run([C.FFMPEG, "-y", "-v", "error", "-i", str(clip), "-vn", "-af", "volume=3dB", "-ar", "44100", "-c:a", "pcm_s16le", str(dst)], check=True)
        return dst


class DriveFalso:
    """Lo que la web le pide a Drive, sobre una carpeta local. Registra subidas y borrados."""
    def __init__(self):
        self.carpeta = tmp / "drive"; self.carpeta.mkdir(exist_ok=True)
        self.subidos, self.borrados, self._n = [], [], 0

    def bajar(self, d, fid, dst, cb=None):
        shutil.copyfile(clip, dst); cb and cb(1.0); return dst

    def carpeta_salida(self, d, padre, nombre):
        return "carpeta_doblaje"

    def subir(self, d, ruta, cid):
        self._n += 1; shutil.copyfile(ruta, self.carpeta / ruta.name); self.subidos.append(ruta.name); return f"id{self._n}"

    def borrar(self, d, fid):
        self.borrados.append(fid); return True


def separar_falso(audio, out_dir, log=None):
    """Voz = el audio; fondo = el audio a −20 dB. Suficiente para que la mezcla y las medidas corran."""
    out_dir.mkdir(parents=True, exist_ok=True)
    v, f = out_dir / "vocals_clean.wav", out_dir / "music_effects.wav"
    shutil.copyfile(audio, v)
    subprocess.run([C.FFMPEG, "-y", "-v", "error", "-i", str(audio), "-af", "volume=-20dB", str(f)], check=True)
    return v, f


def correr(cuenta, con_separador=True, provisorio=True):
    dr = DriveFalso()
    web._drive = lambda s: None
    web._cuenta = lambda nombre: cuenta
    drive.bajar, drive.carpeta_salida, drive.subir, drive.borrar = dr.bajar, dr.carpeta_salida, dr.subir, dr.borrar
    media.separador_disponible = (lambda: True) if con_separador else (lambda: False)
    media.separar = separar_falso
    C.PROVISORIO = provisorio
    t = dict(id="t1", video_id="v1", nombre="clip.mp4", padre="p", tamano=clip.stat().st_size, duracion_s=8.0, motor="eleven_v2",
             origen="es", destino="pt-BR", clonacion=1, cuenta="principal", keyterms=[], estimado=1766, destino_carpeta=None,
             destino_nombre=None, estado="en cola", etapa="", progreso=0.0, log=[], creado="2026-09-26 00:00:00", usuario="u",
             carpeta_salida_id=None, salidas=[], informe=None, error=None)
    web._trabajos.clear(); web._trabajos["t1"] = t
    web._procesar(t, {})
    return t, dr


print("P1 · camino feliz por pistas, con provisorio")
K.LEDGER.unlink(missing_ok=True); K.PAUSA.unlink(missing_ok=True)
el = ElevenFalso()
t, dr = correr(el)
ok(t["estado"] in ("listo", "revisar"), "P1a termina", f"{t['estado']} {t.get('error')}")
ok(dr.subidos[0].endswith("_PROVISORIO_mezcla.mp4"), "P1b lo primero que subió fue el provisorio por mezcla", str(dr.subidos))
ok(dr.subidos[-2:] == ["clip_ptBR.mp4", "clip_ptBR_informe.json"], "P1c después el definitivo y el informe", str(dr.subidos))
ok(dr.borrados == ["id1"] and t.get("provisorio") is None, "P1d y borró el provisorio de Drive", str(dr.borrados))
ev = K.leer()
ok([e["tipo"] for e in ev] == ["proyecto", "idioma"] and all(e["origen"] == "web" for e in ev), "P1e libro: proyecto + idioma, origen web", str([e["tipo"] for e in ev]))
ok(ev[1]["cobro"] == 1800 and ev[1]["estimado"] == 1766, "P1f el cobro del idioma quedó medido en el libro", str(ev[1]))
inf = t["informe"]
ok(inf.get("cobro_medido") == 1800 and inf["cobro"] == 1800, "P1g informe: cobro medido", str(inf.get("cobro_medido")))
ok((inf.get("nivel") or {}).get("modo") == "pistas", "P1h nivel por pistas", str((inf.get("nivel") or {}).get("modo")))
ok(not K.pausado(), "P1i +34 cr sobre 1.766 no pausa nada")
ok(el.creados == ["proyecto", "idioma"], "P1j se creó UN proyecto y UN idioma")

print("P2 · frenado por la guarda antes de crear el proyecto")
C.RESERVA_CR = 5_000_000
el = ElevenFalso()
t, dr = correr(el)
ok(t["estado"] == "frenado" and "reserva" in (t.get("error") or ""), "P2a queda frenado y dice por qué", f"{t['estado']}: {str(t.get('error'))[:80]}")
ok(el.creados == [] and dr.subidos == [], "P2b no se creó nada ni se subió nada")
C.RESERVA_CR = 50_000

print("P3 · cobro medido mucho mayor que el estimado → pausa")
K.LEDGER.unlink(missing_ok=True)
el = ElevenFalso(cobro_idioma=9000)
t, dr = correr(el)
ok(t["estado"] in ("listo", "revisar") and t.get("alerta"), "P3a termina pero avisa", str(t.get("alerta"))[:80])
ok(K.pausado() and "9,000" in K.pausado()["motivo"], "P3b el gasto quedó pausado con el motivo", str(K.pausado())[:100])
el2 = ElevenFalso()
t2, _ = correr(el2)
ok(t2["estado"] == "frenado" and "PAUSADO" in t2["error"], "P3c el siguiente trabajo queda frenado por la pausa")
K.reanudar("test")

print("P4 · sin separador: mezcla, sin provisorio")
el = ElevenFalso()
t, dr = correr(el, con_separador=False)
ok(t["estado"] in ("listo", "revisar") and (t["informe"].get("nivel") or {}).get("modo") == "mezcla", "P4a modo mezcla")
ok(not any("PROVISORIO" in x for x in dr.subidos), "P4b no hubo provisorio")

print()
print("TODO OK" if not F else f"FALLAN {len(F)}: {F}")
sys.exit(1 if F else 0)
