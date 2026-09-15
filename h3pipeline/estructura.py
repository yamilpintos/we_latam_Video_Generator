"""La estructura por tramos: la entrada que dice qué tiene que pasar en cada
segundo del video ANTES de escribir un solo plano.

Es la fuente de información para el paso siguiente, que es dibujar los
primeros fotogramas. Un tramo dice "de 0 a 3 s hace falta un evento llamativo
visible ya en el primer fotograma"; el que escribe los planos (una persona o
un LLM) lee el brief, propone los planos, y el módulo verifica que cada tramo
quedó cubierto y que ningún corte se pasó de largo.

Las estructuras viven en JSON (`estructuras/short.json`, `estructuras/largo.json`)
y se cargan por nombre, por ruta o como dict ya armado. Los tramos se declaran
en segundos (`desde`/`hasta`) o como fracción de la duración objetivo
(`desde_pct`/`hasta_pct`), y se pueden mezclar.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from . import grilla

CARPETA = Path(__file__).resolve().parent / "estructuras"
NOMBRES_TAMANO = ("PGE", "PG", "PA", "PM", "PP", "PD")


class EstructuraInvalida(ValueError):
    pass


@dataclass
class Tramo:
    id: str
    nombre: str
    desde: float
    hasta: float
    objetivo: str = ""
    exige: list[str] = field(default_factory=list)
    corte_min: float | None = None
    corte_max: float | None = None
    tamanos: list[str] = field(default_factory=list)
    prompt_frame: str = ""       # en inglés: se inyecta en el prompt del fotograma
    audio: str = ""
    planos_min: int = 1
    # El "triple refuerzo": el mensaje del tramo entra por lo visual, lo
    # auditivo y el TEXTO EN PANTALLA a la vez. Ojo: el texto va como overlay en
    # post, nunca pedido al generador — los modelos de imagen y video destrozan
    # el texto, y en un gancho eso es fatal.
    texto_pantalla: str = ""
    # Este tramo tiene que romper el patrón: cambio de ritmo, plano, luz o
    # sonido. Sin interrupciones periódicas el cerebro predice y deja de mirar.
    interrupcion: bool = False

    @property
    def duracion(self) -> float:
        return self.hasta - self.desde

    def contiene(self, t: float) -> bool:
        return self.desde <= t < self.hasta

    def corte_tipico(self) -> float:
        if self.corte_min is not None and self.corte_max is not None:
            return (self.corte_min + self.corte_max) / 2
        if self.corte_max is not None:
            return self.corte_max * 0.8
        if self.corte_min is not None:
            return self.corte_min * 1.3
        return 6.0


@dataclass
class Estructura:
    nombre: str
    formato: str                      # "short" | "largo"
    duracion_objetivo: float
    tramos: list[Tramo]
    tolerancia: float = 3.0
    notas: list[str] = field(default_factory=list)
    # Dónde entra esta duración y qué retención hay que sacarle. Los umbrales
    # son de las fuentes de 2026: en Shorts de menos de 30 s el empuje a más
    # audiencia arranca cerca del 65 % de retención; entre 30 y 60 s, del 50 %.
    plataformas: list[str] = field(default_factory=list)
    retencion_objetivo: float = 0.0
    # Cada cuántos segundos, como máximo, tiene que haber una interrupción de
    # patrón. 0 = no se exige.
    interrupcion_cada: float = 0.0

    # ------------------------------------------------------------ carga
    @classmethod
    def cargar(cls, que) -> "Estructura":
        """Por nombre ("short", "largo"), por ruta a un JSON, o como dict."""
        if isinstance(que, Estructura):
            return que
        if isinstance(que, dict):
            return cls.desde_dict(que)
        p = Path(que)
        if not p.suffix:
            p = CARPETA / f"{que}.json"
        if not p.is_file():
            raise EstructuraInvalida(
                f"no existe la estructura {que!r}; hay: {', '.join(disponibles())}")
        return cls.desde_dict(json.loads(p.read_text(encoding="utf-8")))

    @classmethod
    def desde_dict(cls, d: dict) -> "Estructura":
        dur = float(d["duracion_objetivo"])
        tramos: list[Tramo] = []
        for t in d["tramos"]:
            desde = t.get("desde")
            hasta = t.get("hasta")
            if desde is None and "desde_pct" in t:
                desde = round(dur * float(t["desde_pct"]), 2)
            if hasta is None and "hasta_pct" in t:
                hasta = round(dur * float(t["hasta_pct"]), 2)
            if desde is None:
                desde = tramos[-1].hasta if tramos else 0.0
            if hasta is None:
                hasta = dur
            tramos.append(Tramo(
                id=t["id"], nombre=t.get("nombre", t["id"]),
                desde=float(desde), hasta=float(hasta),
                objetivo=t.get("objetivo", ""), exige=list(t.get("exige", [])),
                corte_min=t.get("corte_min"), corte_max=t.get("corte_max"),
                tamanos=list(t.get("tamanos", [])),
                prompt_frame=t.get("prompt_frame", ""), audio=t.get("audio", ""),
                planos_min=int(t.get("planos_min", 1)),
                texto_pantalla=t.get("texto_pantalla", ""),
                interrupcion=bool(t.get("interrupcion", False))))
        e = cls(nombre=d["nombre"], formato=d.get("formato", "short"),
                duracion_objetivo=dur, tramos=tramos,
                tolerancia=float(d.get("tolerancia", 3.0)),
                notas=list(d.get("notas", [])),
                plataformas=list(d.get("plataformas", [])),
                retencion_objetivo=float(d.get("retencion_objetivo", 0.0)),
                interrupcion_cada=float(d.get("interrupcion_cada", 0.0)))
        e._verificar()
        return e

    def _verificar(self) -> None:
        if not self.tramos:
            raise EstructuraInvalida("una estructura necesita al menos un tramo")
        for a, b in zip(self.tramos, self.tramos[1:]):
            if b.desde < a.hasta - 1e-6:
                raise EstructuraInvalida(f"los tramos {a.id} y {b.id} se solapan")
        ids = [t.id for t in self.tramos]
        if len(ids) != len(set(ids)):
            raise EstructuraInvalida("hay tramos con el mismo id")

    def con_duracion(self, segundos: float) -> "Estructura":
        """La misma estructura estirada a otra duración. Los tramos declarados
        en fracción se reescalan; los absolutos se mantienen."""
        d = self.a_dict()
        for t, orig in zip(d["tramos"], self.tramos):
            t["desde_pct"] = orig.desde / self.duracion_objetivo
            t["hasta_pct"] = orig.hasta / self.duracion_objetivo
            t.pop("desde", None)
            t.pop("hasta", None)
        d["duracion_objetivo"] = segundos
        return Estructura.desde_dict(d)

    def a_dict(self) -> dict:
        return {"nombre": self.nombre, "formato": self.formato,
                "duracion_objetivo": self.duracion_objetivo,
                "tolerancia": self.tolerancia, "notas": self.notas,
                "plataformas": self.plataformas,
                "retencion_objetivo": self.retencion_objetivo,
                "interrupcion_cada": self.interrupcion_cada,
                "tramos": [dict(t.__dict__) for t in self.tramos]}

    def guardar(self, ruta) -> Path:
        ruta = Path(ruta)
        ruta.write_text(json.dumps(self.a_dict(), ensure_ascii=False, indent=2),
                        encoding="utf-8")
        return ruta

    # ------------------------------------------------------------ consulta
    def tramo(self, id_: str) -> Tramo:
        for t in self.tramos:
            if t.id == id_:
                return t
        raise KeyError(id_)

    def tramo_en(self, t: float) -> Tramo | None:
        for tr in self.tramos:
            if tr.contiene(t):
                return tr
        if self.tramos and abs(t - self.tramos[-1].hasta) < 1e-6:
            return self.tramos[-1]
        return None

    # ------------------------------------------------------------ planos
    @staticmethod
    def corte(p: dict) -> float:
        """Cuánto dura el plano EN LA LÍNEA DE TIEMPO: el tramo `usa` si lo hay,
        si no el plano entero."""
        if p.get("usa"):
            return float(p["usa"][1]) - float(p["usa"][0])
        return float(p["segundos"])

    def linea_de_tiempo(self, planos: list[dict]) -> list[tuple[float, float]]:
        out, t = [], 0.0
        for p in planos:
            d = self.corte(p)
            out.append((round(t, 3), round(t + d, 3)))
            t += d
        return out

    def asignar(self, planos: list[dict]) -> None:
        """Escribe `tramo` en cada plano según dónde arranca en la línea de
        tiempo. Un plano declarado con `tramo` a mano se respeta."""
        for p, (ini, _fin) in zip(planos, self.linea_de_tiempo(planos)):
            if not p.get("tramo"):
                tr = self.tramo_en(ini)
                p["tramo"] = tr.id if tr else None

    def validar(self, planos: list[dict]) -> list[str]:
        """Avisos, no errores: la estructura es una guía y el director decide.
        Pero todo lo que se aparta queda escrito."""
        avisos: list[str] = []
        if not planos:
            return ["no hay planos"]
        self.asignar(planos)
        lt = self.linea_de_tiempo(planos)
        total = lt[-1][1]
        if abs(total - self.duracion_objetivo) > self.tolerancia:
            avisos.append(f"dura {total:.1f} s y la estructura pide "
                          f"{self.duracion_objetivo:.0f} ± {self.tolerancia:.0f}")
        por_tramo: dict[str, list[dict]] = {t.id: [] for t in self.tramos}
        for p, (ini, _fin) in zip(planos, lt):
            tr = self.tramo_en(ini)
            if tr is None:
                avisos.append(f"{p['id']} arranca en {ini:.1f} s, fuera de todo tramo")
                continue
            por_tramo[tr.id].append(p)
            c = self.corte(p)
            if tr.corte_max is not None and c > tr.corte_max + 0.05:
                avisos.append(f"{p['id']} ({tr.id}) corta a {c:.1f} s; el tramo "
                              f"pide como mucho {tr.corte_max:.1f}")
            if tr.corte_min is not None and c < tr.corte_min - 0.05:
                avisos.append(f"{p['id']} ({tr.id}) corta a {c:.1f} s; el tramo "
                              f"pide al menos {tr.corte_min:.1f}")
            if tr.tamanos and p.get("tipo") in NOMBRES_TAMANO and p["tipo"] not in tr.tamanos:
                avisos.append(f"{p['id']} es {p['tipo']} y el tramo {tr.id} sugiere "
                              f"{'/'.join(tr.tamanos)}")
        for tr in self.tramos:
            n = len(por_tramo[tr.id])
            if n < tr.planos_min:
                avisos.append(f"el tramo {tr.id} ({self._seg(tr.desde)}-"
                              f"{self._seg(tr.hasta)} s) tiene "
                              f"{n} plano(s) y pide al menos {tr.planos_min}")
            # El triple refuerzo: donde el tramo pide texto en pantalla, algún
            # plano tiene que traerlo. Va como overlay en post, nunca generado.
            if tr.texto_pantalla and por_tramo[tr.id] \
                    and not any(p.get("texto") for p in por_tramo[tr.id]):
                avisos.append(f"el tramo {tr.id} pide texto en pantalla y ningún plano lo "
                              f"trae: agregá `texto` al plano ({tr.texto_pantalla})")

        avisos += self._interrupciones(planos, lt)
        return avisos

    def _interrupciones(self, planos: list[dict], lt) -> list[str]:
        """Huecos sin interrupción de patrón.

        Un cambio de ritmo, plano, tono o formato cada pocos segundos evita que
        el cerebro «ahorre energía» e ignore lo predecible.

        **Un corte no cuenta.** En un short todo son cortes cada 3-6 s, así que
        si contaran la regla no diría nada. Lo que cuenta es un cambio de
        *régimen*: entra una luz de otro color, aparece o desaparece un sonido,
        cambia la velocidad del montaje, se rompe la expectativa. Por eso lo
        marca el tramo (`interrupcion`) o el plano que lo hace a propósito.
        """
        if not self.interrupcion_cada:
            return []
        marcas = [0.0]
        for p, (ini, _fin) in zip(planos, lt):
            tr = self.tramo_en(ini)
            if p.get("interrupcion") or (tr and tr.interrupcion):
                marcas.append(ini)
        marcas.append(lt[-1][1])
        avisos = []
        for a, b in zip(marcas, marcas[1:]):
            if b - a > self.interrupcion_cada + 0.05:
                avisos.append(f"{b - a:.0f} s sin interrupción de patrón, entre {a:.0f} y "
                              f"{b:.0f} s (el máximo es {self.interrupcion_cada:.0f}): "
                              f"meté un cambio de ritmo, luz o sonido ahí")
        return avisos

    # ------------------------------------------------------------ brief
    def esqueleto(self) -> list[dict]:
        """Una propuesta de huecos por tramo, para arrancar a escribir: cuántos
        planos, cuánto corta cada uno y cuánto habría que generar. En el short
        el corte no puede bajar del mínimo de H3, así que se genera de más."""
        out = []
        for tr in self.tramos:
            n = max(tr.planos_min, int(round(tr.duracion / tr.corte_tipico())) or 1)
            corte_real = tr.duracion / n
            if self.formato == "short":
                genera = grilla.encajar(max(grilla.MINIMO, corte_real + 0.5))[1]
            else:
                genera = grilla.encajar(corte_real)[1]
            out.append({"tramo": tr.id, "planos": n,
                        "corte_sugerido": round(corte_real, 1),
                        "genera_sugerido": round(genera, 2),
                        "tamanos": tr.tamanos})
        return out

    @staticmethod
    def _seg(x: float) -> str:
        """Sin decimales cuando es redondo: 5.5 no puede mostrarse como 6, que es
        otro tramo."""
        return f"{x:.0f}" if abs(x - round(x)) < 0.05 else f"{x:.1f}"

    def brief(self, planos: list[dict] | None = None, titulo: str | None = None) -> str:
        """El documento que se le da a quien escribe los planos y dibuja los
        fotogramas. Sin planos, lista los huecos; con planos, muestra cómo
        quedó cubierto cada tramo y los avisos."""
        L = [f"# {titulo or self.nombre} — estructura por tramos", "",
             f"Formato **{self.formato}** · duración objetivo "
             f"**{self.duracion_objetivo:.0f} s** (± {self.tolerancia:.0f}) · "
             f"{len(self.tramos)} tramos", ""]
        meta = []
        if self.plataformas:
            meta.append("Plataformas: " + ", ".join(self.plataformas))
        if self.retencion_objetivo:
            meta.append(f"**Retención objetivo: {self.retencion_objetivo * 100:.0f} %** — "
                        f"por debajo de eso la plataforma no lo empuja a más audiencia")
        if self.interrupcion_cada:
            meta.append(f"Interrupción de patrón cada **{self.interrupcion_cada:.0f} s** "
                        f"como máximo")
        if meta:
            L += [" · ".join(meta), ""]
        if self.notas:
            L += [f"> {n}" for n in self.notas] + [""]
        lt: dict[str, tuple[float, float]] = {}
        if planos:
            self.asignar(planos)
            lt = dict(zip((p["id"] for p in planos), self.linea_de_tiempo(planos)))
        esq = {e["tramo"]: e for e in self.esqueleto()}
        for tr in self.tramos:
            L.append(f"## {tr.id} · {tr.nombre} · {self._seg(tr.desde)}–"
                     f"{self._seg(tr.hasta)} s")
            L.append("")
            if tr.objetivo:
                L += [tr.objetivo, ""]
            if tr.exige:
                L.append("Exige:")
                L += [f"- {x}" for x in tr.exige]
                L.append("")
            detalle = []
            if tr.corte_min is not None or tr.corte_max is not None:
                a = f"{tr.corte_min:.1f}" if tr.corte_min is not None else "…"
                b = f"{tr.corte_max:.1f}" if tr.corte_max is not None else "…"
                detalle.append(f"corte {a}–{b} s")
            if tr.tamanos:
                detalle.append("tamaños " + "/".join(tr.tamanos))
            if tr.interrupcion:
                detalle.append("**rompe el patrón**")
            if tr.audio:
                detalle.append("audio: " + tr.audio)
            if detalle:
                L += ["_" + " · ".join(detalle) + "_", ""]
            if tr.texto_pantalla:
                L += [f"**Texto en pantalla** (overlay en post, NUNCA pedido al generador): "
                      f"{tr.texto_pantalla}", ""]
            if tr.prompt_frame:
                L += [f"Para el fotograma (se inyecta en el prompt): `{tr.prompt_frame}`", ""]
            if planos:
                mios = [p for p in planos if p.get("tramo") == tr.id]
                if not mios:
                    L.append("**Sin planos.**")
                else:
                    L.append("| plano | en línea | corta | tipo | función |")
                    L.append("|---|---|---|---|---|")
                    for p in mios:
                        a, b = lt[p["id"]]
                        L.append(f"| {p['id']} | {a:.1f}–{b:.1f} | {self.corte(p):.1f} s | "
                                 f"{p.get('tipo', '')} | {p.get('funcion', '')} |")
            else:
                e = esq[tr.id]
                L.append(f"Huecos sugeridos: **{e['planos']} plano(s)** de "
                         f"~{e['corte_sugerido']} s en línea, generando "
                         f"~{e['genera_sugerido']} s cada uno.")
            L.append("")
        if planos:
            av = self.validar(planos)
            L += ["## Verificación", ""]
            L += [f"- ⚠ {a}" for a in av] if av else \
                 ["- Sin avisos: cada tramo tiene su plano y ningún corte se pasa."]
            L.append("")
        return "\n".join(L)


def disponibles() -> list[str]:
    return sorted(x.stem for x in CARPETA.glob("*.json"))
