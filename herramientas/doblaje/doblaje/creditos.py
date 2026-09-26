# -*- coding: utf-8 -*-
"""CONTROL DE CRÉDITOS de ElevenLabs: libro mayor, topes y pausa. Lo usan la web Y los scripts de la PC.

POR QUÉ (26-sep). La cuenta business quedó activa (1,8 M de créditos por mes) y Dubbing v2 cobra al crear el
proyecto/idioma: 13.245 cr por minuto de fuente. Un video mal elegido, una tanda repetida o una sesión paralela
gastando en la misma clave (8-sep: 238.400 cr de otra sesión mataron una corrida) no se pueden deshacer.
Acá vive UNA sola política, y cada guarda es independiente:

  1. libro mayor `ledger_creditos.jsonl`: TODO cobro pasa por `Cuenta.crear_proyecto/crear_idioma` (dubbing.py),
     que miden el saldo antes y después y lo anotan con quién lo pidió (web / script) y para qué.
  2. tope por trabajo (MAX_CR_POR_TRABAJO) — nadie manda una película de 3 h sin subir la perilla a propósito
  3. tope por día (MAX_CR_POR_DIA) — sumando lo estimado de lo que está en curso
  4. reserva (RESERVA_CR) — el saldo nunca baja de ahí: queda margen para parches y regeneraciones
  5. PAUSA automática cuando un cobro medido supera lo estimado en más de TOLERANCIA_COBRO: nada más se manda
     hasta que una persona lo reanude (`POST /api/gasto/reanudar` o `python saldo.py --reanudar`)
  6. `python saldo.py`: qué hay en cada clave, qué se gastó hoy, qué GPU está viva. ANTES de gastar desde un chat.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import date
from pathlib import Path

from . import config as C

LEDGER = C.TRABAJO / "ledger_creditos.jsonl"
PAUSA = C.TRABAJO / "gasto_pausado.json"


# ── libro mayor ────────────────────────────────────────────────────────────────────────────────
def registrar(**ev) -> dict:
    """Una línea en el libro: ts, cuenta, origen, referencia, tipo, estimado, saldo_antes, saldo_despues, cobro."""
    ev.setdefault("ts", time.strftime("%Y-%m-%d %H:%M:%S"))
    if ev.get("cobro") is None and ev.get("saldo_antes") is not None and ev.get("saldo_despues") is not None:
        ev["cobro"] = int(ev["saldo_antes"]) - int(ev["saldo_despues"])
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(ev, ensure_ascii=False) + "\n")
    return ev


def leer(desde: str | None = None) -> list[dict]:
    if not LEDGER.exists():
        return []
    out = []
    for l in LEDGER.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(l)
        except Exception:
            continue
        if not desde or str(e.get("ts", "")) >= desde:
            out.append(e)
    return out


def hoy() -> dict:
    """Lo de hoy: estimado (lo que se pidió), cobrado (lo medido), cuántos cobros, por cuenta."""
    d = date.today().isoformat()
    ev = [e for e in leer(d) if e.get("tipo") in ("proyecto", "idioma", "cobro")]
    por_cuenta: dict[str, dict] = {}
    for e in ev:
        c = por_cuenta.setdefault(str(e.get("cuenta") or "?"), dict(estimado=0, cobrado=0, n=0))
        c["estimado"] += int(e.get("estimado") or 0)
        c["cobrado"] += max(0, int(e.get("cobro") or 0))
        c["n"] += 1
    return dict(fecha=d, estimado=sum(c["estimado"] for c in por_cuenta.values()),
                cobrado=sum(c["cobrado"] for c in por_cuenta.values()), n=len(ev), por_cuenta=por_cuenta)


# ── pausa ──────────────────────────────────────────────────────────────────────────────────────
def pausado() -> dict | None:
    try:
        return json.loads(PAUSA.read_text(encoding="utf-8"))
    except Exception:
        return None


def pausar(motivo: str) -> dict:
    PAUSA.parent.mkdir(parents=True, exist_ok=True)
    d = dict(motivo=motivo, desde=time.strftime("%Y-%m-%d %H:%M:%S"))
    PAUSA.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    registrar(tipo="pausa", motivo=motivo)
    return d


def reanudar(quien: str = "") -> bool:
    if not PAUSA.exists():
        return False
    PAUSA.unlink()
    registrar(tipo="reanudar", quien=quien)
    return True


# ── las guardas ────────────────────────────────────────────────────────────────────────────────
def puede_gastar(libres: int, estimado: int, comprometido: int = 0, mayor: int | None = None) -> tuple[bool, str]:
    """¿Se puede mandar algo que cuesta `estimado` con `libres` de saldo? `comprometido` = lo estimado de lo que ya
    está en curso y todavía no se cobró; `mayor` = el trabajo más caro de la tanda (default: `estimado`)."""
    p = pausado()
    if p:
        return False, f"el gasto está PAUSADO desde {p['desde']}: {p['motivo']}. Reanudalo desde la web (Gasto → Reanudar) o `python saldo.py --reanudar`"
    mayor = estimado if mayor is None else mayor
    if mayor > C.MAX_CR_POR_TRABAJO:
        return False, (f"un solo trabajo de ~{mayor:,} créditos supera el tope por trabajo ({C.MAX_CR_POR_TRABAJO:,}); "
                       f"es una guarda de gasto: se sube con DOBLAJE_MAX_CR_POR_TRABAJO")
    h = hoy()
    usado_hoy = max(h["estimado"], h["cobrado"])
    if usado_hoy + comprometido + estimado > C.MAX_CR_POR_DIA:
        return False, (f"tope por día: hoy van ~{usado_hoy:,} + {comprometido:,} en curso + {estimado:,} pedidos "
                       f"> {C.MAX_CR_POR_DIA:,} (DOBLAJE_MAX_CR_POR_DIA)")
    if libres - comprometido - estimado < C.RESERVA_CR:
        return False, (f"quedarían {libres - comprometido - estimado:,} créditos y la reserva es {C.RESERVA_CR:,} "
                       f"(hay {libres:,}, {comprometido:,} comprometidos, {estimado:,} pedidos)")
    return True, "ok"


def controlar_cobro(estimado: int, cobro: int | None, referencia: str = "") -> str | None:
    """Después de cobrar: si lo medido supera lo estimado más de la tolerancia (y más de 5.000 cr), PAUSA todo
    y devuelve el aviso. Un cobro mayor al esperado es la señal de una tarifa distinta o de otra sesión gastando."""
    if cobro is None or estimado <= 0:
        return None
    exceso = cobro - estimado
    if exceso > max(5000, estimado * C.TOLERANCIA_COBRO):
        m = (f"cobro medido {cobro:,} vs estimado {estimado:,} (+{exceso:,}, {exceso / estimado:+.0%}) en {referencia}: "
             f"o la tarifa cambió o hay otra sesión gastando en la misma clave")
        pausar(m)
        return m
    return None


# ── claves y resumen ───────────────────────────────────────────────────────────────────────────
def claves_conocidas() -> list[tuple[str, str, str]]:
    """[(etiqueta, clave, dónde)] de ElevenLabs: las del entorno (las que usa la web) y las de los .env, activas
    o comentadas (la PC guarda la business comentada y la trial activa en dubai_v2/.env)."""
    out, vistas = [], set()
    for var, et in C.CUENTAS:
        k = os.getenv(var, "").strip()
        if k and k not in vistas:
            out.append((et, k, f"entorno {var}")); vistas.add(k)
    for f in (C.RAIZ / ".env", C.FOTON / "dubai_v2" / ".env"):
        if f.exists():
            for m in re.finditer(r"^(#\s*)?(ELEVENLABS_API_KEY\w*)\s*=\s*['\"]?(sk_[A-Za-z0-9_-]+)",
                                 f.read_text(encoding="utf-8", errors="replace"), re.M):
                k = m.group(3)
                if k not in vistas:
                    out.append((m.group(2), k, f"{f.parent.name}/.env ({'comentada' if m.group(1) else 'activa'})")); vistas.add(k)
    return out


def resumen(cuentas=None) -> dict:
    """Para la web y para saldo.py: saldos, hoy, topes, pausa y últimos movimientos."""
    from .dubbing import Cuenta, DubbingError
    saldos = []
    for c in (cuentas or []):
        try:
            s = c.saldo()
            saldos.append(dict(cuenta=c.etiqueta, termina=c.termina, libres=s["libres"], limite=s["limite"], plan=s.get("plan"),
                               renueva=time.strftime("%d/%m %H:%M", time.localtime(s["renueva_unix"])) if s.get("renueva_unix") else None))
        except DubbingError as e:
            saldos.append(dict(cuenta=c.etiqueta, termina=c.termina, error=str(e)[:160]))
    return dict(saldos=saldos, hoy=hoy(), pausa=pausado(),
                topes=dict(por_trabajo=C.MAX_CR_POR_TRABAJO, por_dia=C.MAX_CR_POR_DIA, reserva=C.RESERVA_CR,
                           tolerancia=C.TOLERANCIA_COBRO, cr_por_min=C.CR_POR_MIN),
                ultimos=[e for e in leer()[-20:] if e.get("tipo") in ("proyecto", "idioma", "cobro", "pausa", "reanudar")])


def main(argv: list[str] | None = None):
    """python saldo.py [--reanudar] [--json]: el estado de la plata, para leer ANTES de gastar desde un chat."""
    from .dubbing import Cuenta
    from . import gpu_vast
    argv = sys.argv[1:] if argv is None else argv
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if "--reanudar" in argv:
        print("pausa levantada" if reanudar("saldo.py") else "no había pausa")
    cuentas = [Cuenta(k, f"{et} …{k[-4:]} ({donde})", origen="saldo.py") for et, k, donde in claves_conocidas()]
    r = resumen(cuentas)
    if "--json" in argv:
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return
    print("== ElevenLabs")
    for s in r["saldos"]:
        if "error" in s:
            print(f"   {s['cuenta']}: ERROR {s['error']}")
        else:
            print(f"   {s['cuenta']}: {s['libres']:,} libres de {s['limite']:,} · plan {s['plan']} · renueva {s['renueva']}")
    h = r["hoy"]
    print(f"== hoy {h['fecha']}: estimado {h['estimado']:,} · cobrado {h['cobrado']:,} · {h['n']} cobros")
    for c, v in h["por_cuenta"].items():
        print(f"   {c}: estimado {v['estimado']:,} · cobrado {v['cobrado']:,} ({v['n']})")
    t = r["topes"]
    print(f"== topes: por trabajo {t['por_trabajo']:,} · por día {t['por_dia']:,} · reserva {t['reserva']:,} · tolerancia {t['tolerancia']:.0%}")
    if r["pausa"]:
        print(f"== ★ GASTO PAUSADO desde {r['pausa']['desde']}: {r['pausa']['motivo']}  (levantar: python saldo.py --reanudar)")
    if r["ultimos"]:
        print("== últimos movimientos")
        for e in r["ultimos"][-10:]:
            print(f"   {e.get('ts')}  {e.get('tipo'):9s} {str(e.get('cobro') if e.get('cobro') is not None else '-'):>9s}  "
                  f"est {str(e.get('estimado') or '-'):>8s}  {e.get('origen', '')} {str(e.get('referencia') or e.get('motivo') or '')[:60]}")
    g = gpu_vast.estado()
    print("== GPU vast:", "no configurada" if not g["configurada"] else f"modo {g['modo']} · fase {g['fase']}"
          + (f" · instancia {g['instancia']['id']} {g['instancia']['gpu']} USD {g['instancia']['usd_h']}/h, {g['instancia']['horas']} h ≈ USD {g['instancia']['usd']}"
             if g.get("instancia") else " · ninguna viva") + f" · hoy USD {g.get('usd_hoy') or 0:.2f} de {g['topes']['usd_dia']:.2f}")
    if g["configurada"]:
        try:
            otras = [i for i in gpu_vast.instancias_vivas() if not (g.get("instancia") and i.get("id") == g["instancia"]["id"])]
            for i in otras:
                print(f"   otra instancia de la cuenta (NO se toca): {i.get('id')} {i.get('gpu_name')} USD {i.get('dph_total')}/h {i.get('actual_status')}")
        except Exception as e:
            print("   (no pude listar las instancias de vast:", str(e)[:100] + ")")


if __name__ == "__main__":
    main()
