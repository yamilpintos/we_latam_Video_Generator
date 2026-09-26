# -*- coding: utf-8 -*-
"""creditos.py + el libro en Cuenta, sin tocar ElevenLabs (HTTP falso). 0 créditos.

  C1  puede_gastar: reserva, tope por trabajo, tope por día (con lo comprometido) y pausa
  C2  controlar_cobro: dentro de la tolerancia no pasa nada; pasado, PAUSA y lo dice; reanudar levanta la pausa
  C3  Cuenta.crear_proyecto / crear_idioma anotan en el libro saldo antes/después, cobro, origen y referencia
  C4  hoy() suma por cuenta lo estimado y lo cobrado

Correr: cd plataforma/apps/doblaje && python -m tests.test_creditos
"""
import sys, tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from doblaje import config as C, creditos as K, dubbing     # noqa: E402

F = []


def ok(c, e, d=""):
    print(("  OK   " if c else "  MAL  ") + e + (f"  ({d})" if d else ""))
    if not c:
        F.append(e)


tmp = Path(tempfile.mkdtemp())
K.LEDGER, K.PAUSA = tmp / "ledger.jsonl", tmp / "pausa.json"
C.MAX_CR_POR_TRABAJO, C.MAX_CR_POR_DIA, C.RESERVA_CR, C.TOLERANCIA_COBRO = 1_200_000, 2_000_000, 50_000, 0.25

print("C1 · puede_gastar")
ok(K.puede_gastar(1_000_000, 100_000)[0], "C1a con saldo de sobra: ok")
r = K.puede_gastar(140_000, 100_000)
ok(not r[0] and "reserva" in r[1], "C1b tocaría la reserva: no", r[1][:70])
r = K.puede_gastar(5_000_000, 1_500_000)
ok(not r[0] and "tope por trabajo" in r[1], "C1c un trabajo de 1,5 M: no", r[1][:70])
r = K.puede_gastar(5_000_000, 900_000, comprometido=0, mayor=900_000)
ok(r[0], "C1d dos de 900 k en una tanda (1,8 M): pasa el tope por trabajo (el mayor es 900 k)")
r = K.puede_gastar(5_000_000, 1_100_000, comprometido=1_000_000)
ok(not r[0] and "tope por día" in r[1], "C1e 1,0 M en curso + 1,1 M pedidos > 2 M/día: no", r[1][:70])
K.pausar("prueba")
r = K.puede_gastar(5_000_000, 10)
ok(not r[0] and "PAUSADO" in r[1], "C1f pausado: no, aunque sea barato")
ok(K.reanudar("test") and K.puede_gastar(5_000_000, 10)[0], "C1g reanudar levanta la pausa")

print("C2 · controlar_cobro")
ok(K.controlar_cobro(100_000, 110_000, "x") is None and not K.pausado(), "C2a +10 %: nada")
ok(K.controlar_cobro(100_000, None, "x") is None, "C2b sin medición: nada")
m = K.controlar_cobro(100_000, 140_000, "peli")
ok(m and "+40,000" in m.replace(".", ",") and K.pausado() and "peli" in K.pausado()["motivo"], "C2c +40 %: pausa y lo dice", (m or "")[:80])
K.reanudar()
ok(K.controlar_cobro(10_000, 14_000, "x") is None, "C2d +4.000 sobre 10.000 (< 5.000 cr): no pausa por chico")

print("C3 · Cuenta anota en el libro")
saldos = iter([1_000_000, 900_000, 900_000, 850_000])


def req_falso(self, metodo, ruta, reintentos=6, **kw):
    if ruta == "/v1/user/subscription":
        return dict(character_limit=2_000_000, character_count=2_000_000 - next(saldos))
    if ruta == "/v1/dubbing/project":
        return dict(project_id="proj_1")
    if ruta.endswith("/language"):
        return dict(language_id="lang_1")
    raise AssertionError(ruta)


dubbing.Cuenta._req = req_falso
K.LEDGER.unlink(missing_ok=True)
vid = tmp / "v.mp4"
vid.write_bytes(b"0")
c = dubbing.Cuenta("sk_abcdefghc114", "business", origen="cli:test")
pid = c.crear_proyecto(vid, "en", "doblaje :: v.mp4", [], estimado=95_000)
lid = c.crear_idioma(pid, "es-MX", 5, estimado=95_000, referencia="doblaje :: v.mp4")
ev = K.leer()
ok(len(ev) == 2 and ev[0]["tipo"] == "proyecto" and ev[1]["tipo"] == "idioma", "C3a dos líneas: proyecto e idioma", str([e["tipo"] for e in ev]))
ok(ev[0]["saldo_antes"] == 1_000_000 and ev[0]["saldo_despues"] == 900_000 and ev[0]["cobro"] == 100_000, "C3b cobro del proyecto medido", str(ev[0]))
ok(ev[1]["cobro"] == 50_000 and ev[1]["destino"] == "es-MX" and ev[1]["language_id"] == "lang_1", "C3c cobro del idioma medido", str(ev[1]))
ok(ev[0]["cuenta"] == "business…c114" and ev[0]["origen"] == "cli:test" and ev[0]["referencia"] == "doblaje :: v.mp4", "C3d cuenta, origen y referencia")

print("C4 · hoy()")
h = K.hoy()
ok(h["estimado"] == 190_000 and h["cobrado"] == 150_000 and h["n"] == 2, "C4a suma estimado y cobrado", str(h))
ok("business…c114" in h["por_cuenta"], "C4b por cuenta")

print()
print("TODO OK" if not F else f"FALLAN {len(F)}: {F}")
sys.exit(1 if F else 0)
