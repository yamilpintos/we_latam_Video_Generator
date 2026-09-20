"""El proyecto: una definición declarativa que produce el storyboard y los planos.

Un proyecto es un JSON (o un dict) con el estilo, el reparto, las locaciones y
la lista de planos que escribió el director. De ahí salen las dos únicas cosas
que consume el resto del pipeline:

    storyboard.json   un asset por plano → los primeros fotogramas (nano banana)
    planos.json       un plano por entrada → lo que genera H3 dentro de Vast

El orden importa y es el que ahorra plata: el storyboard se revisa entero
ANTES de prender la GPU. Un encuadre mal salido se ve en un PNG que costó 22
segundos, no después de siete minutos de generación con la máquina cobrando.

La estructura por tramos (`estructura.py`) entra acá como *entrada de
dirección*: dice qué tiene que pasar en cada segundo, y `brief()` lo devuelve
escrito para que el director —o un LLM— escriba los planos contra eso. Después
`validar()` chequea que cada tramo quedó cubierto.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from . import grilla, prompts, voz as vozmod
from .estructura import Estructura

# Resolución nativa de H3: lado corto 768, ~1 MP. Apaisado para el largo,
# vertical para el short. Es la misma cantidad de píxeles, así que el tiempo
# por plano no cambia entre formatos.
RESOLUCION = {"largo": (1344, 768), "short": (768, 1344)}
ASPECTO = {"largo": "16:9", "short": "9:16"}


class ProyectoInvalido(ValueError):
    """La definición no cierra. El mensaje dice qué plano y qué campo."""


@dataclass
class Personaje:
    """Un personaje del reparto.

    `descripcion` se inyecta en TODOS los prompts donde aparece, aunque ya esté
    en el dibujo: la hoja de modelo sostiene la cara, el texto sostiene la ropa.
    Sin eso la faja cambia de largo y los parches se mudan entre plano y plano.
    """
    id: str
    hoja: str            # id del asset madre (hoja de modelo con las cuatro vistas)
    descripcion: str


@dataclass
class Locacion:
    id: str
    imagen: str          # id del asset madre (plano general SIN gente)
    descripcion: str = ""


@dataclass
class Voz:
    """Una línea de voz en off. No la genera H3: va de ElevenLabs, encima.

    `t` es el segundo en la línea de tiempo montada. Si se declara `plano`, se
    recalcula solo contra la línea de tiempo real cuando cambia el montaje.
    """
    texto: str
    t: float | None = None
    plano: str | None = None
    offset: float = 0.4


@dataclass
class Proyecto:
    titulo: str
    formato: str                                  # "short" | "largo"
    planos: list[dict]
    slug: str = ""
    estructura: object = None                     # nombre, ruta, dict o Estructura
    duracion_objetivo: float | None = None
    estilo_imagen: str = ""                       # prompt de estilo del fotograma
    estilo_video: str = ""                        # cabecera del prompt de video (short)
    cierre_video: str = ""                        # coda del prompt de video (short)
    medio: str = "2D animated film"               # cómo se describe el medio (largo)
    sujeto: str = ""                              # short: el sujeto constante
    solo_sonidos: str = ""                        # short: qué se oye si no hay voz
    refs_estilo: list[str] = field(default_factory=list)
    personajes: dict[str, Personaje] = field(default_factory=dict)
    locaciones: dict[str, Locacion] = field(default_factory=dict)
    madre: list[dict] = field(default_factory=list)   # assets madre (hojas, locaciones)
    voz: list[Voz] = field(default_factory=list)
    voces: dict[str, str] = field(default_factory=dict)   # personaje → voice_id de ElevenLabs
    resolucion: tuple[int, int] | None = None
    # False = sin los bloques negativos fijos del prompt de video (no inventes,
    # humo, idioma): en escenas quietas y sin gente inducen lo que prohíben.
    negativos: bool = True
    # Idioma de lo que se habla dentro del clip: "es" (default) o "en". Ver
    # prompts.IDIOMAS.
    idioma: str = "es"
    raiz: Path = Path(".")

    # ------------------------------------------------------------- carga
    @classmethod
    def cargar(cls, ruta) -> "Proyecto":
        ruta = Path(ruta)
        d = json.loads(ruta.read_text(encoding="utf-8"))
        p = cls.desde_dict(d)
        p.raiz = ruta.parent
        return p

    @classmethod
    def desde_dict(cls, d: dict) -> "Proyecto":
        formato = d.get("formato", "short")
        if formato not in RESOLUCION:
            raise ProyectoInvalido(f"formato {formato!r}: tiene que ser 'short' o 'largo'")
        pers = {k: Personaje(id=k, hoja=v.get("hoja", f"m_{k}"),
                             descripcion=v["descripcion"])
                for k, v in (d.get("personajes") or {}).items()}
        locs = {k: Locacion(id=k, imagen=v.get("imagen", f"l_{k}"),
                            descripcion=v.get("descripcion", ""))
                for k, v in (d.get("locaciones") or {}).items()}
        voz = [Voz(**v) if isinstance(v, dict) else Voz(texto=v) for v in (d.get("voz") or [])]
        res = d.get("resolucion")
        p = cls(
            titulo=d["titulo"], formato=formato, planos=[dict(x) for x in d["planos"]],
            slug=d.get("slug") or _slug(d["titulo"]),
            estructura=d.get("estructura", formato),
            duracion_objetivo=d.get("duracion_objetivo"),
            estilo_imagen=d.get("estilo_imagen", ""), estilo_video=d.get("estilo_video", ""),
            cierre_video=d.get("cierre_video", ""), medio=d.get("medio", "2D animated film"),
            sujeto=d.get("sujeto", ""), solo_sonidos=d.get("solo_sonidos", ""),
            refs_estilo=list(d.get("refs_estilo") or []),
            personajes=pers, locaciones=locs, madre=list(d.get("madre") or []), voz=voz,
            voces=dict(d.get("voces") or {}),
            resolucion=tuple(res) if res else None,
            negativos=bool(d.get("negativos", True)),
            idioma=d.get("idioma", "es"))
        p._verificar()
        return p

    def _verificar(self) -> None:
        vistos = set()
        for i, p in enumerate(self.planos, 1):
            # `ve` describe el dibujo del primer fotograma, así que un plano
            # encadenado no lo necesita: su primer fotograma es el último del
            # clip anterior. `mueve` sí es obligatorio siempre.
            campos = ("mueve",) if p.get("sigue_de") else ("ve", "mueve")
            for campo in campos:
                if not p.get(campo):
                    raise ProyectoInvalido(
                        f"plano {p.get('id') or i}: falta '{campo}' "
                        f"({'qué se ve, quieto' if campo == 've' else 'qué se mueve'})")
            pid = p.get("id")
            if pid and pid in vistos:
                raise ProyectoInvalido(f"el id de plano {pid} está repetido")
            vistos.add(pid)
            for nom in p.get("personajes") or []:
                if nom not in self.personajes:
                    raise ProyectoInvalido(f"plano {pid or i}: no existe el personaje {nom!r}")
            loc = p.get("loc")
            if loc and loc not in self.locaciones:
                raise ProyectoInvalido(f"plano {pid or i}: no existe la locación {loc!r}")
            tam = p.get("tipo", "PM" if self.formato == "largo" else "SHORT")
            if self.formato == "largo" and tam not in prompts.TAMANIO:
                raise ProyectoInvalido(
                    f"plano {pid or i}: tipo {tam!r}; hay {', '.join(prompts.TAMANIO)}")

    # -------------------------------------------------------- derivados
    @property
    def aspecto(self) -> str:
        return ASPECTO[self.formato]

    @property
    def wh(self) -> tuple[int, int]:
        return tuple(self.resolucion or RESOLUCION[self.formato])

    def estructura_resuelta(self) -> Estructura:
        e = Estructura.cargar(self.estructura or self.formato)
        if self.duracion_objetivo and abs(e.duracion_objetivo - self.duracion_objetivo) > 0.01:
            e = e.con_duracion(self.duracion_objetivo)
        return e

    def prefijo(self) -> str:
        return "S" if self.formato == "short" else "P"

    # ---------------------------------------------------------- armado
    def _refs_de(self, p: dict) -> list[str]:
        """Locación primero, después los personajes sin repetir. El orden es el
        que nombran <Picture 1>, <Picture 2>… en el prompt."""
        if p.get("refs") is not None:
            return list(p["refs"])
        out: list[str] = []
        if p.get("loc") and p["loc"] in self.locaciones:
            out.append(self.locaciones[p["loc"]].imagen)
        for nom in p.get("personajes") or []:
            hoja = self.personajes[nom].hoja
            if hoja not in out:
                out.append(hoja)
        return out

    def _descripciones(self, p: dict) -> list[str]:
        return [self.personajes[n].descripcion for n in (p.get("personajes") or [])]

    def _duraciones(self, p: dict) -> tuple[int, float, list[float] | None]:
        """(length, segundos_generados, usa).

        En el short el corte manda: el director dice cuánto tiene que durar EN
        LA LÍNEA (`corta`) y el módulo genera de más, porque H3 no baja de
        5,17 s. En el largo el plano se usa entero.
        """
        if self.formato == "short":
            if p.get("usa"):
                ini, fin = float(p["usa"][0]), float(p["usa"][1])
            else:
                corta = float(p.get("corta") or p.get("segundos") or 4.0)
                ini, fin = 0.0, corta
            pedido = p.get("segundos")
            if pedido:
                length, real = grilla.encajar(float(pedido))
            else:
                # Colchón de 0,5 s: el final de un clip de H3 suele derivar, así
                # que conviene tener de dónde recortar y no usar el último cuadro.
                length, real = grilla.encajar(max(grilla.MINIMO, (fin - ini) + 0.5))
            if fin > real:
                fin = round(real, 3)
            return length, real, [round(ini, 2), round(fin, 2)]
        length, real = grilla.encajar(float(p.get("segundos") or p.get("corta") or 8.0))
        return length, real, None

    def construir(self) -> tuple[dict, dict]:
        """Devuelve (storyboard, planos) listos para escribir a disco.

        Va en dos pasadas y no en una porque el tramo de cada plano depende de
        dónde cae en la línea de tiempo, y el tramo **entra en el prompt del
        fotograma**: es lo que hace que "los primeros 3 segundos necesitan un
        evento llamativo" llegue hasta el dibujo en vez de quedarse en un
        documento que nadie relee.
        """
        est = self.estructura_resuelta()
        pref = self.prefijo()

        # Pasada 1: duraciones y línea de tiempo, que es lo que fija los tramos.
        base = []
        for i, p in enumerate(self.planos, 1):
            length, seg, usa = self._duraciones(p)
            base.append({"id": p.get("id") or f"{pref}{i:02d}", "length": length,
                         "segundos": round(seg, 3), "usa": usa, "tramo": p.get("tramo")})
        est.asignar(base)
        lt = est.linea_de_tiempo(base)

        # Pasada 2: los prompts, ya sabiendo en qué tramo cae cada plano.
        sb_assets, planos = [], []
        for p, b, (t_ini, t_fin) in zip(self.planos, base, lt):
            pid, length, seg, usa, tramo = (b["id"], b["length"], b["segundos"],
                                            b["usa"], b["tramo"])
            refs = self._refs_de(p)
            tam = p.get("tipo", "SHORT" if self.formato == "short" else "PM")
            # Lo que el tramo le pide a ESTE fotograma. El plano puede pisarlo
            # con su propia `intencion` si el director quiere otra cosa.
            intencion = p.get("intencion") or (
                est.tramo(tramo).prompt_frame if tramo else "")

            # Un plano encadenado arranca del ÚLTIMO FOTOGRAMA del anterior, no
            # de un dibujo: no necesita entrada en el storyboard y su prompt de
            # video lleva el bloque de continuidad cinética.
            sigue = p.get("sigue_de")

            if self.formato == "short":
                sb_prompt = prompts.storyboard_short(
                    self.estilo_imagen, p["ve"], p.get("sujeto", self.sujeto),
                    intencion, self.aspecto)
                vid_prompt = prompts.video_short(
                    p.get("cabecera") or self.estilo_video, p["mueve"], p.get("audio", ""),
                    p.get("dialogo"), p.get("cierre") or self.cierre_video,
                    p.get("solo_sonidos", self.solo_sonidos), self.idioma)
            else:
                sb_prompt = prompts.storyboard_largo(
                    self.estilo_imagen, tam, len(refs), self._descripciones(p),
                    p["ve"], self.aspecto, intencion)
                vid_prompt = prompts.video_largo(
                    tam, self._descripciones(p), p["mueve"], p.get("audio", ""),
                    p.get("dialogo"), p.get("medio", self.medio), self.negativos,
                    self.idioma)

            # Prompt ya escrito en el formato oficial de MiniMax (guías de
            # models/MiniMax-H3/docs): va TAL CUAL, sin los bloques del módulo.
            # Los armadores de arriba son el formato viejo (texto libre), que el
            # README oficial no recomienda; se conservan para los videos previos.
            if p.get("prompt_h3"):
                vid_prompt = p["prompt_h3"]

            reusa = p.get("clip_de")
            # `dibujo`: usa el primer fotograma de OTRO plano ya dibujado (la
            # muestra prueba varias configuraciones sobre el mismo dibujo).
            dibujo = p.get("dibujo")
            if sigue:
                # Sin dibujo propio: el primer fotograma sale del clip anterior.
                vid_prompt = prompts.CONTINUIDAD + "\n" + vid_prompt
            elif reusa or dibujo:
                pass  # clip de otro plano, o dibujo de otro plano: no se dibuja nada
            else:
                sb_assets.append({
                    "id": f"sb_{pid}",
                    "aspecto": self.aspecto,
                    "refs": [r if "/" in r else f"assets/{r}.png" for r in refs],
                    "prompt": sb_prompt,
                })
            plano = {
                "id": pid,
                "escena": p.get("escena", self.slug.upper()),
                "tramo": tramo,
                "tipo": tam,
                "loc": p.get("loc"),
                "personajes": list(p.get("personajes") or []),
                "length": length,
                "segundos": round(seg, 3),
                "funcion": p.get("funcion", ""),
                "first_frame": (None if (sigue or reusa)
                                else f"assets/{dibujo}" if dibujo else f"assets/sb_{pid}.png"),
                "clip_de": reusa,
                "sigue_de": sigue,
                "prompt": vid_prompt,
                "dialogo": p.get("dialogo"),
            }
            # El texto en pantalla y la marca de interrupción viajan hasta el
            # plano construido: son lo que valida la ley de retención, y el
            # texto además es una instrucción de post que hay que entregar.
            if p.get("texto"):
                plano["texto"] = p["texto"]
            if p.get("interrupcion"):
                plano["interrupcion"] = True
            # Semilla a mano: para rehacer un plano que salió mal sin repetir
            # exactamente el mismo resultado (el runner usa 1000+índice si falta).
            if p.get("seed") is not None:
                plano["seed"] = int(p["seed"])
            if p.get("ventana_dialogo"):
                plano["ventana_dialogo"] = float(p["ventana_dialogo"])
            if p.get("voz_de"):
                plano["voz_de"] = p["voz_de"]
            # Lo que el runner necesita para Ref2VA y para variar la calidad por
            # plano (la muestra compara configuraciones en la misma corrida).
            #   modo        "fl2va" (default) o "ref2va"
            #   refs_extra  imágenes de referencia después del primer fotograma
            #               (<Picture 2>, <Picture 3>…), nombres dentro de assets/
            #   voz_ref     WAV de 32 kHz estéreo con el timbre (<Audio 1>)
            #   guia0       ancla además el primer fotograma con MiniMaxH3AddGuide
            #   pasos, turbo, shift_video, shift_audio, scheduler: pisan los globales
            for campo in ("modo", "refs_extra", "voz_ref", "guia0", "pasos", "turbo",
                          "shift_video", "shift_audio", "scheduler", "ref_image_size"):
                if p.get(campo) is not None:
                    plano[campo] = p[campo]
            if usa is not None:
                plano["usa"] = usa
            plano["en_linea_de_tiempo"] = [round(t_ini, 2), round(t_fin, 2)]
            planos.append(plano)

        w, h = self.wh
        storyboard = {
            "_comentario": ("Un dibujo por plano: es el primer fotograma que recibe H3. "
                            "Se revisa y se rehace lo que no cierra ANTES de gastar un "
                            "minuto de GPU."),
            "titulo": self.titulo, "aspecto": self.aspecto,
            "refs": list(self.refs_estilo), "assets": sb_assets,
        }
        doc_planos = {
            "_comentario": ("Planos independientes: ninguno depende de otro, así que todos "
                            "paralelizan y cualquiera se rehace solo. Se montan con cortes."
                            + (" Cada plano lleva 'usa' con el tramo que va a la línea: se "
                               "genera de más porque H3 no baja de 5,17 s."
                               if self.formato == "short" else "")),
            "titulo": self.titulo, "slug": self.slug, "formato": self.formato,
            "fps": grilla.FPS, "ancho": w, "alto": h,
            "estructura": self.estructura_resuelta().nombre,
            "planos": planos,
        }
        return storyboard, doc_planos

    # ------------------------------------------------------------- voz
    def guion_de_voz(self, planos: list[dict]) -> list[tuple[float, str, str]]:
        """(segundo, plano, texto) con los tiempos contra la línea real."""
        est = self.estructura_resuelta()
        lt = dict(zip((p["id"] for p in planos), est.linea_de_tiempo(planos)))
        out = []
        for v in self.voz:
            if v.plano and v.plano in lt:
                t = lt[v.plano][0] + v.offset
            else:
                t = v.t if v.t is not None else 0.0
            out.append((round(t, 1), v.plano or "", v.texto))
        return sorted(out)

    # ------------------------------------------------------- voz y texto
    def lineas_de_voz(self, planos: list[dict] | None = None) -> list:
        """Cada línea hablada con **la ventana que le toca**, que es lo que
        decide si el texto entra. Son dos casos distintos:

          · el diálogo de un plano (largo) tiene boca en pantalla, así que la
            ventana es el plano menos el aire de entrada y salida, y quedarse
            corto se ve como labios moviéndose sin voz;
          · la voz en off (short) no tiene boca, así que la ventana sólo sirve
            para que una línea no pise la siguiente.

        Con esto, `python -m h3pipeline voz` dice qué reescribir antes de gastar
        un crédito. Ver `voz.py` y VOZ-EMOCION-V3.md.
        """
        planos = planos if planos is not None else self.construir()[1]["planos"]
        est = self.estructura_resuelta()
        lt = dict(zip((p["id"] for p in planos), est.linea_de_tiempo(planos)))
        out = []

        for p in planos:
            if not p.get("dialogo"):
                continue
            a, b = lt[p["id"]]
            # Si el director no declara cuánto se habla, se supone el plano
            # entero menos el aire. Es una cota superior deliberada: avisa de
            # más y nunca de menos, que es lo que conviene antes de generar.
            declarada = p.get("ventana_dialogo")
            ventana = float(declarada) if declarada else max(
                0.1, (b - a) - vozmod.AIRE_ENTRADA - vozmod.AIRE_SALIDA)
            # Quien habla no siempre es quien está en cuadro: una voz por radio,
            # por teléfono o desde fuera de campo la dice otro. `voz_de` lo
            # declara; si no está, se supone el primer personaje del plano.
            quien = p.get("voz_de") or (p.get("personajes") or [""])[0]
            out.append(vozmod.Linea(
                id=p["id"], texto=p["dialogo"], ventana=round(ventana, 2), tipo="boca",
                ventana_estimada=not declarada,
                personaje=quien, voz_id=self.voces.get(quien, ""),
                t=round(a + vozmod.AIRE_ENTRADA, 2), plano=p["id"],
                emocion=p.get("emocion", ""), intensidad=int(p.get("intensidad") or 0),
                variantes=list(p.get("variantes") or [])))

        total = lt[planos[-1]["id"]][1] if planos else 0.0
        offs = self.guion_de_voz(planos)
        for k, (t, pid, texto) in enumerate(offs):
            # La ventana llega hasta donde entra la línea siguiente: es lo único
            # que hay que respetar cuando no hay boca.
            hasta = offs[k + 1][0] if k + 1 < len(offs) else total
            v = next((x for x in self.voz if x.texto == texto), None)
            out.append(vozmod.Linea(
                id=f"VO{k + 1:02d}", texto=texto, ventana=round(max(0.1, hasta - t), 2),
                tipo="off", personaje=getattr(v, "personaje", "") or "narrador",
                voz_id=self.voces.get("narrador", ""), t=t, plano=pid))
        return out

    # -------------------------------------------------------- reportes
    def validar(self, planos: list[dict] | None = None) -> list[str]:
        """Todo lo que se aparta de las reglas, junto. Son avisos: el director
        decide. Pero queda escrito."""
        planos = planos if planos is not None else self.construir()[1]["planos"]
        avisos = list(self.estructura_resuelta().validar(planos))

        # Fuera del rango entrenado de H3 no está roto: está adivinando.
        fuera = [p["id"] for p in planos if not grilla.en_rango(p["length"])]
        if fuera:
            avisos.append(f"fuera del rango entrenado de H3: {' '.join(fuera)}")

        # Cortar entre dos planos del mismo tamaño, en la misma locación y con
        # la misma gente da un brinco, no un corte. Lo chequea la máquina porque
        # leyendo la lista a ojo se pasa.
        #
        # Pide locación declarada a propósito: sin ella no se sabe si dos planos
        # generales seguidos son el mismo encuadre repetido o dos distancias muy
        # distintas del mismo hallazgo, que es lo normal en un short.
        for a, b in zip(planos, planos[1:]):
            # Entre planos encadenados no hay corte —son la misma toma— así que
            # tampoco puede haber salto de eje. Repetir tamaño y reparto ahí es
            # justamente lo que se busca.
            if b.get("sigue_de") == a["id"]:
                continue
            # Dos tomas cortadas del MISMO clip (`clip_de`) son la misma toma
            # de cámara partida, no un salto: la réplica de «danza peligrosa»
            # tiene varias seguidas.
            fuente_a, fuente_b = a.get("clip_de") or a["id"], b.get("clip_de") or b["id"]
            if fuente_a == fuente_b:
                continue
            if (a["loc"] and a["tipo"] == b["tipo"] and a["loc"] == b["loc"]
                    and a["personajes"] == b["personajes"]):
                avisos.append(f"salto de eje: {a['id']} y {b['id']} son los dos {a['tipo']} "
                              f"en {a['loc']} con {a['personajes'] or 'nadie'}")

        # Dos personajes alternando en diez segundos es pedirle demasiado al
        # modelo: una línea, un personaje. El contraplano es otro plano.
        for p in planos:
            # Una toma de 15 s (20/9/2026) trae varios renglones con rótulo en un
            # plano largo: ahí sí hay dos voces y más de 14 palabras a propósito.
            varias = bool(p["dialogo"]) and "\n" in p["dialogo"] and float(p.get("segundos") or 0) >= 10
            if p["dialogo"] and len(p["personajes"]) > 1 and not varias:
                avisos.append(f"{p['id']} tiene diálogo y {len(p['personajes'])} personajes: "
                              f"una sola voz por plano")
            if p["dialogo"] and len(p["dialogo"].split()) > 14 and not varias:
                avisos.append(f"{p['id']}: la línea tiene {len(p['dialogo'].split())} palabras; "
                              f"por encima de ~12 no entra cómoda en el plano")

        # La duración contra las plataformas donde va. Es un aviso y no un
        # error: publicar en una sola plataforma es una decisión válida.
        est = self.estructura_resuelta()
        if est.formato == "short" and planos:
            total = est.linea_de_tiempo(planos)[-1][1]
            fuera = []
            if total > 60.5 and "YouTube Shorts" in est.plataformas:
                fuera.append("YouTube Shorts (el límite es 60 s)")
            if total > 90.5 and "Instagram Reels" in est.plataformas:
                fuera.append("Explorar de Instagram Reels (el límite es 90 s)")
            if fuera:
                avisos.append(f"dura {total:.0f} s: queda fuera de " + " y de ".join(fuera))

        # Las cadenas de planos encadenados no pueden crecer sin límite: cada
        # eslabón está una generación más lejos del dibujo, y al tercero los
        # personajes se desfiguran. Es lo que hundió el método viejo.
        largo, previo = {}, {}
        for x in planos:
            if x.get("sigue_de"):
                previo[x["id"]] = x["sigue_de"]
        for x in planos:
            n, actual = 1, x["id"]
            while actual in previo:
                actual, n = previo[actual], n + 1
            largo[x["id"]] = n
        for pid, n in largo.items():
            if n > 3:
                avisos.append(f"{pid} es el eslabón {n} de una cadena: al tercero la "
                              f"identidad se degrada. Cortá y arrancá de un dibujo nuevo.")
        huerfanos = [a for a, b in previo.items() if b not in {x["id"] for x in planos}]
        if huerfanos:
            avisos.append("encadenan de un plano que no existe: " + " ".join(huerfanos))

        # Densidad y emoción de cada línea: es el paso que evita sintetizar
        # algo que no va a entrar en su hueco.
        avisos += vozmod.revisar(self.lineas_de_voz(planos))

        # Assets madre declarados contra los que usan los planos.
        declarados = {a["id"] for a in self.madre}
        if declarados:
            usados = {r for p in self.planos for r in self._refs_de(p)}
            faltan = usados - declarados
            if faltan:
                avisos.append("assets madre usados pero no declarados: " + " ".join(sorted(faltan)))
        return avisos

    def overlays(self, planos: list[dict]) -> list[tuple[float, float, str, str]]:
        """(entra, sale, plano, texto) de cada texto en pantalla.

        Es una instrucción de POST, no de generación: los modelos destrozan el
        texto, así que nunca se le pide al generador. Sale acá para que quien
        monta sepa qué poner y cuándo."""
        est = self.estructura_resuelta()
        lt = dict(zip((x["id"] for x in planos), est.linea_de_tiempo(planos)))
        out = []
        for x in planos:
            if x.get("texto"):
                a, b = lt[x["id"]]
                out.append((round(a, 2), round(b, 2), x["id"], x["texto"]))
        return out

    def brief(self, planos: list[dict] | None = None) -> str:
        """El documento de dirección: la estructura, tramo por tramo, con los
        planos que la cubren (o los huecos, si todavía no hay planos)."""
        est = self.estructura_resuelta()
        return est.brief(planos, titulo=self.titulo)

    def resumen(self, planos: list[dict]) -> str:
        est = self.estructura_resuelta()
        lt = est.linea_de_tiempo(planos)
        total = lt[-1][1] if lt else 0.0
        genera = sum(p["segundos"] for p in planos)
        w, h = self.wh
        L = [f"{self.titulo} · {self.formato} · {len(planos)} planos · {w}×{h}",
             f"  se genera ....... {genera:6.1f} s",
             f"  va a la línea ... {total:6.1f} s   ({grilla.mmss(total)})"]
        if genera - total > 0.05:
            L.append(f"  se descarta ..... {genera - total:6.1f} s "
                     f"({(genera - total) / genera * 100:.0f} %)")
        L.append("")
        L.append(f"  {'id':<5} {'tramo':<12} {'gen':>6} {'en línea':>13}  función")
        for p, (a, b) in zip(planos, lt):
            L.append(f"  {p['id']:<5} {str(p.get('tramo') or ''):<12} {p['segundos']:5.1f}s "
                     f"{a:6.1f}-{b:<6.1f} {p.get('funcion', '')[:44]}")
        con_voz = [p for p in planos if p["dialogo"]]
        if con_voz:
            L.append(f"\n  {len(con_voz)} planos con diálogo, un solo personaje en cada uno")
        if self.voz:
            L.append(f"  {len(self.voz)} líneas de voz en off (ElevenLabs, montadas encima)")
        return "\n".join(L)

    # --------------------------------------------------------- escritura
    def escribir(self, carpeta: Path | None = None, log=print) -> dict[str, Path]:
        """Escribe storyboard.json, planos.json, brief.md y, si hay, voz.txt."""
        carpeta = Path(carpeta or self.raiz)
        carpeta.mkdir(parents=True, exist_ok=True)
        sb, pl = self.construir()
        salidas = {
            "storyboard": carpeta / "storyboard.json",
            "planos": carpeta / "planos.json",
            "brief": carpeta / "brief.md",
        }
        salidas["storyboard"].write_text(json.dumps(sb, ensure_ascii=False, indent=2),
                                         encoding="utf-8")
        salidas["planos"].write_text(json.dumps(pl, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
        salidas["brief"].write_text(self.brief(pl["planos"]), encoding="utf-8")
        if self.voz:
            L = [f"{self.titulo} — voz en off para ElevenLabs", "=" * 46, "",
                 "No la genera H3: va grabada aparte y montada encima. Así queda",
                 "idéntica en todas las líneas, que es lo que H3 no sabe resolver.", ""]
            for t, pid, texto in self.guion_de_voz(pl["planos"]):
                L.append(f"  {t:6.1f} s  ({pid or '—'})   {texto}")
            salidas["voz"] = carpeta / "voz_en_off.txt"
            salidas["voz"].write_text("\n".join(L) + "\n", encoding="utf-8")
        ov = self.overlays(pl["planos"])
        if ov:
            L = [f"{self.titulo} — textos en pantalla", "=" * 46, "",
                 "Van como OVERLAY EN POST. Nunca se le piden al generador: los",
                 "modelos de imagen y video destrozan el texto, y en un gancho eso",
                 "es fatal.", "",
                 "El del gancho es la mitad del gancho: antepone el resultado",
                 "concreto, no la promesa genérica.", ""]
            for a, b, pid, txt in ov:
                L.append(f"  {a:6.1f} – {b:5.1f} s  ({pid})   {txt}")
            salidas["textos"] = carpeta / "texto_en_pantalla.txt"
            salidas["textos"].write_text("\n".join(L) + "\n", encoding="utf-8")
        if self.madre:
            salidas["madre"] = carpeta / "madre.json"
            salidas["madre"].write_text(json.dumps(
                {"_comentario": "Assets madre: hojas de modelo y locaciones. Se generan "
                                "una vez y son la referencia de todos los fotogramas.",
                 "aspecto": self.aspecto, "refs": list(self.refs_estilo),
                 "assets": self.madre}, ensure_ascii=False, indent=2), encoding="utf-8")
        for k, v in salidas.items():
            log(f"  {k:<11} {v}")
        avisos = self.validar(pl["planos"])
        if avisos:
            log(f"\n  {len(avisos)} aviso(s):")
            for a in avisos:
                log(f"    ⚠ {a}")
        return salidas


def _slug(t: str) -> str:
    limpio = "".join(c.lower() if c.isalnum() else "-" for c in t)
    return "-".join(x for x in limpio.split("-") if x)[:40]
