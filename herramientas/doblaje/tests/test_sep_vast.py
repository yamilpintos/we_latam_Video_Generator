# -*- coding: utf-8 -*-
"""sep_vast sin prender nada: ssh/scp FALSOS que registran qué se pidió. 0 créditos, 0 USD.

  S1  sin instancia registrada: disponible() False y separar() devuelve None (la app cae a "mezcla" y lo dice).
  S2  con instancia: sube el audio, corre el separador del motor con --backend local, baja las DOS pistas,
      y devuelve (vocals_clean.wav, music_effects.wav).
  S3  SIEMPRE borra allá el audio del cliente (rm -rf), aunque falle a mitad.
  S4  si el separador falla allá, devuelve None (no inventa pistas).
  S5  media.separar va a vast sólo con DOBLAJE_SEP_REMOTO=vast; sin eso, el camino de siempre.

Correr: cd plataforma/apps/doblaje && python -m tests.test_sep_vast
"""
import json, subprocess, sys, tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from doblaje import config as C, media, sep_vast as SV     # noqa: E402

C.GPU_MODO = "off"                                          # ★ nunca la GPU propia desde una prueba (ver tests/__init__)

F = []


def ok(c, e, d=""):
    print(("  OK   " if c else "  MAL  ") + e + (f"  ({d})" if d else ""))
    if not c:
        F.append(e)


class Falso:
    """Reemplaza subprocess.run dentro de sep_vast: ssh/scp que no salen de la PC."""
    def __init__(self, falla_sep=False):
        self.llamadas, self.falla_sep = [], falla_sep

    def __call__(self, cmd, **kw):
        self.llamadas.append(cmd)
        rc = 0
        if cmd[0] == "ssh" and "sep_replicate.py" in cmd[-1] and self.falla_sep:
            rc = 1
        if cmd[0] == "scp" and cmd[-1].endswith((".wav",)) and not cmd[-1].startswith("root@"):
            Path(cmd[-1]).write_bytes(b"RIFF")          # "baja" una pista
        return subprocess.CompletedProcess(cmd, rc, stdout="", stderr="")


tmp = Path(tempfile.mkdtemp())
audio = tmp / "in.wav"
audio.write_bytes(b"RIFF")
real_run, real_inst = SV.subprocess.run, SV.INSTANCIA

print("S1 · sin instancia")
SV.INSTANCIA = tmp / "no_existe.json"
logs = []
ok(not SV.disponible(), "S1a disponible() es False")
ok(SV.separar(audio, tmp / "o1", logs.append) is None and logs, "S1b separar() devuelve None y lo dice", logs[:1])

print("S2/S3 · con instancia (ssh/scp falsos)")
SV.INSTANCIA = tmp / "inst.json"
SV.INSTANCIA.write_text(json.dumps({"host": "ssh9.vast.ai", "port": 12345}), encoding="utf-8")
fa = Falso()
SV.subprocess.run = fa
r = SV.separar(audio, tmp / "o2", None)
ok(r is not None and r[0].name == "vocals_clean.wav" and r[1].name == "music_effects.wav", "S2a devuelve las dos pistas", str(r))
cmds = [" ".join(map(str, c)) for c in fa.llamadas]
ok(any("sep_replicate.py" in c and "--backend local" in c for c in cmds), "S2b corre el separador del motor con --backend local")
ok(sum(1 for c in fa.llamadas if c[0] == "scp" and not str(c[-1]).startswith("root@")) == 2, "S2c baja exactamente dos archivos")
ok("rm -rf /motor/sep_app/" in cmds[-1], "S3a al final borra allá el audio del cliente")

print("S4 · el separador falla allá")
fa = Falso(falla_sep=True)
SV.subprocess.run = fa
ok(SV.separar(audio, tmp / "o3", None) is None, "S4a devuelve None")
ok("rm -rf /motor/sep_app/" in " ".join(map(str, fa.llamadas[-1])), "S3b borra allá aunque haya fallado")
SV.subprocess.run, SV.INSTANCIA = real_run, real_inst

print("S5 · media.separar elige el camino por la perilla")
llamado = []
SV_sep = SV.separar
SV.separar = lambda a, o, l=None: llamado.append("vast") or None
C.SEP_REMOTO = "vast"
media.separar(audio, tmp / "o4")
ok(llamado == ["vast"], "S5a con SEP_REMOTO=vast va a vast")
C.SEP_REMOTO = ""
llamado.clear()
C_sep = C.SEPARADOR
C.SEPARADOR = str(tmp / "no_hay_separador.py")                 # camino local sin separador: None sin ir a vast
ok(media.separar(audio, tmp / "o5") is None and not llamado, "S5b sin la perilla NO va a vast")
C.SEPARADOR, SV.separar = C_sep, SV_sep

print()
if F:
    print(f"[MAL] {F}")
    raise SystemExit(1)
print("[OK] todas las pruebas pasan · 0 créditos · nada prendido")
