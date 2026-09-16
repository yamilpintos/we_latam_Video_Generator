/* La Fábrica · frontend. Sin framework: rutas por hash, fetch a /api, y dos
   librerías por CDN para la portada (Three.js) y las transiciones (GSAP). */

const $ = (s, el = document) => el.querySelector(s);
const h = (s) => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const usd = (x) => x == null ? "—" : "$" + Number(x).toFixed(2);
const mins = (s) => { s = Math.round(s || 0); return s < 90 ? `${s} s` : `${Math.floor(s / 60)} min ${s % 60 ? (s % 60) + " s" : ""}`.trim(); };
const fmtHora = (t) => new Date(t * 1000).toLocaleTimeString("es-AR", {hour: "2-digit", minute: "2-digit"});
const CPS = {pablo: 10.5, kate: 16.7};

async function api(ruta, opts = {}) {
  const r = await fetch("/api" + ruta, {
    headers: {"Content-Type": "application/json"},
    ...opts, body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  const txt = await r.text();
  let data; try { data = JSON.parse(txt); } catch { data = {detail: txt}; }
  if (!r.ok) throw new Error(data.detail || r.statusText);
  return data;
}

function toast(msg, bad = false) {
  const t = document.createElement("div");
  t.className = "toast" + (bad ? " bad" : ""); t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), bad ? 6000 : 3200);
}

function modal(html) {
  const m = $("#modal");
  m.innerHTML = `<div class="modal-bg" onclick="if(event.target===this)cerrarModal()"><div class="modal">${html}</div></div>`;
  gsap.from(".modal", {y: 14, opacity: 0, duration: .25});
}
function cerrarModal() { $("#modal").innerHTML = ""; }
function lightbox(src) {
  $("#modal").innerHTML = `<div class="modal-bg lightbox" onclick="cerrarModal()"><img src="${src}"></div>`;
}
function confirmar(titulo, cuerpo, etiqueta, fn, peligro = false) {
  modal(`<h3>${titulo}</h3><div class="muted" style="margin-bottom:18px">${cuerpo}</div>
    <div class="row" style="justify-content:flex-end"><button class="btn" onclick="cerrarModal()">Cancelar</button>
    <button class="btn ${peligro ? "d" : "p"}" id="mconf">${etiqueta}</button></div>`);
  $("#mconf").onclick = async () => { cerrarModal(); await fn(); };
}

/* ─────────────────────────────────────────────── tareas en segundo plano */
const tareasVivas = new Map();
function seguirTarea(t, alTerminar) {
  tareasVivas.set(t.id, {t, alTerminar});
  pintarTareas();
}
async function pollTareas() {
  for (const [id, x] of tareasVivas) {
    try {
      const t = await api(`/tareas/${id}?lineas=8`);
      x.t = t;
      if (t.estado !== "corriendo") {
        tareasVivas.delete(id);
        toast(`${t.nombre}: ${t.estado === "ok" ? "terminó" : "falló"} (${mins(t.segundos)})`, t.estado !== "ok");
        x.alTerminar && x.alTerminar(t);
      }
    } catch {}
  }
  pintarTareas();
}
function pintarTareas() {
  const box = $("#tasks");
  box.innerHTML = [...tareasVivas.values()].map(({t}) => `
    <div class="task"><div class="h"><i class="dot live" style="color:var(--ac)"></i><b>${h(t.nombre)}</b>
      <span class="tiny">${h(t.slug || "")} · ${mins(t.segundos)}</span>
      <button class="btn s" onclick="matar('${t.id}')">parar</button></div>
      <pre>${h(t.log)}</pre></div>`).join("");
}
async function matar(id) { await api(`/tareas/${id}/matar`, {method: "POST"}); toast("tarea detenida"); }
setInterval(pollTareas, 2000);

/* ─────────────────────────────────────────────── router */
const rutas = {};
function ruta(path, fn) { rutas[path] = fn; }
async function navegar() {
  const hash = location.hash.replace(/^#/, "") || "/";
  const [path, ...rest] = hash.split("/").filter(Boolean);
  document.querySelectorAll(".top nav a").forEach(a => a.classList.toggle("on", a.dataset.r === "/" + (path || "")));
  const vista = $("#vista");
  vista.style.opacity = 0;
  try {
    const fn = rutas["/" + (path || "")] || rutas["/"];
    await fn(rest);
  } catch (e) {
    vista.innerHTML = `<div class="wrap"><div class="card"><h3>Error</h3><div class="pre">${h(e.message)}</div></div></div>`;
  }
  gsap.to(vista, {opacity: 1, duration: .35});
  gsap.from("#vista .card, #vista .puerta", {y: 12, opacity: 0, stagger: .04, duration: .35, clearProps: "all"});
  document.body.classList.toggle("en-portada", !path);
}
window.addEventListener("hashchange", navegar);

/* ─────────────────────────────────────────────── estado Vast en la barra */
async function estadoVast() {
  const el = $("#vast-estado");
  try {
    const d = await api("/vast/instancias");
    const vivas = d.instancias.length;
    if (vivas) {
      const gasto = d.instancias.reduce((s, i) => s + (i.corrida?.acumulado || 0), 0);
      el.className = "pill warn"; el.innerHTML = `<i class="dot live"></i> ${vivas} máquina${vivas > 1 ? "s" : ""} viva${vivas > 1 ? "s" : ""} · ${usd(gasto)}`;
    } else { el.className = "pill ok"; el.innerHTML = `<i class="dot"></i> Vast: nada cobrando`; }
  } catch { el.className = "pill bad"; el.innerHTML = `<i class="dot"></i> Vast sin respuesta`; }
}
setInterval(estadoVast, 30000);

/* ─────────────────────────────────────────────── portada */
ruta("/", async () => {
  let ps = []; try { ps = await api("/proyectos"); } catch {}
  const esLoop = p => String(p.estructura).startsWith("loop"), esRecap = p => String(p.estructura).startsWith("recap");
  const n = (f) => ps.filter(p => f(p)).length;
  const masters = ps.reduce((s, p) => s + (p.estado?.masters?.length || 0), 0);
  $("#vista").innerHTML = `
  <section class="hero">
    <h1>Del guion al <span>máster</span>,<br>con la GPU cobrando lo justo.</h1>
    <p class="lead">Pegás tu guion. La app lo traduce a planos, dibuja los fotogramas, alquila la máquina, controla los clips y mezcla. Cada paso muestra lo que cuesta antes de gastarlo.</p>
    <div class="puertas">
      <div class="puerta" onclick="location.hash='#/nuevo/short'"><span class="k">VERTICAL · 15 A 90 S</span><h2>Short</h2>
        <p>Tu guion, en voz en off con subtítulos. Tres clips para una muestra de 15 s; doce para un minuto.</p><span class="n">${n(p => p.formato === "short" && !esLoop(p) && !esRecap(p))} proyectos</span></div>
      <div class="puerta" onclick="location.hash='#/nuevo/largo'"><span class="k">VERTICAL · 3 A 8 MIN</span><h2>Largo</h2>
        <p>Recap con voz continua. Primero el audio, medido contra la voz elegida; después los planos que lo sirven.</p><span class="n">${n(esRecap)} proyectos</span></div>
      <div class="puerta" onclick="location.hash='#/musica'"><span class="k">16:9 · LOOP</span><h2>Music video</h2>
        <p>Decís qué música y qué escena. La app compone la pista, hace el loop y el video dura lo que dure la música.</p><span class="n">${n(esLoop)} loops</span></div>
      <div class="puerta" onclick="location.hash='#/libre'"><span class="k">CHAT · SIN ESTRUCTURA</span><h2>Libre</h2>
        <p>Escribís un prompt, ves la imagen, describís el movimiento y sale un clip de MiniMax. Para probar ideas antes de un guion.</p><span class="n">como un playground</span></div>
    </div>
    <div class="card" id="maq" style="margin-top:34px"><h3>La máquina</h3><div class="muted">consultando…</div></div>
    <div class="card" id="cola" style="margin-top:14px"><h3>La cola</h3><div class="muted">consultando…</div></div>
    <div class="stats"><div><b>${ps.length}</b>proyectos</div><div><b>${masters}</b>másters</div><div><b>5,17 s</b>por clip, sin excepción</div><div><b>4× 5090</b>verificada o se espera</div></div>
  </section>`;
  pintarMaquina(); pintarCola();
});

/* ─────────────────────────────────────────────── la cola (portada) */
let colaTimer = null;
const ESTADOS_COLA = {pendiente: "", generando: "warn", bajando: "warn", bajado: "ok", error: "bad"};
async function pintarCola() {
  const box = $("#cola"); if (!box) return;
  let c; try { c = await api("/cola"); } catch (e) { box.innerHTML = `<h3>La cola</h3><div class="pre">${h(e.message)}</div>`; return; }
  const pend = c.items.filter(i => i.estado === "pendiente" || i.estado === "error").length;
  box.innerHTML = `<h3>La cola <span class="pill ${c.corriendo ? "warn" : pend ? "ac" : ""}">${c.corriendo ? '<i class="dot live"></i> corriendo' : pend ? pend + " por generar" : "vacía"}</span></h3>
    <p class="muted">Varios videos con una sola máquina: enciende si hace falta, genera uno tras otro, baja cada uno y apaga al final. Se agregan desde <a href="#/proyectos">Proyectos</a> (los que ya están empaquetados).</p>
    ${c.items.length ? `<table><tr><th>proyecto</th><th>estado</th><th></th></tr>${c.items.map(i => `<tr><td><a href="#/p/${i.slug}">${h(i.titulo || i.slug)}</a>${i.zip ? "" : ' <span class="pill bad">sin ZIP</span>'}</td>
      <td><span class="pill ${ESTADOS_COLA[i.estado] || ""}">${i.estado}</span> <span class="tiny">${h(i.nota || "")}</span></td>
      <td>${i.estado !== "generando" && !c.corriendo ? `<button class="btn s" onclick="quitarDeCola('${i.slug}')">quitar</button>` : ""}</td></tr>`).join("")}</table>` : ""}
    ${c.tarea ? `<pre class="pre" style="margin-top:10px;max-height:120px">${h(c.tarea.log)}</pre>` : ""}
    <div class="row" style="margin-top:12px">
      ${!c.corriendo ? `<button class="btn p" ${pend ? "" : "disabled"} onclick="correrCola()">Correr la cola</button>
        <label class="tiny"><input type="checkbox" id="apagar-fin" ${c.apagar_al_final !== false ? "checked" : ""}> apagar la máquina al terminar</label>` : `<span class="tiny">La cola avanza sola; podés cerrar la página.</span>`}
    </div>`;
  clearTimeout(colaTimer);
  if (c.corriendo) colaTimer = setTimeout(() => { if ($("#cola")) pintarCola(); }, 20000);
}
async function agregarACola(slug) {
  try { await api("/cola/agregar", {method: "POST", body: {slug}}); toast("agregado a la cola"); navegar(); } catch (e) { toast(e.message, true); }
}
async function quitarDeCola(slug) { try { await api("/cola/quitar", {method: "POST", body: {slug}}); pintarCola(); } catch (e) { toast(e.message, true); } }
async function correrCola() {
  const apagar = $("#apagar-fin")?.checked !== false;
  let m = null; try { m = await api("/maquina"); } catch {}
  const hayMaq = m && m.fase === "lista";
  confirmar("Correr la cola",
    `${hayMaq ? "La máquina ya está lista: se usa ésa." : "No hay máquina lista: <b>se alquila una 4×5090</b> (o se espera a que aparezca una apta) y se instala H3 una sola vez."}<br>
     Después genera cada proyecto de la cola, lo baja, y ${apagar ? "<b>apaga la máquina al terminar</b>" : "deja la máquina encendida (acordate de apagarla)"}.<br><br>Esto cobra desde que la máquina arranca hasta que se apaga.`,
    "Correr", async () => {
      try { const d = await api("/cola/correr", {method: "POST", body: {confirmar: true, apagar_al_final: apagar}}); seguirTarea(d.tarea, () => { pintarCola(); pintarMaquina(); }); toast("cola en marcha"); setTimeout(() => { pintarCola(); pintarMaquina(); }, 1500); }
      catch (e) { toast(e.message, true); }
    });
}

/* ─────────────────────────────────────────────── la máquina (portada) */
let maqTimer = null;
const FASES = {apagada: ["apagada", ""], buscando: ["buscando una 4×5090 apta…", "warn"], arrancando: ["arrancando", "warn"],
  instalando: ["instalando H3", "warn"], lista: ["lista", "ok"], fallo: ["falló", "bad"]};
async function pintarMaquina() {
  const box = $("#maq"); if (!box) return;
  let m; try { m = await api("/maquina"); } catch (e) { box.innerHTML = `<h3>La máquina</h3><div class="pre">${h(e.message)}</div>`; return; }
  const [ftxt, fcl] = FASES[m.fase] || [m.fase, ""];
  const viva = ["buscando", "arrancando", "instalando", "lista"].includes(m.fase);
  const inst = m.instalacion, gen = m.generando;
  box.innerHTML = `<h3>La máquina <span class="pill ${fcl}">${viva && m.fase !== "buscando" ? '<i class="dot live"></i> ' : ""}${ftxt}${m.instancia ? ` · ${m.instancia}` : ""}</span>
      <span class="pill" title="crédito en Vast">saldo ${usd(m.saldo)}</span></h3>
    <div class="kpis" style="margin-bottom:12px">
      <div class="kpi"><div class="l">precio</div><div class="v">${m.dph ? "$" + Number(m.dph).toFixed(3) + '<span class="tiny">/h</span>' : "—"}</div></div>
      <div class="kpi"><div class="l">${viva ? "encendida hace" : "última sesión"}</div><div class="v">${m.minutos ? m.minutos + " min" : "—"}</div></div>
      <div class="kpi"><div class="l">${viva ? "gastado" : "gastó"}</div><div class="v" style="color:var(--ac)">${usd(viva ? m.acumulado : m.gasto_final)}</div></div>
      <div class="kpi"><div class="l">dónde</div><div class="v" style="font-size:15px">${m.oferta ? h(m.oferta.geo) + `<div class="tiny">${m.oferta.inet} Mbps · fiab ${m.oferta.fiabilidad}</div>` : "—"}</div></div>
    </div>
    ${m.fase === "instalando" ? `<div class="tiny" style="margin-bottom:4px">Bajando los modelos de H3: ${inst?.gb ?? "?"} de 59 GB${inst?.pct != null ? ` · ${inst.pct} %` : ""}</div>
      <div class="bar"><i style="width:${inst?.pct ?? 0}%"></i></div><div class="tiny mono" style="margin-top:6px;white-space:pre-wrap">${h(inst?.ultimo || "")}</div>` : ""}
    ${m.fase === "arrancando" ? `<div class="tiny">El host está levantando la instancia (2 a 8 min). Si no arranca en 20, se destruye sola y se busca otra.</div>` : ""}
    ${m.fase === "buscando" ? `<div class="tiny">No hay ninguna 4×5090 verificada ahora. Consulta cada minuto y alquila sola cuando aparezca. Podés cerrar la página.</div>` : ""}
    ${gen ? `<div style="margin:10px 0"><b>Generando:</b> <a href="#/p/${gen.slug}/maquina">${h(gen.titulo || gen.slug)}</a> · ${gen.hechos ?? "?"}/${gen.total ?? "?"} clips
      <div class="bar" style="margin-top:6px"><i style="width:${gen.total ? Math.round(gen.hechos / gen.total * 100) : 0}%"></i></div></div>` : ""}
    ${m.fase === "lista" && !gen ? `<div class="tiny" style="margin-bottom:8px">H3 instalado. Elegí un proyecto empaquetado y tocá «Generar en la máquina» en su paso Máquina. Cada minuto que pasa cuesta ${m.dph ? "$" + (m.dph / 60).toFixed(3) : "plata"}.</div>` : ""}
    ${m.fase === "lista" && gen && gen.total && gen.hechos >= gen.total ? `<div class="tiny" style="margin-bottom:8px;color:var(--ok)">Todos los clips están en la máquina: bajalos desde el proyecto y después apagá.</div>` : ""}
    <div class="row" style="margin-top:8px">
      ${!viva ? `<button class="btn p" onclick="encenderMaquina()">Buscar una 4×5090 y encender</button>` : ""}
      ${viva ? `<button class="btn d" onclick="apagarMaquina()">Apagar (destruir)</button>` : ""}
      ${m.ssh ? `<code class="tiny">${h(m.ssh)}</code>` : ""}
      ${m.tareas?.length ? `<span class="tiny">${h(m.tareas[0].nombre)}: ${h((m.tareas[0].log || "").split("\n").pop())}</span>` : ""}
    </div>`;
  clearTimeout(maqTimer);
  if (viva) maqTimer = setTimeout(() => { if ($("#maq")) pintarMaquina(); }, m.fase === "instalando" ? 15000 : 20000);
}
async function encenderMaquina() {
  let o = null; try { o = (await api("/maquina/mejor")).oferta; } catch (e) { return toast(e.message, true); }
  const cuerpo = o ? `Mejor oferta ahora: <b>${o.gpus}× ${h(o.gpu)}</b> en ${h(o.geo)} a <b>$${o.dph.toFixed(3)}/h</b>, ${o.inet} Mbps, fiabilidad ${o.fiabilidad}.<br>
      Arranque + instalación de H3 (59 GB): unos <b>${usd(o.instalacion_estimada)}</b>. Después la máquina queda lista y cada proyecto cuesta sólo su generación.<br><br>Empieza a cobrar de inmediato y sigue cobrando hasta que la apagues.`
    : `Ahora no hay ninguna 4×5090 verificada. Si confirmás, la app consulta cada minuto y alquila sola la primera que aparezca (sólo aptas, techo $4/h). Podés cerrar la página; el cazador sigue mientras el servidor esté vivo.`;
  confirmar("Encender la máquina", cuerpo, o ? "Alquilar e instalar" : "Buscar y encender cuando haya", async () => {
    try { const d = await api("/maquina/encender", {method: "POST", body: {id: o?.id ?? null, confirmar: true}}); seguirTarea(d.tarea, () => pintarMaquina()); toast(o ? "alquilando…" : "buscando…"); setTimeout(pintarMaquina, 1500); }
    catch (e) { toast(e.message, true); }
  });
}
function apagarMaquina() {
  confirmar("Apagar la máquina", "Se destruye la instancia: deja de cobrar y se pierde todo lo que haya adentro (modelos y clips no bajados). <b>Bajá los clips antes.</b>", "Apagar", async () => {
    try { const d = await api("/maquina/apagar", {method: "POST", body: {confirmar: true}}); toast(`apagada · gastó ${usd(d.gasto_final)} en ${d.minutos} min`); estadoVast(); pintarMaquina(); }
    catch (e) { toast(e.message, true); }
  }, true);
}

/* ─────────────────────────────────────────────── proyectos */
ruta("/proyectos", async () => {
  const ps = await api("/proyectos");
  $("#vista").innerHTML = `<div class="wrap"><h1>Proyectos</h1><p class="sub">Cada uno es una carpeta en <code>mis-videos/</code>. El estado sale de lo que existe en la carpeta.</p>
    <div class="row" style="margin-bottom:16px"><a class="btn p" href="#/nuevo/short">＋ Short</a><a class="btn" href="#/nuevo/largo">＋ Largo</a><a class="btn" href="#/nuevo/loop">＋ Loop</a></div>
    <div class="grid g3">${ps.map(tarjetaProyecto).join("")}</div></div>`;
});
function etapa(p) {
  const e = p.estado; if (!e) return ["error", "bad"];
  if (e.masters.length) return ["máster listo", "ok"];
  if (e.corrida && !e.corrida.fin) return ["máquina viva", "warn"];
  if (e.clips.hechos === e.clips.esperados && e.clips.esperados) return ["clips bajados", "ac"];
  if (e.zip) return ["empaquetado", "ac"];
  if (e.assets.hechos === e.assets.esperados && e.assets.esperados) return ["dibujos listos", ""];
  if (e.assets.hechos) return [`dibujos ${e.assets.hechos}/${e.assets.esperados}`, ""];
  return ["escrito", ""];
}
function tarjetaProyecto(p) {
  if (p.error) return `<div class="card"><h3>${h(p.titulo)} <span class="pill bad">roto</span></h3><div class="tiny">${h(p.error)}</div></div>`;
  const [et, cl] = etapa(p); const e = p.estado;
  return `<div class="card" style="cursor:pointer" onclick="location.hash='#/p/${p.slug}'">
    <h3>${h(p.titulo)} <span class="pill ${cl}">${et}</span></h3>
    <div class="muted">${p.formato === "largo" ? "16:9" : "9:16"} · ${h(p.estructura)} · ${e.planos} planos · ${mins(e.segundos)}</div>
    <div class="tiny" style="margin-top:8px">dibujos ${e.assets.hechos}/${e.assets.esperados} · clips ${e.clips.hechos}/${e.clips.esperados}${e.corrida ? ` · GPU ${usd(e.corrida.gasto_final ?? e.corrida.acumulado)}` : ""}</div>
    ${e.zip && e.clips.hechos < e.clips.esperados ? `<div style="margin-top:8px"><button class="btn s" onclick="event.stopPropagation();agregarACola('${p.slug}')">＋ a la cola</button></div>` : ""}
  </div>`;
}

/* ─────────────────────────────────────────────── escenas prearmadas para loops */
const ESCENAS = [
  {n: "La ventana de lluvia", e: 1, t: "Un cuarto de estudio de noche junto a una ventana grande bajo la lluvia. Escritorio de madera con lámpara de bronce de pantalla verde, taza humeante, cuaderno abierto, auriculares; tocadiscos girando en una repisa; alféizar con manta bordó y plantas; un gato gris dormido en la manta. Afuera, luces borrosas de la ciudad. Sin gente. Se mueve despacio: gotas en el vidrio, vapor, el gato respira, el disco gira."},
  {n: "Estanque de koi", e: 1, t: "Un jardín japonés de noche bajo lluvia fina: estanque negro con koi naranjas y blancos, farol de piedra con vela, dos farolitos rojos de papel colgados de un arce, musgo en las piedras, nenúfares, un caño de bambú que gotea. Sin gente. Se mueve despacio: los koi, los anillos de lluvia, la llama, las gotas en las hojas."},
  {n: "Invernadero en órbita", e: 1, t: "Un pequeño módulo invernadero en órbita: bandejas hidropónicas con tomate, frutilla y hierbas bajo luz cálida y suave (no magenta), y por un gran ojo de buey la Tierra girando despacio. Un ventilador en la rejilla, una regadera sujeta con velcro, hierbas secas colgadas. Sin gente. Se mueve despacio: la Tierra, una gota que flota, las hojas."},
  {n: "Cabaña con chimenea", e: 0, t: "El interior de una cabaña de madera en una noche de nieve: chimenea encendida, pava humeando sobre la estufa, un perro dormido en la alfombra, una ventana con nieve cayendo afuera, mantas, libros, una vela. Sin gente. Se mueve despacio: el fuego, la nieve, el vapor, el perro respira."},
  {n: "Vagón nocturno", e: 0, t: "El interior de un vagón de tren vacío de noche bajo la lluvia: asientos de cuero cálidos, luces amarillas, un paraguas mojado apoyado, gotas horizontales en la ventana, luces de pueblos pasando afuera. Sin gente. Se mueve despacio: las luces que pasan, el vaivén, las gotas."},
  {n: "Acuario de medusas", e: 0, t: "Un living a oscuras iluminado sólo por una pared de acuario: medusas azules bioluminiscentes flotando, burbujas, la silueta de un sofá y una planta, la luz azul ondulando en el techo. Sin gente. Se mueve despacio: las medusas pulsan, las burbujas suben, la luz ondula."},
  {n: "Faro en la tormenta", e: 0, t: "La sala de la lámpara de un faro de piedra en una noche de tormenta: la lámpara girando, lluvia en los cristales, un mar negro con espuma allá abajo, una taza de café, un cuaderno de bitácora, un impermeable colgado. Sin gente. Se mueve despacio: el haz que gira, la lluvia, las olas lejanas."},
  {n: "Biblioteca antigua", e: 0, t: "Una biblioteca antigua de noche: estantes hasta el techo, una lámpara de lectura verde, un libro abierto, polvo en el haz de luz, una escalera de madera, lluvia contra un ventanal alto con vitrales. Sin gente. Se mueve despacio: el polvo, la llama de una vela, la lluvia."},
  {n: "Cafetería bajo la lluvia", e: 4, t: "Una cafetería pequeña de noche vista desde adentro: la vidriera empañada con gotas, luces de neón borrosas afuera, una taza humeante en la barra, una planta, una máquina de café con vapor, mesas vacías. Sin gente. Se mueve despacio: las gotas, el vapor, el neón que parpadea."},
  {n: "Playa de noche", e: 0, t: "Una playa desierta de noche con luna llena: olas suaves que llegan y se van, una fogata chica con brasas, una manta, una lámpara de camping, estrellas. Sin gente. Se mueve despacio: las olas, las brasas, la llama, las nubes."},
];

/* ─────────────────────────────────────────────── nuevo: el guion */
ruta("/nuevo", async ([formato]) => {
  const op = await api("/guion/opciones");
  const f = formato === "largo" ? "largo" : "short";
  const esLoop = formato === "loop";
  const ests = op.estructuras.filter(e => esLoop ? e.nombre.startsWith("loop")
    : f === "largo" ? (e.nombre.startsWith("recap") || (e.formato === "largo" && !e.nombre.startsWith("loop")))
    : (e.formato === "short" && !e.nombre.startsWith("recap")));
  const estDefault = esLoop ? "loop" : f === "largo" ? "recap" : "short-15";
  const titulo = esLoop ? "Nuevo loop" : f === "largo" ? "Nuevo largo" : "Nuevo short";
  const sub = esLoop ? "Describí la escena: un lugar, una hora, una luz, y qué se mueve despacio. La app la traduce a doce encuadres."
    : "Pegá tu guion. La app lo traduce a planos siguiendo la estructura, lo valida y te lo muestra. El guion no se reescribe: se ilustra.";
  const ph = esLoop ? "Un jardín japonés de noche bajo lluvia fina: estanque negro con koi, un farol de piedra con vela, farolitos rojos, musgo, un arce…"
    : "Soy Tomás, buzo de mantenimiento en la represa. Bajé a 42 metros a revisar una compuerta que no cerraba…";
  $("#vista").innerHTML = `<div class="wrap"><h1>${titulo}</h1><p class="sub">${sub}</p>
    <div class="grid g2">
      <div class="card" style="grid-column:1/-1"><h3>${esLoop ? "La escena" : "El guion"}</h3>
        ${esLoop ? `<select id="escena" style="margin-bottom:8px"><option value="">Escena propia (escribila abajo)</option>${ESCENAS.map((s, i) => `<option value="${i}">${h(s.n)}</option>`).join("")}</select>` : ""}
        <textarea id="guion" class="json" style="font-family:var(--font);font-size:15px;min-height:240px" placeholder="${ph}"></textarea>
        <div class="tiny" style="margin-top:6px"><span id="nchars">0</span> caracteres${esLoop ? "" : ` · con la voz elegida entran unos <span id="cabe">—</span> caracteres en <span id="durest">—</span> s`}</div></div>
      <div class="card"><h3>Título y formato</h3>
        <input id="titulo" placeholder="Título" style="margin-bottom:8px">
        <select id="estructura">${ests.map(e => `<option value="${e.nombre}" ${e.nombre === estDefault ? "selected" : ""}>${e.nombre} · ${e.duracion} s${e.retencion ? " · retención " + Math.round(e.retencion * 100) + " %" : ""}</option>`).join("")}</select>
        ${esLoop ? `<div style="margin-top:8px"><select id="duracion"><option value="5.17" selected>UNA escena · 1 clip de 5 s, cerrado con fundido</option><option value="10.08">UNA escena · 1 clip de 10 s (riesgo de VRAM)</option><option value="15.5">3 escenas · 3 clips · 15 s</option><option value="31">Loop de 30 s · 6 clips</option><option value="46.5">Loop de 45 s · 9 clips</option><option value="62">Loop de 60 s · 12 clips</option><option value="93">Loop de 90 s · 18 clips</option></select>
          <div class="tiny" style="margin-top:4px">Una escena: un solo plano que se repite, cerrado con un fundido de la cola sobre la cabeza (o ping-pong). Varias escenas: cortes entre encuadres del mismo lugar. Después, en Music video, el loop se repite hasta cubrir la pista.</div></div>` : `<div style="margin-top:8px"><select id="voz"><option value="pablo">Voz: Pablo, argentino (10,5 cps)</option><option value="kate">Voz: Kate (16,7 cps)</option><option value="">Sin voz en off</option></select></div>`}
        <textarea id="notas" style="margin-top:8px;min-height:60px" placeholder="Notas para el traductor (opcional): tono, qué no mostrar, cortes que querés…"></textarea></div>
      <div class="card"><h3>Estilo visual</h3>
        <select id="estilo">${op.estilos.map(e => `<option value="${e.i}">${h(e.nombre)}</option>`).join("")}<option value="">Estilo propio (escribilo abajo)</option></select>
        <textarea id="estilo_libre" style="margin-top:8px;min-height:90px" placeholder="Opcional: tu propio estilo, en inglés. Reemplaza al preset."></textarea>
        <div class="tiny" style="margin-top:6px" id="estilo_prev"></div></div>
    </div>
    <div class="row" style="margin-top:14px"><button class="btn p" id="btn-trad">Traducir a planos</button>
      <span class="tiny">1 a 3 llamadas al modelo, 1-3 minutos. Después: dibujos, máquina, clips, máster.</span></div>
    <div id="err" class="tiny" style="color:var(--bad);margin-top:8px"></div></div>`;
  const actualizar = () => {
    $("#nchars").textContent = $("#guion").value.length;
    const e = ests.find(x => x.nombre === $("#estructura").value); const v = $("#voz")?.value;
    if ($("#cabe")) { $("#cabe").textContent = v && e ? Math.round(e.duracion * CPS[v] * 0.9) : "—"; $("#durest").textContent = e ? e.duracion : "—"; }
    const pe = op.estilos[Number($("#estilo").value)]; $("#estilo_prev").textContent = $("#estilo").value === "" ? "" : pe?.prompt || "";
  };
  ["guion", "estructura", "voz", "estilo"].forEach(id => $("#" + id)?.addEventListener("input", actualizar));
  $("#escena")?.addEventListener("change", () => {
    const s = ESCENAS[Number($("#escena").value)]; if (!s) return;
    $("#guion").value = s.t; if (!$("#titulo").value) $("#titulo").value = s.n.toUpperCase(); $("#estilo").value = String(s.e); actualizar();
  });
  $("#btn-trad").onclick = () => traducirGuion(esLoop, f);
  actualizar();
});

/* ─────────────────────────────────────────────── libre: el chat con H3 */
let libreTimer = null;
ruta("/libre", async () => {
  const d = await api("/libre");
  const lista = d.maquina === "lista";
  $("#vista").innerHTML = `<div class="wrap"><h1>Libre <span class="pill ${lista ? "ok" : "warn"}">máquina ${h(d.maquina || "apagada")}</span></h1>
    <p class="sub">Un prompt → una imagen → un clip de MiniMax H3. Sin estructura, sin proyecto: para probar una idea, un estilo o un movimiento. La imagen cuesta 4 centavos; el clip, ~4 minutos de GPU de la máquina encendida.</p>
    <div class="card" style="margin-bottom:14px"><h3>Nuevo turno</h3>
      <textarea id="lp" style="min-height:80px" placeholder="Qué querés ver (en castellano o inglés): «un faro de piedra en una tormenta de noche, visto desde el mar, olas enormes, la lámpara girando»"></textarea>
      <div class="row" style="margin-top:8px"><select id="lasp" style="max-width:160px"><option value="16:9">16:9 horizontal</option><option value="9:16">9:16 vertical</option></select>
        <select id="lmotor" style="max-width:220px"><option value="openai">OpenAI / GPT (~$0,25)</option><option value="nanobanana">nano banana (~$0,04, sin créditos hoy)</option></select>
        <input id="lest" placeholder="estilo (opcional, en inglés): photorealistic, 35mm film grain…" style="flex:1;min-width:220px">
        <label class="btn s">subir imagen<input type="file" id="lfile" accept="image/*" hidden></label>
        <button class="btn p" onclick="libreImagen()">Crear imagen</button></div>
      <div id="lerr" class="tiny" style="color:var(--bad);margin-top:6px"></div></div>
    <div id="turnos"></div></div>`;
  $("#lfile").addEventListener("change", async (ev) => {
    const f = ev.target.files[0]; if (!f) return;
    const b64 = await new Promise(r => { const fr = new FileReader(); fr.onload = () => r(fr.result); fr.readAsDataURL(f); });
    libreImagen(b64);
  });
  pintarTurnos(d.turnos, d);
});
function pintarTurnos(ts, d) {
  const lista = d.maquina === "lista";
  $("#turnos").innerHTML = ts.map(t => `<div class="card" style="margin-bottom:12px"><div class="grid g2">
    <div><div class="tiny" style="margin-bottom:6px">${new Date(t.creado * 1000).toLocaleString("es-AR")} · ${t.aspecto} · ${h(t.origen_imagen)}</div>
      <img src="/api/libre/archivo/${t.imagen}" style="width:100%;border-radius:8px;cursor:zoom-in" onclick="lightbox('/api/libre/archivo/${t.imagen}')">
      <div class="muted" style="margin-top:6px">${h(t.prompt_imagen || "(imagen subida)")}</div></div>
    <div>${t.estado === "listo" ? `<video controls style="width:100%;border-radius:8px" src="/api/libre/archivo/${t.clip}"></video><div class="muted" style="margin-top:6px">${h(t.prompt_video)} · ${t.segundos} s</div>`
      : t.estado === "generando" ? `<div class="pill warn"><i class="dot live"></i> generando en la máquina… (~4 min)</div><div class="muted" style="margin-top:6px">${h(t.prompt_video)}</div>`
      : t.estado === "error" ? `<div class="pill bad">error</div><div class="tiny">${h(t.nota)}</div>`
      : `<textarea id="lv-${t.id}" style="min-height:70px" placeholder="Qué se mueve a partir de esta imagen (inglés recomendado): «locked-off camera; the beam of the lighthouse sweeps slowly; waves crash against the rocks; rain streaks the lens»"></textarea>
         <div class="row" style="margin-top:8px"><select id="ls-${t.id}" style="max-width:170px"><option value="5.167">5,17 s (seguro)</option><option value="5.875">5,88 s</option><option value="6.583">6,58 s (riesgo)</option><option value="10.083">10,08 s (riesgo)</option></select>
           <button class="btn p" ${lista && !d.ocupada ? "" : "disabled"} onclick="libreVideo('${t.id}')">Generar clip</button>
           <span class="tiny">${!lista ? "encendé la máquina desde el inicio" : d.ocupada ? "hay un turno generando" : ""}</span></div>`}
      ${t.nota && t.estado !== "error" ? `<div class="tiny">${h(t.nota)}</div>` : ""}</div></div></div>`).join("") || `<div class="muted">Todavía no hay turnos.</div>`;
  clearTimeout(libreTimer);
  if (ts.some(t => t.estado === "generando")) libreTimer = setTimeout(async () => { if (!$("#turnos")) return; const d2 = await api("/libre"); pintarTurnos(d2.turnos, d2); }, 12000);
}
async function libreImagen(b64 = null) {
  $("#lerr").textContent = ""; toast(b64 ? "subiendo…" : "dibujando… (10-20 s)");
  try { await api("/libre/imagen", {method: "POST", body: {prompt: $("#lp").value, aspecto: $("#lasp").value, estilo: $("#lest").value, imagen_b64: b64, motor: $("#lmotor").value}}); navegar(); }
  catch (e) { $("#lerr").textContent = e.message; }
}
async function libreVideo(id) {
  try { await api("/libre/video", {method: "POST", body: {id, prompt_video: $(`#lv-${id}`).value, segundos: Number($(`#ls-${id}`).value)}}); toast("clip lanzado en la máquina"); navegar(); }
  catch (e) { toast(e.message, true); }
}
async function traducirGuion(esLoop, formato) {
  const body = {guion: $("#guion").value, formato: esLoop ? "largo" : "short", estructura: $("#estructura").value,
    titulo: $("#titulo").value.trim(), estilo: $("#estilo").value === "" ? null : Number($("#estilo").value),
    estilo_libre: $("#estilo_libre").value, voz: esLoop ? null : ($("#voz").value || null), negativos: !esLoop, notas: $("#notas").value,
    duracion: esLoop ? Number($("#duracion").value) : null};
  if (!body.titulo) return $("#err").textContent = "Falta el título.";
  if (body.guion.trim().length < 40) return $("#err").textContent = "El guion es demasiado corto.";
  $("#btn-trad").disabled = true;
  try {
    const d = await api("/guion", {method: "POST", body});
    toast("traduciendo el guion…");
    seguirTarea(d.tarea, (t) => { if (t.estado === "ok") location.hash = `#/p/${d.slug}`; else toast("la traducción falló: mirá el log", true); });
    location.hash = `#/p/${d.slug}/espera`;
  } catch (e) { $("#err").textContent = e.message; $("#btn-trad").disabled = false; }
}

/* ─────────────────────────────────────────────── el proyecto: los pasos */
let P = null;
let pasoActual = null;
ruta("/p", async ([slug, paso]) => {
  if (paso === "espera") {
    $("#vista").innerHTML = `<div class="wrap"><h1>Traduciendo el guion…</h1><p class="sub">Una a tres llamadas al modelo. Cuando termine, esta página pasa sola al proyecto. El avance está abajo a la derecha.</p>
      <div class="card"><div class="muted">El guion quedó guardado en <code>mis-videos/${h(slug)}/guion.txt</code>. Si la traducción falla, el log dice por qué; el guion no se pierde.</div></div></div>`;
    return;
  }
  P = await api(`/proyectos/${slug}`);
  const e = P.estado;
  const conVoz = (P.proyecto.voz || []).length > 0 || P.planos.some(x => x.dialogo);
  const hechos = {
    proyecto: P.avisos.length === 0,
    voz: false,
    dibujos: e.assets.hechos === e.assets.esperados && e.assets.esperados > 0,
    maquina: e.clips.hechos === e.clips.esperados && e.clips.esperados > 0,
    clips: e.clips.hechos === e.clips.esperados && e.clips.esperados > 0,
    master: e.masters.length > 0,
  };
  pasoActual = paso || (!hechos.proyecto ? "proyecto" : !hechos.dibujos ? "dibujos" : !hechos.maquina ? "maquina" : !hechos.master ? "clips" : "master");
  const pasos = [["proyecto", "Proyecto"], ...(conVoz ? [["voz", "Voz"]] : []), ["dibujos", "Dibujos"], ["maquina", "Máquina"], ["clips", "Clips"], ["master", "Máster"]];
  $("#vista").innerHTML = `<div class="wrap">
    <div class="row" style="justify-content:space-between"><div><h1>${h(P.titulo)}</h1>
      <p class="sub">${P.formato === "largo" ? "16:9" : "9:16"} · ${h(P.estructura)} · ${P.planos.length} planos · ${mins(e.segundos)} generados ${P.negativos === false ? "· sin negativos" : ""}</p></div>
      <div class="row">${e.corrida && !e.corrida.fin ? `<span class="pill warn"><i class="dot live"></i> instancia ${e.corrida.instancia} · ${usd(e.corrida.acumulado)}</span>` : ""}${e.corrida?.gasto_final != null ? `<span class="pill">GPU gastada ${usd(e.corrida.gasto_final)}</span>` : ""}</div></div>
    <div class="pasos">${pasos.map(([k, n], i) => `<div class="paso ${k === pasoActual ? "on" : ""} ${hechos[k] ? "done" : ""}" onclick="location.hash='#/p/${slug}/${k}'"><b>${hechos[k] ? "✓" : i + 1}</b>${n}</div>`).join("")}</div>
    <div id="paso"></div></div>`;
  await ({proyecto: pasoProyecto, voz: pasoVoz, dibujos: pasoDibujos, maquina: pasoMaquina, clips: pasoClips, master: pasoMaster}[pasoActual] || pasoProyecto)();
});

function lineaDeTiempo() {
  const total = Math.max(1, ...P.planos.map(p => p.hasta));
  return `<div class="tl">${P.tramos.map(t => `<div class="t" style="left:${t.desde / total * 100}%">${h(t.id)}</div>`).join("")}
    ${P.planos.map(p => `<div class="p" title="${h(p.funcion)}" style="left:${p.desde / total * 100}%;width:${Math.max(.5, (p.hasta - p.desde) / total * 100 - .3)}%">${p.id}</div>`).join("")}</div>
    <div class="tiny">${mins(total)} en la línea de tiempo · los tramos punteados son la estructura <code>${h(P.estructura)}</code></div>`;
}

async function pasoProyecto() {
  const av = P.avisos;
  const voz = P.proyecto.voz || [];
  $("#paso").innerHTML = `<div class="grid g2">
    <div class="card" style="grid-column:1/-1"><h3>Línea de tiempo <span class="pill ${av.length ? "warn" : "ok"}">${av.length ? av.length + " aviso(s)" : "sin avisos"}</span></h3>${lineaDeTiempo()}
      ${av.length ? `<div class="pre" style="margin-top:10px;max-height:160px">${av.map(h).join("\n")}</div>` : ""}</div>
    <div class="card"><h3>Planos</h3><table><tr><th>id</th><th>tipo</th><th>tramo</th><th class="num">genera</th><th class="num">en línea</th><th>función</th></tr>
      ${P.planos.map(p => `<tr><td class="mono">${p.id}${p.clip_de ? ` <span class="tiny">= ${p.clip_de}</span>` : ""}</td><td>${p.tipo}</td><td class="tiny">${h(p.tramo || "")}</td><td class="num">${p.segundos.toFixed(2)}</td><td class="num">${p.desde.toFixed(1)}–${p.hasta.toFixed(1)}</td><td class="tiny">${h(p.funcion)}</td></tr>`).join("")}</table>
      ${voz.length ? `<h3 style="margin-top:18px">Voz en off</h3>${voz.map(v => `<div class="muted" style="margin-bottom:6px"><span class="mono tiny">${h(v.plano || "")}</span> ${h(v.texto)}</div>`).join("")}` : ""}</div>
    <div class="card"><h3>proyecto.json <span class="pill">editable</span></h3>
      <textarea id="pj" class="json" style="min-height:420px">${h(JSON.stringify(P.proyecto, null, 2))}</textarea>
      <div class="row" style="margin-top:10px"><button class="btn p" onclick="guardarProyecto()">Guardar y reconstruir</button><span class="tiny">Se valida al guardar. Cero avisos antes de dibujar.</span></div>
      <div id="err" class="tiny" style="color:var(--bad);margin-top:8px"></div></div></div>`;
}
async function guardarProyecto() {
  let pj; try { pj = JSON.parse($("#pj").value); } catch (e) { $("#err").textContent = "JSON inválido: " + e.message; return; }
  try { await api(`/proyectos/${P.slug}`, {method: "PUT", body: {proyecto: pj}}); await api(`/proyectos/${P.slug}/construir`, {method: "POST"}); toast("construido"); navegar(); }
  catch (e) { $("#err").textContent = e.message; }
}

/* ── voz ── */
async function pasoVoz() {
  const v = await api(`/proyectos/${P.slug}/voz`);
  const fuera = v.lineas.filter(l => l.entra_en_voz === false).length;
  const conTomas = v.lineas.filter(l => l.tomas.length).length;
  $("#paso").innerHTML = `<div class="card"><h3>Voz en off <span class="pill ${fuera ? "warn" : "ok"}">${fuera ? fuera + " línea(s) no entran" : "todas entran"}</span></h3>
    <p class="muted">La densidad se mide contra la voz elegida, no contra la teórica. Si una línea no entra, se acorta el texto en el paso Proyecto; nunca se estira el audio. ${v.sin_voz.length ? `<b style="color:var(--bad)">Sin voz asignada: ${v.sin_voz.join(", ")}</b>` : ""}</p>
    <div class="row" style="margin-bottom:12px"><button class="btn p" onclick="generarVoz()">${conTomas ? "Volver a sintetizar lo que cambió" : "Sintetizar con ElevenLabs"}</button><span class="tiny">gasta créditos; las tomas se cachean por texto</span></div>
    <table><tr><th>id</th><th>texto</th><th class="num">ventana</th><th class="num">carac.</th><th class="num">cps</th><th>voz</th><th>toma</th></tr>
    ${v.lineas.map(l => `<tr class="${l.entra_en_voz === false ? "noapta" : ""}"><td class="mono">${l.id}</td><td>${h(l.texto)}</td><td class="num">${l.ventana.toFixed(1)} s</td>
      <td class="num">${l.caracteres}${l.max_caracteres ? ` <span class="tiny">/ ${l.max_caracteres}</span>` : ""}</td>
      <td class="num"><b style="color:${l.entra_en_voz === false ? "var(--bad)" : "var(--ok)"}">${l.cps}</b>${l.cps_voz ? ` <span class="tiny">/ ${l.cps_voz}</span>` : ""}</td>
      <td class="tiny">${h(l.voz_nombre || l.voz_id || "—")}</td>
      <td>${l.tomas.length ? l.tomas.map(tm => `<div class="row" style="gap:6px"><audio controls preload="none" src="${tm.url}" style="height:28px;width:200px"></audio><span class="tiny">${tm.dur ?? "?"} s · ${tm.factor ?? "?"}×</span></div>`).join("") : `<span class="tiny">sin toma</span>`}</td></tr>`).join("")}</table></div>`;
}
async function generarVoz() {
  try { const d = await api(`/proyectos/${P.slug}/voz/generar`, {method: "POST"}); seguirTarea(d.tarea, () => navegar()); toast("sintetizando…"); }
  catch (e) { toast(e.message, true); }
}

/* ── dibujos ── */
async function pasoDibujos() {
  const as = await api(`/proyectos/${P.slug}/assets`);
  const faltan = as.filter(a => !a.existe).length, barras = as.filter(a => a.con_barras).length;
  const vertical = P.formato === "short";
  $("#paso").innerHTML = `<div class="card" style="margin-bottom:14px"><h3>Dibujos ${as.length - faltan}/${as.length}
      <span class="pill ${faltan ? "warn" : barras ? "bad" : "ok"}">${faltan ? faltan + " faltan" : barras ? barras + " con barras" : "todos listos"}</span></h3>
    <div class="row"><select id="motor" style="max-width:230px"><option value="openai">OpenAI / GPT (~$0,25)</option><option value="nanobanana">nano banana (~$0,04, sin créditos hoy)</option></select>
      <button class="btn p" onclick="dibujar([])">${faltan ? "Dibujar los que faltan" : "Dibujar (nada nuevo)"}</button>
      <button class="btn" onclick="rehacerMarcados()">Rehacer los marcados</button>
      <button class="btn" ${faltan ? "disabled" : ""} onclick="empaquetar()">Empaquetar ZIP ${P.estado.zip ? `(${P.estado.zip_mb} MB, ya existe)` : ""}</button>
      <span class="tiny">se revisan TODOS antes de empaquetar · el detector marca letterbox</span></div></div>
    <div class="thumbs">${as.map(a => `<div class="th ${vertical && a.tipo === "plano" ? "v" : ""} ${a.existe ? "" : "falta"}">
      <img src="${a.existe ? a.url : ""}" onclick="${a.existe ? `lightbox('${a.url}')` : ""}" alt="">
      <div class="c"><input type="checkbox" class="rh" value="${a.id}" title="marcar para rehacer"><b>${a.id}</b>${a.plano ? `<span>${a.plano}</span>` : `<span>${a.tipo}</span>`}
        ${a.con_barras ? `<span class="pill bad">barras</span>` : ""}</div>
      ${a.funcion ? `<div class="tiny" style="padding:0 10px 8px">${h(a.funcion)}</div>` : ""}</div>`).join("")}</div>`;
}
async function dibujar(rehacer) {
  try {
    const d = await api(`/proyectos/${P.slug}/frames`, {method: "POST", body: {madre: true, motor: $("#motor")?.value || "openai", rehacer}});
    seguirTarea(d.tarea, () => navegar()); toast("dibujando…");
  } catch (e) { toast(e.message, true); }
}
function rehacerMarcados() {
  const ids = [...document.querySelectorAll(".rh:checked")].map(x => x.value);
  if (!ids.length) return toast("marcá al menos uno", true);
  confirmar("Rehacer dibujos", `Se apartan y se vuelven a generar: <b>${ids.join(", ")}</b> (~$${(ids.length * .04).toFixed(2)}).`, "Rehacer", () => dibujar(ids));
}
async function empaquetar() {
  try { const d = await api(`/proyectos/${P.slug}/empaquetar`, {method: "POST"}); seguirTarea(d.tarea, () => { toast("ZIP listo"); location.hash = `#/p/${P.slug}/maquina`; }); }
  catch (e) { toast(e.message, true); }
}

/* ── la máquina: ofertas, alquiler, taxímetro ── */
let seguimiento = null;
async function pasoMaquina() {
  const e = P.estado;
  let m = null; try { m = await api("/maquina"); } catch {}
  const lista = m && m.fase === "lista";
  const ocupada = lista && m.generando && m.generando.slug !== P.slug && m.generando.total && m.generando.hechos < m.generando.total;
  $("#paso").innerHTML = `<div class="grid g2">
    <div class="card" style="grid-column:1/-1"><h3>La máquina encendida <span class="pill ${lista ? "ok" : m && m.fase !== "apagada" ? "warn" : ""}">${m ? (FASES[m.fase] || [m.fase])[0] : "?"}${m?.instancia ? " · " + m.instancia : ""}</span>${m?.acumulado ? `<span class="pill">gastado ${usd(m.acumulado)}</span>` : ""}</h3>
      ${lista ? `<div class="row"><button class="btn p" ${e.zip && !ocupada ? "" : "disabled"} onclick="generarEnMaquina()">Generar este proyecto en la máquina</button>
        <span class="tiny">${!e.zip ? "falta empaquetar" : ocupada ? `ocupada con ${h(m.generando.slug)} (${m.generando.hechos}/${m.generando.total})` : "H3 ya está instalado: sólo se paga la generación (~" + Math.round(e.segundos * 0.77) + " min de GPU, ~" + Math.ceil(e.segundos * 0.77 / 4) + " de pared)"}</span></div>`
        : `<div class="muted">No hay máquina lista. Encendela desde el <a href="#/">inicio</a> (una sola instalación para todos los proyectos), o alquilá una sólo para este proyecto con la tabla de abajo.</div>`}</div>
    <div class="card" style="grid-column:1/-1" id="inst"></div>
    <div class="card" style="grid-column:1/-1"><h3>Ofertas de 4× RTX 5090 <span class="pill" id="of-n">consultando…</span></h3>
      <div class="row" style="margin-bottom:10px"><label class="tiny"><input type="checkbox" id="todas" onchange="cargarOfertas()"> mostrar también las no aptas (desverificadas, lentas, caras)</label>
        <button class="btn s" onclick="cargarOfertas()">Actualizar</button>
        <span class="tiny">${e.zip ? `ZIP listo (${e.zip_mb} MB)` : "falta empaquetar: el alquiler queda deshabilitado"} · estimado con la curva medida de la 5090 más 10 min de overhead</span></div>
      <div id="ofertas"></div></div></div>`;
  await pintarInstancia();
  await cargarOfertas();
}
async function cargarOfertas() {
  const box = $("#ofertas"); box.innerHTML = `<div class="muted">Consultando Vast…</div>`;
  try {
    const todas = $("#todas")?.checked ? "&todas=true" : "";
    const d = await api(`/vast/ofertas?proyecto=${P.slug}${todas}`);
    const of = d.ofertas; $("#of-n").textContent = `${of.filter(o => o.apta).length} aptas de ${of.length} · ${fmtHora(d.consultado)}`;
    if (!of.length) { box.innerHTML = `<div class="muted">No hay ninguna 4×5090 permitida ahora. Lo barato es esperar: la oferta sube y baja durante el día.</div>`; return; }
    box.innerHTML = `<table><tr><th>id</th><th>dónde</th><th class="num">$/h</th><th class="num">Mbps</th><th class="num">fiab.</th><th>verif.</th><th class="num">estimado</th><th></th></tr>
      ${of.map(o => `<tr class="${o.apta ? "apta" : "noapta"}"><td class="mono">${o.id}</td><td>${h(o.geo)}${o.datacenter ? ' <span class="tiny">DC</span>' : ""}</td>
        <td class="num">${o.dph.toFixed(3)}</td><td class="num">${o.inet}</td><td class="num">${o.fiabilidad.toFixed(3)}</td><td class="tiny">${h(o.verificacion)}</td>
        <td class="num">${o.estimado ? `<b>${usd(o.estimado.con_overhead)}</b> <span class="tiny">${o.estimado.minutos} min</span>` : "—"}</td>
        <td>${o.apta ? `<button class="btn p s" ${P.estado.zip ? "" : "disabled"} onclick='alquilar(${JSON.stringify(o)})'>Alquilar</button>` : `<span class="tiny">${o.motivos.join(" · ")}</span>`}</td></tr>`).join("")}</table>`;
  } catch (e) { box.innerHTML = `<div class="pre">${h(e.message)}</div>`; }
}
function alquilar(o) {
  confirmar("Alquilar y generar",
    `<b>${o.gpus}× ${h(o.gpu)}</b> en ${h(o.geo)} a <b>$${o.dph.toFixed(3)}/h</b>, ${o.inet} Mbps, fiabilidad ${o.fiabilidad.toFixed(3)}.<br>
     Estimado del trabajo: <b>${usd(o.estimado?.con_overhead)}</b> (${o.estimado?.minutos} min). Empieza a cobrar de inmediato; el taxímetro corre acá.`,
    "Sí, alquilar", async () => {
      try {
        const d = await api("/vast/alquilar", {method: "POST", body: {slug: P.slug, id: o.id, confirmar: true}});
        seguirTarea(d.tarea, () => navegar()); toast("alquilando… (arranque 2 a 8 min)");
        setTimeout(pintarInstancia, 15000);
      } catch (e) { toast(e.message, true); }
    });
}
async function pintarInstancia() {
  const box = $("#inst"); if (!box) return;
  const c = P.estado.corrida;
  if (!c || c.fin) {
    let vivas = []; try { vivas = (await api("/vast/instancias")).instancias; } catch {}
    box.innerHTML = `<h3>Máquina <span class="pill ${vivas.length ? "warn" : "ok"}">${vivas.length ? vivas.length + " viva(s) en la cuenta" : "nada cobrando"}</span></h3>
      <div class="muted">${c?.gasto_final != null ? `La última corrida de este proyecto costó <b>${usd(c.gasto_final)}</b> en ${c.minutos} min.` : "Este proyecto todavía no alquiló."}
      ${vivas.length ? `<div style="margin-top:8px">${vivas.map(i => `<span class="pill warn">${i.id} · ${h(i.gpu)} · $${i.dph}/h · ${h(i.estado)}</span> <button class="btn d s" onclick="destruir(${i.id})">destruir</button>`).join(" ")}</div>` : ""}</div>`;
    return;
  }
  let s; try { s = await api(`/vast/seguir/${P.slug}/${c.instancia}`); } catch (e) { box.innerHTML = `<div class="pre">${h(e.message)}</div>`; return; }
  const pct = s.total ? Math.round(s.hechos.length / s.total * 100) : 0;
  const listo = s.total && s.hechos.length === s.total;
  box.innerHTML = `<h3>Instancia ${c.instancia} <span class="pill warn"><i class="dot live"></i> ${h(s.estado || "?")}</span></h3>
    <div class="kpis"><div class="kpi"><div class="l">precio</div><div class="v">$${(s.dph || c.dph).toFixed(3)}<span class="tiny">/h</span></div></div>
      <div class="kpi"><div class="l">viva hace</div><div class="v">${c.minutos} min</div></div>
      <div class="kpi"><div class="l">gastado</div><div class="v" style="color:var(--ac)">${usd(c.acumulado)}</div></div>
      <div class="kpi"><div class="l">estimado</div><div class="v">${usd(c.estimado)}</div></div>
      <div class="kpi"><div class="l">clips</div><div class="v">${s.hechos.length}/${s.total}</div></div></div>
    <div class="bar" style="margin:12px 0 6px"><i style="width:${pct}%"></i></div>
    <div class="tiny">${listo ? "todos los clips están en la máquina" : "faltan: " + s.faltan.join(" ")}</div>
    <div class="row" style="margin-top:12px"><button class="btn ${listo ? "p" : ""}" onclick="bajar()">Bajar clips${listo ? "" : " (parcial)"}</button>
      ${c.maquina_compartida ? `<button class="btn d" onclick="apagarMaquina()">Apagar la máquina</button><span class="tiny">es la máquina compartida: apagarla corta también los otros proyectos</span>` : `<button class="btn d" onclick="destruir(${c.instancia})">Destruir instancia</button>`}
      <button class="btn s" onclick="pintarInstancia()">actualizar</button><code class="tiny">${h(s.ssh || "")}</code></div>
    <details style="margin-top:10px"><summary class="tiny">log de la máquina</summary><div class="pre">${h(s.logs)}</div></details>`;
  clearTimeout(seguimiento); seguimiento = setTimeout(() => { if (location.hash.includes("/maquina")) pintarInstancia(); }, 20000);
}
async function generarEnMaquina() {
  try { const d = await api("/maquina/generar", {method: "POST", body: {slug: P.slug}}); seguirTarea(d.tarea, () => navegar()); toast("subiendo el proyecto a la máquina…"); }
  catch (e) { toast(e.message, true); }
}
async function bajar() {
  const c = P.estado.corrida;
  try { const d = await api("/vast/bajar", {method: "POST", body: {slug: P.slug, id: c.instancia}}); seguirTarea(d.tarea, () => { location.hash = `#/p/${P.slug}/clips`; }); toast("bajando…"); }
  catch (e) { toast(e.message, true); }
}
function destruir(iid) {
  confirmar("Destruir la instancia " + iid, "Deja de cobrar y se pierde todo lo que haya en la máquina. <b>Bajá los clips antes.</b> No hay vuelta atrás.", "Destruir", async () => {
    try { const d = await api("/vast/destruir", {method: "POST", body: {id: iid, confirmar: true}}); toast(`destruida · gasto final ${usd(d.gasto_final)}`); estadoVast(); navegar(); }
    catch (e) { toast(e.message, true); }
  }, true);
}

/* ── clips: QC con tiras ── */
async function pasoClips() {
  $("#paso").innerHTML = `<div class="card"><h3>Clips <span class="pill">${P.estado.clips.hechos}/${P.estado.clips.esperados} bajados</span></h3>
    <div class="row"><button class="btn p" onclick="hacerTiras()">Armar tiras de 10 cuadros</button><span class="tiny">2 cuadros por segundo de cada clip: gente inventada, luz que deriva, texto quemado. Mirá los 10.</span></div>
    <div id="clips" style="margin-top:14px"></div></div>`;
  await pintarClips();
}
async function pintarClips() {
  const cs = await api(`/proyectos/${P.slug}/clips`);
  $("#clips").innerHTML = cs.map(c => `<div style="margin-bottom:16px"><div class="row" style="margin-bottom:6px"><b class="mono">${c.id}</b><span class="tiny">${h(c.funcion)}</span>
    <span class="pill ${c.existe ? "ok" : "bad"}" style="margin-left:auto">${c.existe ? c.mb + " MB" : "falta"}</span></div>
    ${c.tira ? `<img class="tira" src="${c.tira}" onclick="lightbox('${c.tira}')">` : `<div class="tiny">${c.existe ? "sin tira todavía" : ""}</div>`}</div>`).join("") || `<div class="muted">No hay clips bajados.</div>`;
}
async function hacerTiras() { toast("armando tiras…"); try { await api(`/proyectos/${P.slug}/tiras`, {method: "POST"}); await pintarClips(); } catch (e) { toast(e.message, true); } }

/* ── máster ── */
async function pasoMaster() {
  const e = P.estado; const loop = String(P.estructura).startsWith("loop");
  $("#paso").innerHTML = `<div class="grid g2">
    <div class="card"><h3>Máster</h3><p class="muted">${loop ? "Loop: 5,0 s de cada clip, 1080p, −14 LUFS y el «×3» para mirar el empalme. Para el video con música, usá la sección Music video." : "Corte por <code>usa</code>, tres capas con ducking, −14 LUFS y subtítulos quemados."}</p>
      ${loop ? `<div class="row"><input id="repite" type="number" min="0" placeholder="repetir N veces (opcional)" style="max-width:220px">${P.planos.length === 1 ? `<select id="cierre" style="max-width:260px"><option value="fundido">cierre: fundido de 1 s (lluvia, vapor, todo)</option><option value="pingpong">cierre: ping-pong (fuego, agua, luz)</option><option value="corte">cierre: corte seco</option></select>` : ""}</div>` : ""}
      <div class="row" style="margin-top:12px"><button class="btn p" ${e.clips.hechos ? "" : "disabled"} onclick="masterizar()">Generar máster</button>${loop ? `<a class="btn" href="#/musica/${P.slug}">Ir a la música</a>` : ""}</div></div>
    <div class="card"><h3>Archivos</h3>${e.masters.length ? e.masters.map(m => `<div class="row" style="margin-bottom:8px"><a href="/api/proyectos/${P.slug}/archivo/${encodeURIComponent(m)}" target="_blank">${h(m)}</a></div>`).join("") : `<div class="muted">Todavía no hay máster.</div>`}
      ${e.masters.length ? `<video controls style="width:100%;border-radius:10px;margin-top:8px" src="/api/proyectos/${P.slug}/archivo/${encodeURIComponent(e.masters[0])}"></video>` : ""}</div></div>`;
}
async function masterizar() {
  const body = {repite: Number($("#repite")?.value || 0), cierre: $("#cierre")?.value || "fundido"};
  try { const d = await api(`/proyectos/${P.slug}/master`, {method: "POST", body}); seguirTarea(d.tarea, () => navegar()); toast("masterizando…"); }
  catch (e) { toast(e.message, true); }
}

/* ─────────────────────────────────────────────── máquinas (global) */
ruta("/vast", async () => {
  $("#vista").innerHTML = `<div class="wrap"><h1>Máquinas</h1><p class="sub">Lo que hay alquilado ahora y lo que se puede alquilar. Sólo 4× RTX 5090 verificadas, fuera de EE.UU., UE, Reino Unido y Corea (licencia de H3).</p>
    <div class="card" id="vivas" style="margin-bottom:14px"><h3>Instancias vivas</h3><div class="muted">consultando…</div></div>
    <div class="card"><h3>Ofertas ahora <span class="pill" id="of-n">…</span></h3><div class="row" style="margin-bottom:10px"><label class="tiny"><input type="checkbox" id="todas" onchange="ofertasGlobal()"> mostrar las no aptas</label><button class="btn s" onclick="ofertasGlobal()">Actualizar</button></div><div id="ofertas"></div></div></div>`;
  vivasGlobal(); ofertasGlobal();
});
async function vivasGlobal() {
  const box = $("#vivas");
  try {
    const d = await api("/vast/instancias");
    box.innerHTML = `<h3>Instancias vivas <span class="pill ${d.instancias.length ? "warn" : "ok"}">${d.instancias.length || "ninguna"}</span></h3>` +
      (d.instancias.length ? `<table><tr><th>id</th><th>máquina</th><th>estado</th><th class="num">$/h</th><th>proyecto</th><th class="num">viva</th><th class="num">gastado</th><th></th></tr>
        ${d.instancias.map(i => `<tr><td class="mono">${i.id}</td><td>${i.gpus}× ${h(i.gpu)} · ${h(i.geo || "")}</td><td>${h(i.estado)}</td><td class="num">${i.dph}</td>
          <td>${i.corrida ? `<a href="#/p/${i.corrida.slug}/maquina">${i.corrida.slug}</a>` : "—"}</td><td class="num">${i.corrida ? i.corrida.minutos + " min" : "—"}</td><td class="num">${i.corrida ? usd(i.corrida.acumulado) : "—"}</td>
          <td><button class="btn d s" onclick="destruir(${i.id})">destruir</button></td></tr>`).join("")}</table>` : `<div class="muted">No tenés instancias. Bien: no estás pagando nada.</div>`);
  } catch (e) { box.innerHTML = `<div class="pre">${h(e.message)}</div>`; }
}
async function ofertasGlobal() {
  const box = $("#ofertas"); box.innerHTML = `<div class="muted">Consultando Vast…</div>`;
  try {
    const d = await api(`/vast/ofertas${$("#todas")?.checked ? "?todas=true" : ""}`);
    $("#of-n").textContent = `${d.ofertas.filter(o => o.apta).length} aptas de ${d.ofertas.length} · ${fmtHora(d.consultado)}`;
    box.innerHTML = d.ofertas.length ? `<table><tr><th>id</th><th>dónde</th><th class="num">$/h</th><th class="num">Mbps</th><th class="num">fiab.</th><th>verif.</th><th>motivos</th></tr>
      ${d.ofertas.map(o => `<tr class="${o.apta ? "apta" : "noapta"}"><td class="mono">${o.id}</td><td>${h(o.geo)}</td><td class="num">${o.dph.toFixed(3)}</td><td class="num">${o.inet}</td><td class="num">${o.fiabilidad.toFixed(3)}</td><td class="tiny">${h(o.verificacion)}</td><td class="tiny">${o.apta ? "apta" : o.motivos.join(" · ")}</td></tr>`).join("")}</table>
      <div class="tiny" style="margin-top:8px">Para alquilar, entrá al proyecto empaquetado: ahí la tabla trae el costo estimado del trabajo.</div>` : `<div class="muted">Ninguna 4×5090 permitida ahora.</div>`;
  } catch (e) { box.innerHTML = `<div class="pre">${h(e.message)}</div>`; }
}

/* ─────────────────────────────────────────────── music video */
ruta("/musica", async ([slug]) => {
  const ps = (await api("/proyectos")).filter(p => String(p.estructura).startsWith("loop"));
  const sel = slug || ps[0]?.slug;
  let pistas = [];
  const otros = ps.filter(p => p.slug !== sel && (p.estado?.masters || []).some(m => / - loop\.mp4$/.test(m)));
  if (sel) { try { pistas = await api(`/proyectos/${sel}/musica`); } catch {} }
  const p = ps.find(x => x.slug === sel);
  $("#vista").innerHTML = `<div class="wrap"><h1>Music video</h1>
    <p class="sub">Un escenario que se mira de fondo y se repite lo que dure la música. Elegís el tipo de música y la app la compone con ElevenLabs Music; el loop se hace con el mismo flujo de siempre; el video final dura lo que dura la pista.</p>
    <div class="row" style="margin-bottom:14px"><a class="btn p" href="#/nuevo/loop">＋ Nuevo loop (describís la escena)</a>
      ${ps.length ? `<select id="sel-loop" onchange="location.hash='#/musica/'+this.value" style="max-width:320px">${ps.map(x => `<option value="${x.slug}" ${x.slug === sel ? "selected" : ""}>${h(x.titulo)}</option>`).join("")}</select>` : ""}</div>
    ${p ? `<div class="grid g2">
      <div class="card"><h3>1 · La música para «${h(p.titulo)}»</h3>
        <textarea id="tipo" style="min-height:90px" placeholder="Qué música: «lo-fi hip hop lento para estudiar, piano suave y vinilo, sin batería marcada, melancólico pero cálido»"></textarea>
        <div class="row" style="margin-top:8px"><input id="dur" type="number" value="90" min="30" max="300" style="max-width:120px"><span class="tiny">segundos (30 a 300). Para publicar largo, el loop se repite sobre la pista.</span></div>
        <div class="row" style="margin-top:10px"><button class="btn p" onclick="componer('${sel}')">Componer</button><span class="tiny">créditos de ElevenLabs</span></div>
        <div style="margin-top:14px">${pistas.length ? pistas.map(t => `<div class="row" style="margin-bottom:8px"><audio controls preload="none" src="${t.url}" style="height:30px;flex:1"></audio><span class="tiny">${h(t.archivo)} · ${t.dur ?? "?"} s</span></div>`).join("") : `<div class="tiny">Todavía no hay pistas en este proyecto.</div>`}</div></div>
      <div class="card"><h3>2 · El video final <span class="pill ${p.estado.masters.length ? "ok" : "warn"}">${p.estado.clips.hechos}/${p.estado.clips.esperados} clips</span></h3>
        <p class="muted">La pista manda la duración: el loop se repite hasta cubrirla y se corta a su largo. Si marcás otros loops, se alternan para que no se vea el mismo doce veces.</p>
        <select id="pista">${pistas.map(t => `<option value="${h(t.ruta)}">${h(t.archivo)} (${t.dur ?? "?"} s)</option>`).join("")}${pistas.length ? "" : `<option value="">(primero componé una pista)</option>`}</select>
        ${otros.length ? `<div class="tiny" style="margin:10px 0 4px">Alternar con:</div>${otros.map(o => `<label class="tiny" style="display:block"><input type="checkbox" class="otro" value="${o.slug}"> ${h(o.titulo)}</label>`).join("")}` : ""}
        <div class="row" style="margin-top:12px"><button class="btn p" ${pistas.length && p.estado.clips.hechos ? "" : "disabled"} onclick="masterMusica('${sel}')">Generar video con la pista</button>
          <a class="btn" href="#/p/${sel}">Abrir el loop (dibujos, máquina, clips)</a></div>
        <div style="margin-top:12px">${p.estado.masters.map(m => `<div><a href="/api/proyectos/${sel}/archivo/${encodeURIComponent(m)}" target="_blank">${h(m)}</a></div>`).join("")}</div></div>
    </div>` : `<div class="card"><div class="muted">Todavía no hay loops. Empezá por «Nuevo loop».</div></div>`}
    <h3 style="margin:26px 0 10px">Loops</h3><div class="grid g3">${ps.map(tarjetaProyecto).join("")}</div></div>`;
});
async function componer(slug) {
  const body = {slug, tipo: $("#tipo").value, duracion: Number($("#dur").value || 90)};
  try { const d = await api("/musica/componer", {method: "POST", body}); seguirTarea(d.tarea, () => navegar()); toast("componiendo…"); }
  catch (e) { toast(e.message, true); }
}
async function masterMusica(slug) {
  const otros = [...document.querySelectorAll(".otro:checked")].map(x => x.value);
  try { const d = await api(`/proyectos/${slug}/master`, {method: "POST", body: {musica: $("#pista").value, largo_de_pista: true, otros_loops: otros, cierre: "fundido"}}); seguirTarea(d.tarea, () => navegar()); toast("armando el video con la pista…"); }
  catch (e) { toast(e.message, true); }
}

/* ─────────────────────────────────────────────── fondo 3D */
(function fondo() {
  if (!window.THREE) return;
  const canvas = $("#bg3d");
  const renderer = new THREE.WebGLRenderer({canvas, antialias: true, alpha: true});
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  const scene = new THREE.Scene();
  const cam = new THREE.PerspectiveCamera(55, 1, .1, 100); cam.position.set(0, 0, 9);
  const grupo = new THREE.Group(); scene.add(grupo);
  const geo = new THREE.PlaneGeometry(1.2, .68);
  for (let i = 0; i < 48; i++) {
    const t = i / 48 * Math.PI * 2, r = 4.2 + Math.sin(i * 1.7) * .5;
    const m = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({color: i % 5 ? 0x2a3350 : 0xffb454, transparent: true, opacity: i % 5 ? .55 : .8, side: THREE.DoubleSide, wireframe: i % 3 === 0}));
    m.position.set(Math.cos(t) * r, Math.sin(t * 2) * .9 + Math.sin(i) * .3, Math.sin(t) * r);
    m.lookAt(0, m.position.y, 0); grupo.add(m);
  }
  const n = 900, pos = new Float32Array(n * 3);
  for (let i = 0; i < n * 3; i++) pos[i] = (Math.random() - .5) * 26;
  const puntos = new THREE.Points(new THREE.BufferGeometry().setAttribute("position", new THREE.BufferAttribute(pos, 3)),
    new THREE.PointsMaterial({color: 0x6aa9ff, size: .04, transparent: true, opacity: .6}));
  scene.add(puntos);
  let mx = 0, my = 0;
  addEventListener("pointermove", e => { mx = (e.clientX / innerWidth - .5); my = (e.clientY / innerHeight - .5); });
  function size() { const w = innerWidth, hh = innerHeight; renderer.setSize(w, hh, false); cam.aspect = w / hh; cam.updateProjectionMatrix(); }
  addEventListener("resize", size); size();
  const t0 = performance.now();
  (function loop() {
    const t = (performance.now() - t0) / 1000;
    grupo.rotation.y = t * .08; grupo.rotation.x = Math.sin(t * .15) * .12 + my * .2;
    puntos.rotation.y = -t * .02; cam.position.x += (mx * 1.2 - cam.position.x) * .03;
    cam.lookAt(0, 0, 0);
    canvas.style.opacity = document.body.classList.contains("en-portada") ? .9 : .28;
    renderer.render(scene, cam); requestAnimationFrame(loop);
  })();
})();

estadoVast();
navegar();
