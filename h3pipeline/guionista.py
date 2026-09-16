"""El traductor: del guion del usuario al `proyecto.json` que consume el pipeline.

El guion lo escribe la persona. Esto NO inventa la historia: la convierte al
formato técnico (planos con `ve`/`mueve`/`audio`, tamaños, locaciones, líneas
de voz) aplicando la ley de la estructura elegida, y la valida con el mismo
`construir` de siempre. Si salen avisos, se los devuelve al modelo con el JSON
para que corrija, hasta dos veces. La persona ve el resultado validado.

Es lo que antes se hacía a mano: copiar la instrucción de la Mesa de Armado,
pegarla en un chat, traer el JSON. La instrucción es la misma
(PROMPT-GUIONISTA-SHORT/LARGO + `Estructura.brief()`); sólo cambia que la
llamada la hace el servidor, con la clave `openai` del `.env`.

    from h3pipeline import guionista
    r = guionista.traducir(guion, formato="short", estructura="short", ...)
    r["proyecto"]  → dict listo para guardar
    r["avisos"]    → lo que quedó sin resolver tras los reintentos
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path

from . import config, grilla
from .estructura import Estructura
from .proyecto import Proyecto, ProyectoInvalido

RAIZ = Path(__file__).resolve().parent.parent
API = "https://api.openai.com/v1/chat/completions"
MODELO = "gpt-5.1"          # el que hay en la cuenta (16/9/2026); gpt-4.1 de respaldo
MODELO_RESPALDO = "gpt-4.1"

# Voces conocidas de ElevenLabs, con su ritmo MEDIDO. La densidad se calcula
# contra la voz elegida, nunca contra los 17 cps teóricos (regla 40).
VOCES = {
    "kate":  {"id": "EYBbN7OENxAX5QX56IiW", "cps": 16.7, "nombre": "Kate (16,7 cps)"},
    "pablo": {"id": "JXKQ929SO0LLl7spbEAI", "cps": 10.5, "nombre": "Pablo, argentino (10,5 cps)"},
}


class ErrorGuionista(RuntimeError):
    pass


# ───────────────────────────────────────────────────────────── la instrucción

def _prompt_base(formato_narrativo: str) -> str:
    """El PROMPT-GUIONISTA correspondiente, sin la sección «LA HISTORIA» ni la
    ley pegada al final (la ley se regenera desde el módulo)."""
    nombre = "PROMPT-GUIONISTA-LARGO.md" if formato_narrativo == "largo" else "PROMPT-GUIONISTA-SHORT.md"
    t = (RAIZ / nombre).read_text(encoding="utf-8")
    t = t.split("## LA HISTORIA")[0]
    # Corrección de lo que el manual resolvió (14/9): el clip es 5,17 s siempre.
    t = re.sub(r"redondeado a la grilla\s*\{5\.2, 5\.9, 6\.6\}\. \*\*Nunca más de 6,6\.\*\*",
               "y `segundos` es SIEMPRE 5.17 (el único largo sin fallos en 32 GB). "
               "**Ningún `corta` puede pasar de 4,8 s.**", t)
    return t


def instruccion(guion: str, *, formato: str, estructura: str, estilo_imagen: str,
                estilo_video: str = "", cierre_video: str = "", medio: str = "",
                voz: str | None = "kate", titulo: str = "", negativos: bool = True,
                notas: str = "") -> str:
    est = Estructura.cargar(estructura)
    narrativo = "largo" if (formato == "largo" and not est.nombre.startswith("loop")) else "short"
    L = [_prompt_base(narrativo).strip(), ""]
    L.append("## LO QUE FIJA EL DIRECTOR (no lo cambies)")
    L.append(f"- `formato`: \"{formato}\" · `estructura`: \"{estructura}\"" +
             (f" · `titulo`: \"{titulo}\"" if titulo else ""))
    L.append(f"- `estilo_imagen` (usalo textual): {estilo_imagen}")
    if estilo_video:
        L.append(f"- `estilo_video` (textual): {estilo_video}")
    if cierre_video:
        L.append(f"- `cierre_video` (textual): {cierre_video}")
    if medio:
        L.append(f"- `medio` (textual): {medio}")
    if voz and voz in VOCES:
        v = VOCES[voz]
        L.append(f"- La voz en off es {v['nombre']}: escribí cada línea a MÁXIMO {v['cps'] * 0.92:.0f} "
                 f"caracteres por segundo de su ventana (la ventana llega hasta donde arranca "
                 f"la línea siguiente). Ejemplo: una línea que arranca en un plano de 3 s "
                 f"tiene lugar para {int(3 * v['cps'] * 0.92)} caracteres, no más. Esto es lo "
                 f"que más se falla: contá los caracteres. Declará "
                 f"`\"voces\": {{\"narrador\": \"{v['id']}\"}}`.")
    elif voz is None:
        L.append("- NO hay voz en off: no escribas `voz`. El gancho lo cargan imagen, sonido y texto.")
    L.append(f"- `segundos` de TODOS los planos: {grilla.MINIMO:.2f}. `corta` ≤ 4.8. "
             f"Si una idea necesita más, son dos planos.")
    if not negativos:
        L.append("- Es una escena quieta y sin gente: agregá `\"negativos\": false` y describí sólo lo "
                 "que SÍ pasa (nunca «no hay X»). Los audios en positivo: «The only sounds are…».")
    L.append("- Todo `ve`, `mueve`, `audio` y los prompts de `madre` en INGLÉS; `funcion`, `voz` y "
             "`texto` en castellano rioplatense.")
    if notas.strip():
        L.append(f"- Notas del director: {notas.strip()}")
    L.append("")
    L.append("## LA HISTORIA (el guion del director; respetalo, no lo reescribas)")
    L.append("")
    L.append(guion.strip())
    L.append("")
    L.append("---")
    L.append("")
    L.append("# LA LEY (cumplila tramo por tramo; los «huecos sugeridos» son el esqueleto)")
    L.append("")
    L.append(est.brief())
    L.append("")
    L.append("Devolvé ÚNICAMENTE el JSON del proyecto, sin prosa ni bloques de código.")
    return "\n".join(L)


# ───────────────────────────────────────────────────────────── OpenAI

def _llamar(mensajes: list[dict], modelo: str = MODELO, clave: str | None = None) -> str:
    config.certificados()
    k = clave or config.leer_env("OPENAI_API_KEY")
    cuerpo = {"model": modelo, "messages": mensajes,
              "response_format": {"type": "json_object"}}
    if not modelo.startswith("gpt-5"):
        cuerpo["temperature"] = 0.4
    req = urllib.request.Request(API, data=json.dumps(cuerpo).encode(),
                                 headers={"Authorization": f"Bearer {k}",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            d = json.load(r)
    except urllib.error.HTTPError as e:
        detalle = e.read().decode("utf-8", "replace")[:600]
        if modelo != MODELO_RESPALDO and e.code in (400, 404):
            return _llamar(mensajes, MODELO_RESPALDO, clave)
        raise ErrorGuionista(f"OpenAI HTTP {e.code}: {detalle}") from e
    return d["choices"][0]["message"]["content"]


def _json(texto: str) -> dict:
    texto = texto.strip()
    if texto.startswith("```"):
        texto = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto, flags=re.S)
    i, j = texto.find("{"), texto.rfind("}")
    if i < 0 or j < 0:
        raise ErrorGuionista("el modelo no devolvió un JSON")
    return json.loads(texto[i:j + 1])


# ───────────────────────────────────────────────────────────── el traductor

def densidad_contra_voz(p: Proyecto, cps_voz: float, tolerancia: float = 1.05) -> list[str]:
    """Las líneas que no entran en su ventana AL RITMO MEDIDO de la voz elegida.

    Es la regla 40 hecha chequeo: el validador general usa 17 cps teóricos y un
    máximo de 22, con lo que una línea de 67 caracteres en 3,1 s «entra». Con
    Pablo, que corre a 10,5 cps, esa línea dura 6,4 s. Acá se calcula contra la
    voz de verdad y se dice cuántos caracteres entran, para que el modelo
    reescriba la línea más corta conservando el dato.
    """
    avisos = []
    try:
        lineas = p.lineas_de_voz()
    except Exception:
        return avisos
    for x in lineas:
        if x.ventana <= 0:
            continue
        cps = x.caracteres / x.ventana
        if cps > cps_voz * tolerancia:
            maximo = int(x.ventana * cps_voz)
            avisos.append(f"{x.id}: {x.caracteres} caracteres en {x.ventana:.1f} s = {cps:.1f} cps; "
                          f"con esta voz ({cps_voz:.1f} cps medidos) entran como mucho {maximo} "
                          f"caracteres. Reescribí la línea más corta conservando el dato, "
                          f"o dale más segundos al plano si el tramo lo permite.")
    return avisos


def _validar(d: dict, cps_voz: float | None = None) -> tuple[list[str], str | None]:
    """(avisos del validador, error fatal si el JSON ni siquiera carga)."""
    try:
        p = Proyecto.desde_dict(d)
    except (ProyectoInvalido, KeyError, TypeError, ValueError) as e:
        return [], f"{type(e).__name__}: {e}"
    try:
        avisos = p.validar()
    except Exception as e:  # una estructura rara no tiene que tirar todo
        return [f"no se pudo validar: {e}"], None
    if cps_voz:
        avisos += densidad_contra_voz(p, cps_voz)
    return avisos, None


def _forzar_grilla(d: dict) -> None:
    """Lo que no se negocia se corrige acá, sin gastar otra llamada: todos los
    planos generan 5,17 s y ningún corte pasa de 4,8."""
    for p in d.get("planos", []):
        if p.get("clip_de") or p.get("sigue_de"):
            continue
        p["segundos"] = round(grilla.MINIMO, 2)
        if p.get("corta") and float(p["corta"]) > 4.8:
            p["corta"] = 4.8
        if p.get("usa"):
            a, b = float(p["usa"][0]), float(p["usa"][1])
            if b - a > 4.8:
                p["usa"] = [a, round(a + 4.8, 2)]


def traducir(guion: str, *, formato: str, estructura: str, estilo_imagen: str,
             estilo_video: str = "", cierre_video: str = "", medio: str = "",
             voz: str | None = "kate", titulo: str = "", negativos: bool = True,
             notas: str = "", reintentos: int = 2, log=print) -> dict:
    """Guion → proyecto validado. Devuelve {"proyecto", "avisos", "intentos", "instruccion"}."""
    if not guion or len(guion.strip()) < 40:
        raise ErrorGuionista("el guion está vacío o es demasiado corto")
    ins = instruccion(guion, formato=formato, estructura=estructura, estilo_imagen=estilo_imagen,
                      estilo_video=estilo_video, cierre_video=cierre_video, medio=medio, voz=voz,
                      titulo=titulo, negativos=negativos, notas=notas)
    mensajes = [{"role": "system", "content": "Sos el director técnico de un pipeline de video con IA. "
                                              "Respondés sólo con JSON válido."},
                {"role": "user", "content": ins}]
    d, avisos, fatal = {}, [], None
    for intento in range(1, reintentos + 2):
        log(f"  · llamada {intento} a OpenAI ({MODELO})…")
        crudo = _llamar(mensajes)
        d = _json(crudo)
        d["formato"] = formato
        d["estructura"] = estructura
        if titulo:
            d["titulo"] = titulo
        d["estilo_imagen"] = estilo_imagen
        if estilo_video:
            d["estilo_video"] = estilo_video
        if cierre_video:
            d["cierre_video"] = cierre_video
        if medio:
            d["medio"] = medio
        if voz and voz in VOCES:
            d.setdefault("voces", {})["narrador"] = VOCES[voz]["id"]
        if not negativos:
            d["negativos"] = False
        _forzar_grilla(d)
        avisos, fatal = _validar(d, VOCES[voz]["cps"] if voz and voz in VOCES else None)
        log(f"    {'ERROR ' + fatal if fatal else str(len(avisos)) + ' aviso(s)'}")
        if not fatal and not avisos:
            break
        if intento > reintentos:
            break
        problema = fatal or "\n".join(f"- {a}" for a in avisos)
        mensajes.append({"role": "assistant", "content": json.dumps(d, ensure_ascii=False)})
        mensajes.append({"role": "user", "content":
                         "El validador devolvió esto. Corregí SÓLO lo necesario y devolvé el JSON "
                         "completo otra vez:\n" + problema})
    if fatal:
        raise ErrorGuionista("el proyecto no carga: " + fatal)
    return {"proyecto": d, "avisos": avisos, "intentos": intento, "instruccion": ins}
