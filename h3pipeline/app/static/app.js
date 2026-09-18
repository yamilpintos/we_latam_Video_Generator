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
  if (r.status === 401) { location.href = "/login?next=" + encodeURIComponent(location.pathname + location.hash); throw new Error("sesión vencida"); }
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
        <p>Tu guion, en voz en off con subtítulos. Tres clips para una muestra de 15 s; doce para un minuto. Suelto, o una <b>serie</b> con personajes fijos que GPT escribe por tandas.</p><span class="n">${n(p => p.formato === "short" && !esLoop(p) && !esRecap(p))} proyectos · suelto o en serie</span></div>
      <div class="puerta" onclick="location.hash='#/nuevo/largo'"><span class="k">VERTICAL · 3 A 8 MIN</span><h2>Largo</h2>
        <p>Recap con voz continua. Primero el audio, medido contra la voz elegida; después los planos que lo sirven. Suelto o en <b>serie</b>.</p><span class="n">${n(esRecap)} proyectos · suelto o en serie</span></div>
      <div class="puerta" onclick="location.hash='#/musica'"><span class="k">16:9 · LOOP</span><h2>Music video</h2>
        <p>Decís qué música y qué escena. La app compone la pista, hace el loop y el video dura lo que dure la música. O una <b>serie</b>: otra pista y otra escena por capítulo.</p><span class="n">${n(esLoop)} loops · suelto o en serie</span></div>
      <div class="puerta" onclick="location.hash='#/libre'"><span class="k">CHAT · SIN ESTRUCTURA</span><h2>Libre</h2>
        <p>Escribís un prompt, ves la imagen, describís el movimiento y sale un clip de MiniMax. Para probar ideas antes de un guion.</p><span class="n">como un playground</span></div>
      <div class="puerta" onclick="location.hash='#/editar'"><span class="k">VIDEO → VIDEO · 2 A 15 S</span><h2>Editar</h2>
        <p>Subís un video y decís qué cambiar: la ropa, el fondo, un objeto, una frase. H3 lo rehace conservando encuadre y movimiento.</p><span class="n">referencia completa</span></div>
      <div class="puerta" onclick="location.hash='#/remaster'"><span class="k">SD → 4K · PELÍCULAS</span><h2>Remasterizar</h2>
        <p>Un capítulo o una película en definición estándar sale en 4K con FlashVSR. Analiza el origen gratis, te dice el costo y alquila una A100 aparte.</p><span class="n">otra máquina · 1× A100 80 GB</span></div>
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
    ${viva && m.progreso ? `<div class="row" style="justify-content:space-between;margin-bottom:4px"><span class="tiny"><b>${h(m.progreso.etapa)}</b> · ${h(m.progreso.detalle || "")}</span><span class="tiny">${m.progreso.pct} %</span></div>
      <div class="bar" style="height:12px"><i style="width:${m.progreso.pct}%"></i></div>
      <div class="tiny" style="margin-top:6px;display:flex;gap:14px"><span style="color:${m.progreso.pct >= 2 ? "var(--ok)" : ""}">① buscar</span><span style="color:${m.progreso.pct >= 5 ? "var(--ok)" : ""}">② arrancar</span><span style="color:${m.progreso.pct >= 15 ? "var(--ok)" : ""}">③ instalar H3 (59 GB)</span><span style="color:${m.progreso.pct >= 100 ? "var(--ok)" : ""}">④ lista</span></div>
      ${m.fase === "instalando" && inst?.ultimo ? `<div class="tiny mono" style="margin-top:6px;white-space:pre-wrap;opacity:.7">${h(inst.ultimo)}</div>` : ""}
      ${m.fase === "buscando" ? `<div class="tiny" style="margin-top:6px">No hay ninguna 4×5090 verificada ahora. Consulta cada minuto y alquila sola cuando aparezca. Podés cerrar la página.</div>` : ""}` : ""}
    ${m.fase === "fallo" && m.error ? `<div class="tiny" style="margin-bottom:8px;color:var(--bad)"><b>Por qué falló:</b> ${h(m.error)} · <a href="/api/maquina/diagnostico" target="_blank">diagnóstico SSH de este servidor</a></div>` : ""}
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
  const titulo = esLoop ? "La escena del music video" : f === "largo" ? "Nuevo largo" : "Nuevo short";
  const sub = esLoop ? "Paso 2 de 4. Describí el lugar que se va a mirar mientras suena la música: un lugar, una hora, una luz, y qué se mueve despacio. Se repite en loop lo que dure la pista."
    : "Pegá tu guion. La app lo traduce a planos siguiendo la estructura, lo valida y te lo muestra. El guion no se reescribe: se ilustra.";
  const ph = esLoop ? "Un jardín japonés de noche bajo lluvia fina: estanque negro con koi, un farol de piedra con vela, farolitos rojos, musgo, un arce…"
    : "Soy Tomás, buzo de mantenimiento en la represa. Bajé a 42 metros a revisar una compuerta que no cerraba…";
  $("#vista").innerHTML = `<div class="wrap"><h1>${titulo}</h1><p class="sub">${sub}</p>
    <div id="series-seccion"></div>
    <div class="grid g2">
      <div class="card" style="grid-column:1/-1"><h3>${esLoop ? "La escena" : "El guion"}</h3>
        ${esLoop ? `<select id="escena" style="margin-bottom:8px"><option value="">Escena propia (escribila abajo)</option>${ESCENAS.map((s, i) => `<option value="${i}">${h(s.n)}</option>`).join("")}</select>` : ""}
        <textarea id="guion" class="json" style="font-family:var(--font);font-size:15px;min-height:240px" placeholder="${ph}"></textarea>
        <div class="tiny" style="margin-top:6px"><span id="nchars">0</span> caracteres${esLoop ? "" : ` · con la voz elegida entran unos <span id="cabe">—</span> caracteres en <span id="durest">—</span> s`}</div></div>
      <div class="card"><h3>${esLoop ? "Título y cuántas tomas" : "Título y formato"}</h3>
        <input id="titulo" placeholder="Título" style="margin-bottom:8px">
        ${esLoop ? `<input type="hidden" id="estructura" value="${estDefault}">` : `<select id="estructura">${ests.map(e => `<option value="${e.nombre}" ${e.nombre === estDefault ? "selected" : ""}>${e.nombre} · ${e.duracion} s${e.retencion ? " · retención " + Math.round(e.retencion * 100) + " %" : ""}</option>`).join("")}</select>`}
        ${esLoop ? `<div><select id="duracion"><option value="5.17" selected>Una sola toma · 1 clip de 5 s (lo más barato y seguro)</option><option value="10.08">Una sola toma · 1 clip de 10 s (riesgo de memoria)</option><option value="15.5">3 tomas del mismo lugar · 3 clips</option><option value="31">6 tomas · 30 s de variedad</option><option value="46.5">9 tomas · 45 s de variedad</option><option value="62">12 tomas · 1 min de variedad</option><option value="93">18 tomas · 1 min 30 de variedad</option></select>
          <div class="tiny" style="margin-top:4px">Una toma: un solo plano que se repite en loop (cerrado con un fundido de la cola sobre la cabeza). Varias tomas: la app corta entre encuadres del mismo lugar, así en 30 minutos de música no se ve siempre lo mismo. Más tomas = más clips = más minutos de GPU.</div></div>` : `<div style="margin-top:8px"><select id="voz"><option value="pablo">Voz: Pablo, argentino (10,5 cps)</option><option value="kate">Voz: Kate (16,7 cps)</option><option value="">Sin voz en off</option></select></div>`}
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
  pintarSeriesSeccion(esLoop ? "musica" : f);
});

/* ─────────────────────────────────────────────── editar: video → video (Ref2VA) */
let editTimer = null;
const DURS_H3 = [[5.167, "5,17 s"], [5.875, "5,88 s"], [6.583, "6,58 s"], [7.292, "7,29 s"], [10.083, "10,08 s"], [12.917, "12,92 s"], [15.083, "15,08 s"]];
ruta("/editar", async () => {
  const d = await api("/editar");
  const lista = d.maquina === "lista";
  $("#vista").innerHTML = `<div class="wrap"><h1>Editar un video <span class="pill ${lista ? "ok" : "warn"}">máquina ${h(d.maquina || "apagada")}</span></h1>
    <p class="sub">Subís un video de 2 a 15 segundos y decís qué cambiar: la ropa, el fondo, un objeto, el clima, una frase que diga. MiniMax H3 lo rehace conservando la persona, el encuadre, el movimiento y los tiempos. Es una reinterpretación fiel, no un filtro: la primera vez conviene un cambio solo y claro.</p>
    <div class="card" style="margin-bottom:14px"><h3>Nuevo video</h3>
      <div class="row"><label class="btn p">subir video<input type="file" id="efile" accept="video/mp4,video/quicktime,video/webm,video/*" hidden></label>
        <select id="eajuste" style="max-width:300px" title="qué hacer si el video no tiene la proporción 16:9 o 9:16"><option value="encajar">entero, con fondo desenfocado a los lados</option><option value="recortar">recortado al cuadro (se pierden bordes)</option></select>
        <span class="tiny">se pasa a 24 fps y al cuadro de H3; si dura más de 15 s se usan los primeros 15</span></div>
      <div id="eerr" class="tiny" style="color:var(--bad);margin-top:6px"></div></div>
    <div id="eturnos"></div></div>`;
  $("#efile").addEventListener("change", async (ev) => {
    const f = ev.target.files[0]; if (!f) return;
    if (f.size > 180 * 1024 * 1024) { $("#eerr").textContent = "el archivo pesa más de 180 MB: recortalo o bajale la resolución antes"; return; }
    toast("subiendo y preparando el video… (10-40 s)");
    const b64 = await new Promise(r => { const fr = new FileReader(); fr.onload = () => r(fr.result); fr.readAsDataURL(f); });
    try { await api("/editar/video", {method: "POST", body: {nombre: f.name, b64, ajuste: $("#eajuste").value}}); toast("video listo"); navegar(); }
    catch (e) { $("#eerr").textContent = e.message; }
  });
  pintarEdiciones(d.turnos, d);
});
function pintarEdiciones(ts, d) {
  const lista = d.maquina === "lista";
  const activos = ts.filter(t => t.estado !== "listo"), hechos = ts.filter(t => t.estado === "listo");
  const dur = s => `${Number(s).toFixed(2).replace(".", ",")} s`;
  const barra = (t, etq) => { const p = t.progreso; return `<div class="row" style="justify-content:space-between"><span class="pill warn"><i class="dot live"></i> ${etq}</span><span class="tiny">${p ? `${Math.floor(p.transcurrido / 60)} min de ~${Math.round(p.estimado / 60)}` : ""}</span></div>
      <div class="bar" style="height:10px;margin-top:8px"><i style="width:${p ? p.pct : 2}%"></i></div>
      <div class="tiny mono" style="margin-top:6px;white-space:pre-wrap;opacity:.75">${p && p.ultimo ? h(p.ultimo) : "esperando la primera señal de la máquina…"}</div>`; };
  const biblioteca = hechos.length ? `<h3 style="margin-top:22px">Ediciones hechas <span class="pill">${hechos.length}</span></h3><div class="grid g3">${hechos.map(t => `<div class="card" style="padding:10px">
      <div class="grid" style="grid-template-columns:1fr 1fr;gap:6px"><div><div class="tiny">original</div><video controls preload="metadata" style="width:100%;border-radius:6px;background:#000" src="/api/editar/archivo/fuentes/${t.fuente.split("/")[1]}"></video></div>
        <div><div class="tiny">editado</div><video controls preload="metadata" style="width:100%;border-radius:6px;background:#000" src="/api/editar/archivo/clips/${t.clip.split("/")[1]}"></video></div></div>
      <div class="tiny" style="margin-top:6px">${new Date(t.creado * 1000).toLocaleString("es-AR")} · ${t.aspecto} · ${dur(t.segundos)}</div>
      <div class="muted" style="margin-top:4px">${h(t.cambio || "")}</div>
      <details style="margin-top:4px"><summary class="tiny" style="cursor:pointer">prompt</summary><div class="tiny mono" style="white-space:pre-wrap;opacity:.8;max-height:220px;overflow:auto">${h(t.prompt_video || "")}</div></details>
      <div class="row" style="margin-top:8px"><a class="btn s" href="/api/editar/archivo/clips/${t.clip.split("/")[1]}" download>descargar</a></div></div>`).join("")}</div>` : "";
  $("#eturnos").innerHTML = (activos.map(t => `<div class="card" style="margin-bottom:12px"><div class="grid g2">
    <div><div class="tiny" style="margin-bottom:6px">${new Date(t.creado * 1000).toLocaleString("es-AR")} · ${h(t.nombre || "")} · ${t.aspecto} · ${dur(t.segundos_fuente)} · ${t.tiene_audio ? "con audio" : "sin audio"}${t.original ? ` · original ${t.original.w}×${t.original.h}, ${t.original.dur} s` : ""}</div>
      <video controls preload="metadata" style="width:100%;border-radius:8px;background:#000;max-height:360px" src="/api/editar/archivo/fuentes/${t.fuente.split("/")[1]}"></video>
      <img src="/api/editar/archivo/fuentes/${t.hoja.split("/")[1]}" style="width:100%;border-radius:6px;margin-top:6px;opacity:.85" title="lo que GPT mira para describir el video">
      ${t.nota && t.estado === "fuente" ? `<div class="tiny" style="margin-top:4px">${h(t.nota)}</div>` : ""}</div>
    <div>${t.estado === "generando" ? barra(t, `editando en la máquina · ${dur(t.segundos)}`) + `<div class="muted" style="margin-top:6px">${h(t.cambio || "")}</div>`
      : t.estado === "instalando_ref2va" ? barra(t, "instalando el modelo Ref2VA en la máquina") + `<div class="tiny" style="margin-top:6px">${h(t.nota || "")}</div>`
      : t.estado === "error" ? `<div class="pill bad">error</div><div class="tiny">${h(t.nota)}</div><div class="muted" style="margin-top:6px">${h(t.cambio || "")}</div>`
      : `<label class="tiny" style="display:block;margin-bottom:4px">Qué cambiar (en castellano; una cosa clara)</label>
         <textarea id="ec-${t.id}" style="min-height:90px" placeholder="«Que la persona tenga un traje rojo con corbata negra» · «Que el fondo sea una playa al atardecer» · «Que diga: “Hola, ¿cómo están?”»">${h(t.cambio || "")}</textarea>
         <div class="row" style="margin-top:8px;gap:10px;flex-wrap:wrap">
           <div><div class="tiny">imagen de referencia (opcional: la prenda, el fondo)</div>
             ${t.ref ? `<div class="row"><img src="/api/editar/archivo/assets/${t.ref.split("/")[1]}" style="height:54px;border-radius:6px"><button class="btn s" onclick="editarRef('${t.id}', null)">quitar</button></div>`
                     : `<label class="btn s">subir imagen<input type="file" accept="image/*" hidden onchange="editarRefArchivo('${t.id}', this)"></label>`}</div>
           <div><div class="tiny">duración del resultado</div><select id="es-${t.id}" style="max-width:150px">${DURS_H3.filter(([v]) => v <= t.segundos_fuente + 0.8).map(([v, l], i, arr) => `<option value="${v}" ${i === arr.length - 1 ? "selected" : ""}>${l}</option>`).join("")}</select></div>
           ${t.tiene_audio ? `<label class="tiny" style="align-self:end"><input type="checkbox" id="ea-${t.id}" checked> mantener el audio original</label>` : ""}</div>
         <div class="row" style="margin-top:10px"><button class="btn s" onclick="editarArmar('${t.id}')" title="convierte lo que escribiste al formato de referencia completa de H3 y lo deja en el cuadro para que lo revises">Armar prompt H3</button>
           <button class="btn p" ${lista && !d.ocupada ? "" : "disabled"} onclick="editarGenerar('${t.id}')">Editar video</button>
           <span class="tiny">${!lista ? "encendé la máquina desde el inicio" : d.ocupada ? "hay un turno generando" : "si la máquina no tiene Ref2VA, primero lo baja (~5 min)"}</span></div>`}
      </div></div></div>`).join("") || `<div class="muted">Nada en curso. Subí un video para empezar.</div>`) + biblioteca;
  clearTimeout(editTimer);
  if (ts.some(t => t.estado === "generando" || t.estado === "instalando_ref2va")) editTimer = setTimeout(async () => { if (!$("#eturnos")) return; const d2 = await api("/editar"); pintarEdiciones(d2.turnos, d2); }, 12000);
}
async function editarRefArchivo(id, input) {
  const f = input.files[0]; if (!f) return;
  const b64 = await new Promise(r => { const fr = new FileReader(); fr.onload = () => r(fr.result); fr.readAsDataURL(f); });
  editarRef(id, b64);
}
async function editarRef(id, b64) {
  try { await api(`/editar/${id}/referencia`, {method: "POST", body: {b64}}); const d = await api("/editar"); pintarEdiciones(d.turnos, d); }
  catch (e) { toast(e.message, true); }
}
function editarOpciones(id) {
  const a = $(`#ea-${id}`);
  return {id, texto: $(`#ec-${id}`).value, segundos: Number($(`#es-${id}`).value), audio_original: a ? a.checked : false};
}
async function editarArmar(id) {
  const ta = $(`#ec-${id}`);
  toast("armando el prompt de edición… (15-30 s)");
  try { const r = await api("/editar/reescribir", {method: "POST", body: editarOpciones(id)}); ta.value = r.prompt; ta.style.minHeight = "300px";
    toast(r.problemas && r.problemas.length ? "prompt armado, con avisos: " + r.problemas[0] : "prompt armado: revisalo y tocá Editar video", !!(r.problemas && r.problemas.length)); }
  catch (e) { toast(e.message, true); }
}
async function editarGenerar(id) {
  const o = editarOpciones(id);
  toast(o.texto.trim().startsWith("subject_definitions:") ? "lanzando…" : "armando el prompt y lanzando… (15-40 s)");
  try { const t = await api("/editar/generar", {method: "POST", body: o}); toast(t.estado === "instalando_ref2va" ? "la máquina baja Ref2VA; el clip arranca solo después" : "edición lanzada en la máquina"); navegar(); }
  catch (e) { toast(e.message, true); }
}

/* ─────────────────────────────────────────────── series: producción en masa */
const FORMATOS_SERIE = {short: "Shorts verticales", largo: "Largos (recap)", musica: "Music videos"};
const ESTADOS_CAP = {propuesto: ["propuesto", ""], aprobado: ["aprobado · sin guion", "ac"], escribiendo: ["escribiendo el guion", "warn"], guion: ["guion listo", "ok"],
  produciendo: ["produciendo", "warn"], producido: ["producido", "ok"], error: ["error", "bad"], descartado: ["descartado", ""]};
/* Cada sección (Short, Largo, Music video) tiene su propia opción de serie con el
   formato ya fijo. #/series/nueva/<formato> crea; #/series/<formato> lista; #/serie/<slug> es la serie. */
async function pintarSeriesSeccion(formato) {
  const box = $("#series-seccion"); if (!box) return;
  let d; try { d = await api("/series"); } catch { return; }
  const mias = d.series.filter(s => s.formato === formato);
  const que = formato === "musica" ? "music videos" : formato === "largo" ? "largos" : "shorts";
  box.innerHTML = `<div class="card" style="margin-bottom:14px;border-color:rgba(255,180,84,.35)"><h3>¿Uno solo o una serie de ${que}?
      <a class="btn s p" style="margin-left:auto" href="#/series/nueva/${formato}">＋ Nueva serie de ${que}</a></h3>
    <p class="muted" style="margin:0 0 ${mias.length ? 10 : 0}px">Una serie tiene personajes fijos con su hoja de modelo (las caras no cambian entre videos), una idea general que los nombra, y GPT propone los capítulos por tandas y escribe cada guion que aprobás. Los capítulos se dibujan, se empaquetan y entran a la cola solos. Abajo, ${formato === "musica" ? "la escena" : "el guion"} de un video suelto, como siempre.</p>
    ${mias.length ? `<div class="row">${mias.map(s => `<a class="btn s" href="#/serie/${s.slug}">${h(s.titulo)} <span class="tiny">· ${s.personajes} pj · ${s.capitulos} cap · ${s.producidos} hechos</span></a>`).join("")}</div>` : ""}</div>`;
}
ruta("/series", async ([a, b]) => {
  const d = await api("/series");
  if (a === "nueva" && FORMATOS_SERIE[b]) return pintarNuevaSerie(d, b);
  const f = FORMATOS_SERIE[a] ? a : null;
  const lista = f ? d.series.filter(s => s.formato === f) : d.series;
  $("#vista").innerHTML = `<div class="wrap"><h1>Series${f ? " de " + FORMATOS_SERIE[f].toLowerCase() : ""}</h1>
    <p class="sub">Cada sección tiene las suyas: se crean desde <a href="#/nuevo/short">Short</a>, <a href="#/nuevo/largo">Largo</a> o <a href="#/musica">Music video</a>.</p>
    <div class="grid g3">${lista.map(s => `<div class="card" style="cursor:pointer" onclick="location.hash='#/serie/${s.slug}'"><h3>${h(s.titulo)}<span class="pill">${FORMATOS_SERIE[s.formato] || s.formato}</span></h3>
      <div class="muted">${s.personajes} personaje${s.personajes === 1 ? "" : "s"} · ${s.capitulos} capítulo${s.capitulos === 1 ? "" : "s"} · ${s.producidos} producido${s.producidos === 1 ? "" : "s"}${s.aprobados ? ` · ${s.aprobados} por producir` : ""}</div></div>`).join("") || `<div class="muted">Todavía no hay series.</div>`}</div></div>`;
});
function pintarNuevaSerie(d, f) {
  const esMusica = f === "musica";
  const ests = d.estructuras.filter(e => esMusica ? e.nombre.startsWith("loop") : f === "largo" ? (e.nombre.startsWith("recap") || (e.formato === "largo" && !e.nombre.startsWith("loop"))) : (e.formato === "short" && !e.nombre.startsWith("recap")));
  const estDefault = esMusica ? "loop" : f === "largo" ? "recap" : "short-15";
  const que = esMusica ? "music videos" : f === "largo" ? "largos" : "shorts";
  $("#vista").innerHTML = `<div class="wrap"><h1>Nueva serie de ${que}</h1>
    <p class="sub">Primero la ficha. Después, en la serie, cargás los personajes con su nombre y escribís la idea general nombrándolos («los tres amigos Pedro, Luis y Juan tienen aventuras juntos cuando terminan las clases»); de ahí GPT propone los capítulos.</p>
    <div class="grid g2">
      <div class="card"><h3>La ficha</h3>
        <input id="s-titulo" placeholder="Título de la serie" style="margin-bottom:8px">
        <div class="row" style="margin-bottom:8px">
          <select id="s-estructura" style="max-width:280px">${ests.map(e => `<option value="${e.nombre}" ${e.nombre === estDefault ? "selected" : ""}>${e.nombre} · ${e.duracion} s${e.retencion ? " · retención " + Math.round(e.retencion * 100) + " %" : ""}</option>`).join("")}</select>
          ${esMusica ? "" : `<select id="s-voz" style="max-width:240px"><option value="pablo">Voz en off: Pablo, argentino</option><option value="kate">Voz en off: Kate</option><option value="">Sin voz en off</option></select>`}
          <select id="s-cont" style="max-width:280px"><option value="antologia">Antología (capítulos sueltos, mismo universo)</option><option value="serial">Serial (la historia sigue de un capítulo al otro)</option></select></div>
        ${esMusica ? `<div class="row" style="margin-bottom:8px"><select id="s-genero" style="max-width:220px">${GENEROS_MUSICA.map(([v, l]) => `<option value="${v}">${l}</option>`).join("")}</select>
          <select id="s-mdur" style="max-width:170px">${[[60, "1 min"], [180, "3 min"], [300, "5 min"], [600, "10 min"]].map(([v, l]) => `<option value="${v}" ${v === 180 ? "selected" : ""}>pistas de ${l}</option>`).join("")}</select>
          <input id="s-mtipo" placeholder="cómo suena la música de la serie (ánimo, instrumentos, tempo)" style="flex:1;min-width:240px"></div>` : ""}
        <div class="row" style="margin-bottom:8px"><select id="s-estilo" style="max-width:320px">${d.estilos.map(e => `<option value="${e.i}">${h(e.nombre)}</option>`).join("")}<option value="">Estilo propio (al lado)</option></select>
          <input id="s-estilo-libre" placeholder="estilo propio, en inglés (opcional)" style="flex:1;min-width:220px"></div>
        <textarea id="s-idea" style="min-height:80px" placeholder="La idea general (opcional acá: conviene escribirla después de cargar los personajes, nombrándolos)."></textarea>
        <div class="row" style="margin-top:10px"><button class="btn p" onclick="serieCrear('${f}')">Crear la serie</button><a class="btn" href="#/${esMusica ? "musica" : "nuevo/" + f}">volver</a><span class="tiny">gratis</span></div>
        <div id="s-err" class="tiny" style="color:var(--bad);margin-top:6px"></div></div>
      <div class="card"><h3>Cómo sigue</h3>
        <ol class="muted" style="margin:0;padding-left:18px;line-height:1.7">
          <li><b>Personajes</b>: nombre y cómo es (o una imagen). GPT lo pasa a la descripción de los prompts y dibuja la hoja de modelo. La aprobás. Se reusa en todos los capítulos.</li>
          <li><b>La idea general</b>, nombrándolos: qué les pasa, tono, qué se repite.</li>
          <li><b>Plan</b>: «proponé N capítulos». Aprobás, editás o descartás cada uno.</li>
          <li><b>Guion</b> por capítulo: GPT lo escribe ${esMusica ? "como una escena para mirar en loop, más la pista" : "medido a la voz"}. Lo leés, lo tocás, lo aprobás.</li>
          <li><b>Producir</b>: proyecto + ${esMusica ? "pista" : "voz"} + dibujos + ZIP + cola, solo. Gasta API (centavos), no GPU.</li>
          <li><b>La cola</b> genera todos con una máquina y apaga.</li></ol></div>
    </div></div>`;
}
async function serieCrear(f) {
  const body = {titulo: $("#s-titulo").value.trim(), formato: f, idea: $("#s-idea").value, estructura: $("#s-estructura").value || null,
    voz: f === "musica" ? null : ($("#s-voz").value || null), estilo: $("#s-estilo").value === "" ? null : Number($("#s-estilo").value), estilo_libre: $("#s-estilo-libre").value,
    continuidad: $("#s-cont").value, musica: f === "musica" ? {genero: $("#s-genero").value, duracion: Number($("#s-mdur").value), tipo: $("#s-mtipo").value} : null,
    duracion: f === "musica" ? 5.167 : null};
  if (!body.titulo) return $("#s-err").textContent = "Falta el título.";
  try { const s = await api("/series", {method: "POST", body}); location.hash = `#/serie/${s.slug}`; } catch (e) { $("#s-err").textContent = e.message; }
}
let serieTimer = null;
ruta("/serie", async ([slug]) => {
  const s = await api(`/series/${slug}`);
  pintarSerie(s);
});
function pintarSerie(s) {
  const slug = s.slug, tarea = s.tarea;
  const pj = Object.entries(s.personajes), lc = Object.entries(s.locaciones);
  const caps = s.capitulos.filter(c => c.estado !== "descartado"), desc = s.capitulos.filter(c => c.estado === "descartado");
  const aprobables = caps.filter(c => c.estado === "guion").length, sinHoja = pj.filter(([, p]) => !p.hoja).length;
  const est = ESTADOS_CAP;
  const ficha = ([id, p]) => `<div class="card" style="padding:10px"><div class="row" style="justify-content:space-between"><b>${h(p.nombre)}</b><span class="tiny mono">${id}</span></div>
      ${p.hoja ? `<img src="/api/series/${slug}/archivo/assets/${p.hoja.split("/")[1]}?${p.creado}" style="width:100%;border-radius:6px;margin-top:6px;cursor:zoom-in;max-height:300px;object-fit:contain;background:#000" onclick="lightbox('/api/series/${slug}/archivo/assets/${p.hoja.split("/")[1]}')">`
              : p.imagen_ref ? `<img src="/api/series/${slug}/archivo/refs/${p.imagen_ref.split("/")[1]}" style="width:100%;border-radius:6px;margin-top:6px;opacity:.7;max-height:200px;object-fit:contain;background:#000" title="imagen de referencia; la hoja sale de acá">` : `<div class="tiny" style="margin-top:6px">sin hoja todavía</div>`}
      <div class="tiny" style="margin-top:6px">${h(p.descripcion_es || p.descripcion)}</div>
      <details style="margin-top:4px"><summary class="tiny" style="cursor:pointer">descripción para los prompts (inglés) · editar</summary><textarea id="pd-${id}" style="min-height:80px;font-size:12px;margin-top:4px">${h(p.descripcion)}</textarea><button class="btn s" style="margin-top:4px" onclick="seriePersonajeGuardar('${slug}','${id}')">guardar</button></details>
      <div class="row" style="margin-top:8px">${p.hoja ? `<button class="btn s ${p.aprobada ? "" : "p"}" onclick="seriePersonajeAprobar('${slug}','${id}',${!p.aprobada})">${p.aprobada ? "aprobada ✓ (desaprobar)" : "aprobar hoja"}</button><button class="btn s" ${tarea ? "disabled" : ""} onclick="serieHojas('${slug}',['${id}'],true)">otra hoja</button>` : `<button class="btn s p" ${tarea ? "disabled" : ""} onclick="serieHojas('${slug}',['${id}'],false)">dibujar la hoja</button>`}
        <button class="btn s d" onclick="seriePersonajeQuitar('${slug}','${id}')">quitar</button></div></div>`;
  const fichaLoc = ([id, l]) => `<div class="card" style="padding:10px"><div class="row" style="justify-content:space-between"><b>${h(l.nombre)}</b><span class="tiny mono">${id}</span></div>
      ${l.imagen ? `<img src="/api/series/${slug}/archivo/assets/${l.imagen.split("/")[1]}?${l.creado}" style="width:100%;border-radius:6px;margin-top:6px;cursor:zoom-in" onclick="lightbox('/api/series/${slug}/archivo/assets/${l.imagen.split("/")[1]}')">` : `<div class="tiny" style="margin-top:6px">sin imagen todavía</div>`}
      <div class="tiny" style="margin-top:6px">${h(l.descripcion_es || l.descripcion)}</div>
      <div class="row" style="margin-top:8px">${l.imagen ? `<button class="btn s" ${tarea ? "disabled" : ""} onclick="serieHojas('${slug}',['${id}'],true)">otra imagen</button>` : `<button class="btn s p" ${tarea ? "disabled" : ""} onclick="serieHojas('${slug}',['${id}'],false)">dibujar</button>`}<button class="btn s d" onclick="serieLocacionQuitar('${slug}','${id}')">quitar</button></div></div>`;
  const filaCap = (c) => { const [etq, cls] = est[c.estado] || [c.estado, ""]; const pr = c.slug ? s.proyectos[c.slug] : null; const activo = c.estado === "escribiendo" || c.estado === "produciendo";
    return `<div class="card" style="margin-bottom:10px;padding:12px 14px"><div class="row" style="justify-content:space-between"><div><b>${c.n}. ${h(c.titulo)}</b> <span class="pill ${cls}">${activo ? '<i class="dot live"></i> ' : ""}${etq}</span></div>
        <span class="tiny">${(c.personajes || []).map(p => s.personajes[p]?.nombre || p).join(", ")}${c.locacion ? " · " + h(c.locacion) : ""}</span></div>
      ${c.estado === "propuesto" ? `<textarea id="cp-${c.n}" style="min-height:60px;margin-top:6px;font-size:13px">${h(c.premisa)}</textarea>` : `<div class="muted" style="margin-top:6px">${h(c.premisa)}</div>`}
      ${c.musica ? `<div class="tiny" style="margin-top:4px">música: ${h(c.musica)}</div>` : ""}
      ${c.nota ? `<div class="tiny" style="margin-top:4px;color:${c.estado === "error" ? "var(--bad)" : "var(--tx3)"}">${h(c.nota)}</div>` : ""}
      ${c.guion && !activo ? `<details ${c.estado === "guion" ? "open" : ""} style="margin-top:8px"><summary class="tiny" style="cursor:pointer">guion (${c.guion.length} caracteres) · leelo, tocalo y aprobalo</summary>
          <textarea id="cg-${c.n}" style="min-height:${c.estado === "guion" ? 200 : 120}px;margin-top:6px;font-size:13px;line-height:1.5" ${c.estado === "producido" ? "readonly" : ""}>${h(c.guion)}</textarea></details>` : ""}
      ${pr ? `<div class="row" style="margin-top:8px"><a class="btn s p" href="#/p/${c.slug}">abrir el proyecto</a><span class="tiny">${pr.planos} planos · ${pr.assets} dibujos · ${pr.clips} clips${pr.zip ? " · ZIP" : ""}${pr.en_cola ? " · en la cola" : ""}${pr.masters.length ? " · <b>máster listo</b>" : ""}</span></div>` : ""}
      <div class="row" style="margin-top:8px">
        ${c.estado === "propuesto" ? `<button class="btn s p" onclick="serieCap('${slug}',${c.n},{estado:'aprobado',premisa:$('#cp-${c.n}').value})">aprobar</button><button class="btn s" onclick="serieCap('${slug}',${c.n},{estado:'descartado'})">descartar</button>` : ""}
        ${c.estado === "aprobado" ? `<button class="btn s p" ${tarea ? "disabled" : ""} onclick="serieGuion('${slug}',${c.n})">escribir el guion (GPT)</button><button class="btn s" onclick="serieCap('${slug}',${c.n},{estado:'propuesto'})">volver a propuesto</button>` : ""}
        ${c.estado === "guion" ? `<button class="btn s" onclick="serieCap('${slug}',${c.n},{guion:$('#cg-${c.n}').value})">guardar cambios del guion</button><button class="btn s" ${tarea ? "disabled" : ""} onclick="serieGuion('${slug}',${c.n})">otro guion</button><button class="btn s p" ${tarea ? "disabled" : ""} onclick="serieProducir('${slug}',${c.n})">producir este capítulo</button>` : ""}
        ${c.estado === "error" ? `<button class="btn s p" ${tarea ? "disabled" : ""} onclick="serieProducir('${slug}',${c.n})">reintentar</button><button class="btn s" onclick="serieCap('${slug}',${c.n},{estado:'guion'})">volver a guion</button>` : ""}
        ${c.estado === "producido" ? `<button class="btn s" ${tarea ? "disabled" : ""} onclick="serieProducir('${slug}',${c.n})">rehacer lo que falte</button>` : ""}
        ${!activo && c.estado !== "producido" ? `<button class="btn s" style="margin-left:auto" onclick="serieCap('${slug}',${c.n},{estado:'descartado'})">descartar</button>` : ""}
      </div></div>`; };
  const volver = s.formato === "musica" ? "#/musica" : `#/nuevo/${s.formato}`;
  const nombres = pj.map(([, p]) => p.nombre);
  const ejemplo = nombres.length ? `«${nombres.slice(0, 3).join(", ")} ${nombres.length > 1 ? "tienen" : "tiene"} aventuras juntos cuando terminan las clases…»` : "«los tres amigos Pedro, Luis y Juan tienen aventuras juntos cuando terminan las clases»";
  $("#vista").innerHTML = `<div class="wrap"><h1>${h(s.titulo)} <span class="pill">${FORMATOS_SERIE[s.formato] || s.formato} · ${h(s.estructura)}${s.duracion ? " · " + s.duracion + " s" : ""}</span><span class="pill">${s.continuidad === "serial" ? "serial" : "antología"}</span>${s.voz ? `<span class="pill">voz ${h(s.voz)}</span>` : ""}<a class="btn s" href="${volver}" style="margin-left:auto">volver a ${FORMATOS_SERIE[s.formato] || s.formato}</a></h1>
    ${tarea ? `<div class="card" style="margin-bottom:14px;border-color:rgba(255,207,90,.4)"><h3><i class="dot live" style="color:var(--warn)"></i> ${h(tarea.nombre)} <span class="tiny">${mins(tarea.segundos)}</span><button class="btn s" style="margin-left:auto" onclick="matar('${tarea.id}')">parar</button></h3><pre class="pre" style="max-height:160px">${h(tarea.log)}</pre></div>` : ""}
    <h3 style="margin:18px 0 8px"><b style="display:inline-grid;place-items:center;width:22px;height:22px;border-radius:50%;background:var(--ac);color:#1a1205;font-size:12px">1</b> Personajes <span class="pill">${pj.length}</span>${sinHoja ? `<button class="btn s p" style="margin-left:10px" ${tarea ? "disabled" : ""} onclick="serieHojas('${slug}',[],false)">dibujar las ${sinHoja} hojas que faltan</button>` : ""}<span class="tiny" style="margin-left:10px">una imagen por hoja (OpenAI, ~$0,05-0,20)</span></h3>
    <div class="grid g3">
      <div class="card" style="padding:12px"><b>Nuevo personaje</b><div class="tiny" style="margin-bottom:6px">GPT lo pasa a la descripción de los prompts y después le dibujás la hoja.</div>
        <input id="p-nombre" placeholder="Nombre (así lo vas a nombrar en la idea)" style="margin-bottom:6px">
        <textarea id="p-desc" style="min-height:90px" placeholder="Cómo es, en castellano: edad, cuerpo, cara, pelo y la ropa que va a llevar en toda la serie."></textarea>
        <div class="row" style="margin-top:8px"><label class="btn s">imagen de referencia<input type="file" id="p-ref" accept="image/*" hidden onchange="$('#p-refn').textContent=this.files[0]?.name||''"></label><span class="tiny" id="p-refn"></span>
          <button class="btn p s" style="margin-left:auto" onclick="seriePersonaje('${slug}')">agregar</button></div></div>
      ${pj.map(ficha).join("")}</div>
    <h3 style="margin:18px 0 8px">Locaciones fijas <span class="pill">${lc.length}</span><span class="tiny" style="margin-left:10px">opcional: los lugares que se repiten</span></h3>
    <div class="grid g3">
      <div class="card" style="padding:12px"><b>Nueva locación</b><input id="l-nombre" placeholder="Nombre" style="margin:6px 0"><input id="l-desc" placeholder="qué lugar es, luz, época"><div class="row" style="margin-top:8px"><button class="btn s" style="margin-left:auto" onclick="serieLocacion('${slug}')">agregar</button></div></div>
      ${lc.map(fichaLoc).join("")}</div>
    <h3 style="margin:26px 0 8px"><b style="display:inline-grid;place-items:center;width:22px;height:22px;border-radius:50%;background:var(--ac);color:#1a1205;font-size:12px">2</b> La idea general</h3>
    <div class="card" style="margin-bottom:14px">
      <div class="tiny" style="margin-bottom:4px">Nombrá a los personajes por su nombre, por ejemplo ${h(ejemplo)}. De acá GPT propone los capítulos.</div>
      <textarea id="b-idea" style="min-height:90px;margin:4px 0 8px" placeholder="De qué va la serie, tono, a quién le habla, qué se repite en cada capítulo.">${h(s.idea)}</textarea>
      <label class="tiny">Notas del director (tono, qué no mostrar, reglas de la serie)</label><textarea id="b-notas" style="min-height:50px;margin:4px 0 8px">${h(s.notas || "")}</textarea>
      <div class="tiny">Estilo visual: ${h(s.estilo.imagen.slice(0, 140))}${s.estilo.imagen.length > 140 ? "…" : ""}</div>
      ${s.musica ? `<div class="tiny" style="margin-top:4px">Música: ${h(s.musica.genero)} · pistas de ${s.musica.duracion} s · ${h(s.musica.tipo || "")}</div>` : ""}
      <div class="row" style="margin-top:8px"><button class="btn s p" onclick="serieBiblia('${slug}')">guardar la idea</button><button class="btn s d" style="margin-left:auto" onclick="serieBorrar('${slug}')">borrar la serie</button></div></div>
    <h3 style="margin:26px 0 8px"><b style="display:inline-grid;place-items:center;width:22px;height:22px;border-radius:50%;background:var(--ac);color:#1a1205;font-size:12px">3</b> Capítulos <span class="pill">${caps.length}</span>
      <span class="row" style="margin-left:auto;gap:6px"><input id="plan-n" type="number" min="1" max="50" value="10" style="width:70px"><input id="plan-pista" placeholder="pista para esta tanda (opcional)" style="width:260px"><button class="btn s p" ${tarea ? "disabled" : ""} onclick="seriePlan('${slug}')">proponer capítulos (GPT)</button></span></h3>
    ${aprobables ? `<div class="row" style="margin-bottom:10px"><button class="btn p" ${tarea ? "disabled" : ""} onclick="serieProducirTodos('${slug}',${aprobables})">producir los ${aprobables} con guion aprobado</button><span class="tiny">traduce, hace la voz, dibuja, empaqueta y encola cada uno; después corrés la cola</span></div>` : ""}
    ${caps.map(filaCap).join("") || `<div class="muted">Sin capítulos. Proponé una tanda.</div>`}
    ${desc.length ? `<details style="margin-top:10px"><summary class="tiny" style="cursor:pointer">${desc.length} descartado(s)</summary>${desc.map(c => `<div class="tiny" style="margin-top:4px">${c.n}. ${h(c.titulo)} — ${h(c.premisa)} <button class="btn s" onclick="serieCap('${slug}',${c.n},{estado:'propuesto'})">recuperar</button></div>`).join("")}</details>` : ""}
    </div>`;
  clearTimeout(serieTimer);
  if (tarea || s.capitulos.some(c => c.estado === "escribiendo" || c.estado === "produciendo"))
    serieTimer = setTimeout(async () => { if (!location.hash.startsWith(`#/serie/${slug}`)) return; try { pintarSerie(await api(`/series/${slug}`)); } catch {} }, 6000);
}
async function serieRefrescar(slug) { try { pintarSerie(await api(`/series/${slug}`)); } catch (e) { toast(e.message, true); } }
async function serieBiblia(slug) {
  try { await api(`/series/${slug}`, {method: "PUT", body: {idea: $("#b-idea").value, notas: $("#b-notas").value}}); toast("biblia guardada"); } catch (e) { toast(e.message, true); }
}
function serieBorrar(slug) {
  confirmar("Borrar la serie", "Se borran la biblia, los personajes y sus hojas, y el plan. Los proyectos ya producidos en mis-videos/ quedan.", "Borrar", async () => {
    try { await api(`/series/${slug}`, {method: "DELETE"}); location.hash = "#/series"; } catch (e) { toast(e.message, true); }
  }, true);
}
async function seriePersonaje(slug) {
  const nombre = $("#p-nombre").value.trim(), descripcion = $("#p-desc").value.trim();
  if (!nombre || descripcion.length < 10) return toast("nombre y una descripción", true);
  const f = $("#p-ref").files[0];
  const b64 = f ? await new Promise(r => { const fr = new FileReader(); fr.onload = () => r(fr.result); fr.readAsDataURL(f); }) : null;
  toast("GPT describe al personaje… (10-20 s)");
  try { await api(`/series/${slug}/personajes`, {method: "POST", body: {nombre, descripcion, b64}}); serieRefrescar(slug); } catch (e) { toast(e.message, true); }
}
async function seriePersonajeGuardar(slug, id) {
  try { await api(`/series/${slug}/personajes/${id}`, {method: "PUT", body: {descripcion: $(`#pd-${id}`).value}}); toast("guardado"); } catch (e) { toast(e.message, true); }
}
async function seriePersonajeAprobar(slug, id, ok) {
  try { await api(`/series/${slug}/personajes/${id}`, {method: "PUT", body: {aprobada: ok}}); serieRefrescar(slug); } catch (e) { toast(e.message, true); }
}
function seriePersonajeQuitar(slug, id) {
  confirmar("Quitar el personaje", "Se borra su hoja también.", "Quitar", async () => { try { await api(`/series/${slug}/personajes/${id}`, {method: "DELETE"}); serieRefrescar(slug); } catch (e) { toast(e.message, true); } }, true);
}
async function serieLocacion(slug) {
  const nombre = $("#l-nombre").value.trim(), descripcion = $("#l-desc").value.trim();
  if (!nombre || descripcion.length < 5) return toast("nombre y descripción", true);
  toast("GPT describe la locación…");
  try { await api(`/series/${slug}/locaciones`, {method: "POST", body: {nombre, descripcion}}); serieRefrescar(slug); } catch (e) { toast(e.message, true); }
}
function serieLocacionQuitar(slug, id) {
  confirmar("Quitar la locación", "Se borra su imagen también.", "Quitar", async () => { try { await api(`/series/${slug}/locaciones/${id}`, {method: "DELETE"}); serieRefrescar(slug); } catch (e) { toast(e.message, true); } }, true);
}
async function serieHojas(slug, ids, rehacer) {
  try { const r = await api(`/series/${slug}/hojas`, {method: "POST", body: {ids, rehacer, motor: "openai"}}); seguirTarea(r.tarea, () => serieRefrescar(slug)); toast("dibujando… (1-2 min por hoja)"); serieRefrescar(slug); } catch (e) { toast(e.message, true); }
}
async function seriePlan(slug) {
  const n = Number($("#plan-n").value || 10), pista = $("#plan-pista").value;
  try { const r = await api(`/series/${slug}/planificar`, {method: "POST", body: {n, pista}}); seguirTarea(r.tarea, () => serieRefrescar(slug)); toast(`GPT propone ${n} capítulos… (30-90 s)`); serieRefrescar(slug); } catch (e) { toast(e.message, true); }
}
async function serieCap(slug, n, cambios) {
  try { pintarSerie({...(await api(`/series/${slug}/capitulos/${n}`, {method: "PUT", body: cambios})), proyectos: {}, tarea: null, cola: {items: []}}); serieRefrescar(slug); } catch (e) { toast(e.message, true); }
}
async function serieGuion(slug, n) {
  try { const r = await api(`/series/${slug}/capitulos/${n}/guion`, {method: "POST"}); seguirTarea(r.tarea, () => serieRefrescar(slug)); toast("GPT escribe el guion… (30-60 s)"); serieRefrescar(slug); } catch (e) { toast(e.message, true); }
}
function serieProducir(slug, n) {
  confirmar("Producir el capítulo", "Traduce el guion a planos (GPT), hace la voz (ElevenLabs), dibuja los fotogramas (una imagen por plano, ~$0,05-0,20 cada una), arma el ZIP y lo pone en la cola. <b>No alquila GPU</b>: eso lo hacés después corriendo la cola.", "Producir", async () => {
    try { const r = await api(`/series/${slug}/capitulos/${n}/producir`, {method: "POST", body: {confirmar: true}}); seguirTarea(r.tarea, () => serieRefrescar(slug)); toast("produciendo… (3-8 min)"); serieRefrescar(slug); } catch (e) { toast(e.message, true); }
  });
}
function serieProducirTodos(slug, n) {
  confirmar(`Producir ${n} capítulos`, `Uno tras otro: guion → planos → voz → dibujos → ZIP → cola. Gasta API (unos centavos a un dólar por capítulo en imágenes y voz), no GPU. Tarda 3-8 min por capítulo; podés cerrar la página.`, "Producir todos", async () => {
    try { const r = await api(`/series/${slug}/producir-aprobados`, {method: "POST", body: {confirmar: true}}); seguirTarea(r.tarea, () => serieRefrescar(slug)); toast("produciendo los aprobados…"); serieRefrescar(slug); } catch (e) { toast(e.message, true); }
  });
}

/* ─────────────────────────────────────────────── remasterizar: SD → 4K con FlashVSR en una A100 */
let remTimer = null;
const FASES_REM = {apagada: ["apagada", ""], fallo: ["falló", "bad"], buscando: ["buscando una A100…", "warn"], arrancando: ["arrancando", "warn"],
  instalando: ["instalando FlashVSR", "warn"], remasterizando: ["remasterizando", "warn"], codificando: ["codificando el 4K", "warn"],
  bajando: ["bajando", "warn"], lista: ["viva, con salida sin bajar", "warn"]};
const ESTADOS_REM = {descargando: ["bajando de Drive", "warn"], origen: ["por preparar", ""], preparando: ["preparando la fuente", "warn"], preparado: ["fuente lista", "ok"],
  alquilando: ["alquilando", "warn"], arrancando: ["arrancando la A100", "warn"], instalando: ["instalando FlashVSR", "warn"],
  remasterizando: ["remasterizando", "warn"], codificando: ["codificando el 4K", "warn"], bajando: ["bajando el 4K", "warn"],
  qc: ["control de calidad", "warn"], listo: ["listo", "ok"], sin_bajar: ["hecho, sin bajar", "bad"], error: ["error", "bad"]};
const hms = (s) => { s = Math.max(0, Math.round(s || 0)); const hh = Math.floor(s / 3600), mm = Math.floor(s % 3600 / 60), ss = s % 60; return (hh ? hh + ":" : "") + String(mm).padStart(hh ? 2 : 1, "0") + ":" + String(ss).padStart(2, "0"); };
ruta("/remaster", async () => {
  const d = await api("/remaster");
  const m = d.maquina || {fase: "apagada"};
  const [ftxt, fcls] = FASES_REM[m.fase] || [m.fase, ""];
  $("#vista").innerHTML = `<div class="wrap"><h1>Remasterizar <span class="pill ${fcls}">A100 ${h(ftxt)}${m.instancia && m.fase !== "apagada" ? " · " + m.instancia : ""}</span>${m.fase !== "apagada" && m.fase !== "fallo" ? `<span class="pill warn">${usd(m.acumulado)} · ${m.minutos} min</span> <button class="btn s d" onclick="remApagar()">apagar</button>` : ""}<span class="pill" style="margin-left:6px">saldo Vast ${usd(d.saldo)}</span></h1>
    <p class="sub">Una película o un capítulo en definición estándar (DVD, máster de emisión, 576i/480p) a 4K con <b>FlashVSR v1.1</b>, el modelo que ganó las pruebas con jueces humanos de 2026. Corre en una <b>A100 de 80 GB aparte</b> de la máquina de H3. El análisis y la preparación son gratis; el alquiler se confirma con el costo a la vista. Medido: <b>1 minuto de A100 por segundo de video</b> (≈ $52 la hora de película); un origen pobre (menos de 5 Mb/s) inventa las caras lejanas.</p>
    <div class="card" style="margin-bottom:14px"><h3>Nuevo origen</h3>
      <div class="row"><label class="btn p">subir video<input type="file" id="rfile" accept="video/*,.mxf,.mpg,.vob,.ts" hidden></label>
        <span class="tiny">hasta ~300 MB por el navegador. Para un máster grande:</span>
        <input id="rruta" placeholder="ruta del archivo en este servidor, p. ej. remasterizado\\original\\capitulo.mxf" style="max-width:520px">
        <button class="btn" onclick="remRuta()">analizar la ruta</button></div>
      <div class="row" style="margin-top:8px"><span class="tiny">o un link de Google Drive (del archivo, compartido con «cualquiera con el link»):</span>
        <input id="rdrive" placeholder="https://drive.google.com/file/d/…/view" style="max-width:520px">
        <button class="btn" onclick="remDrive()">bajar y analizar</button>
        <span class="tiny">se baja acá como tarea (retoma si se corta) y se analiza solo al terminar</span></div>
      <div id="rerr" class="tiny" style="color:var(--bad);margin-top:6px"></div></div>
    <div id="rtrabajos"></div></div>`;
  $("#rfile").addEventListener("change", async (ev) => {
    const f = ev.target.files[0]; if (!f) return;
    if (f.size > 300 * 1024 * 1024) { $("#rerr").textContent = "el archivo pesa más de 300 MB: copialo a la carpeta del proyecto y pegá la ruta"; return; }
    toast("subiendo y analizando… (puede tardar un minuto)");
    const b64 = await new Promise(r => { const fr = new FileReader(); fr.onload = () => r(fr.result); fr.readAsDataURL(f); });
    try { await api("/remaster/origen", {method: "POST", body: {nombre: f.name, b64}}); toast("origen analizado"); navegar(); }
    catch (e) { $("#rerr").textContent = e.message; }
  });
  pintarRemaster(d);
});
async function remDrive() {
  const drive = $("#rdrive").value.trim(); if (!drive) return;
  try { await api("/remaster/origen", {method: "POST", body: {drive}}); toast("bajando de Drive… podés cerrar la página"); navegar(); }
  catch (e) { $("#rerr").textContent = e.message; }
}
async function remReintentarDescarga(id) {
  try { const r = await api(`/remaster/${id}/descargar`, {method: "POST"}); seguirTarea(r.tarea, () => navegar()); toast("retomando la descarga…"); navegar(); }
  catch (e) { toast(e.message, true); }
}
async function remRuta() {
  const ruta = $("#rruta").value.trim(); if (!ruta) return;
  toast("analizando… (sondeo + detección de entrelazado, 10-60 s)");
  try { await api("/remaster/origen", {method: "POST", body: {ruta}}); toast("origen analizado"); navegar(); }
  catch (e) { $("#rerr").textContent = e.message; }
}
function pintarRemaster(d) {
  const ts = d.trabajos || [], m = d.maquina || {};
  const libre = !d.ocupada && !d.tarea && (m.fase === "apagada" || m.fase === "fallo");
  const secs = s => s == null ? "—" : `${Number(s).toFixed(1).replace(".", ",")} s`;
  const barra = (t) => { const p = t.progreso || {}; const [etq] = ESTADOS_REM[t.estado] || [t.estado];
    return `<div class="row" style="justify-content:space-between"><span class="pill warn"><i class="dot live"></i> ${etq}</span><span class="tiny">${p.total && p.hechos != null && t.estado !== "descargando" ? `${p.hechos} de ${p.total} cuadros` : ""}${m.inicio && m.fase !== "apagada" ? ` · ${usd(m.acumulado)} · ${m.minutos} min` : ""}</span></div>
      <div class="bar" style="height:10px;margin-top:8px"><i style="width:${p.pct != null ? p.pct : 2}%"></i></div>
      <div class="tiny mono" style="margin-top:6px;white-space:pre-wrap;opacity:.75">${h(p.ultimo || "esperando la primera señal…")}</div>
      ${d.tarea ? `<pre class="pre" style="margin-top:8px;max-height:140px">${h(d.tarea.log)}</pre>` : ""}`; };
  const sonda = (s) => !s ? "" : `${s.w}×${s.h}${s.dar ? " (DAR " + s.dar + ")" : ""} · ${s.fps} fps · ${hms(s.dur)} · ${s.codec}${s.pix ? " " + s.pix : ""} · ${s.kbps ? (s.kbps / 1000).toFixed(1).replace(".", ",") + " Mb/s" : "bitrate ?"} · ${s.entrelazado ? "entrelazado " + s.campo.toUpperCase() : "progresivo"} · ${s.canales ? s.canales + " canal" + (s.canales > 1 ? "es" : "") + " de audio" : "sin audio"}`;
  const avisos = (t) => (t.avisos || []).map(a => `<div class="pill ${a.nivel === "info" ? "" : a.nivel}" style="display:flex;white-space:normal;margin-top:6px;padding:8px 12px;line-height:1.35">${h(a.texto)}</div>`).join("");
  const form = (t) => { if (!t.sonda) return t.drive ? `<div class="row" style="margin-top:8px"><button class="btn p" onclick="remReintentarDescarga('${t.id}')" ${d.tarea ? "disabled" : ""}>reintentar descarga</button><span class="tiny">${h(t.drive.url)}</span></div>` : ""; const o = t.opciones, s = t.sonda; return `
    <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;margin-top:8px">
      <div><div class="tiny">desde (s)</div><input id="ri-${t.id}" type="number" min="0" step="0.1" value="${o.inicio || 0}"></div>
      <div><div class="tiny">hasta (s, vacío = final)</div><input id="rf-${t.id}" type="number" min="0" step="0.1" value="${o.fin ?? ""}" placeholder="${Math.round(s.dur)}"></div>
      <div><div class="tiny">recorte ancho:alto:x:y</div><input id="rc-${t.id}" value="${h(o.recorte || "")}" placeholder="sin recorte" title="saca el VBI y el blanking del máster; 720×608 IMX → 704:576:12:32"></div>
      <div><div class="tiny">entrelazado</div><select id="rd-${t.id}"><option value="1" ${o.desentrelazar ? "selected" : ""}>desentrelazar (bwdif)</option><option value="0" ${!o.desentrelazar ? "selected" : ""}>ya es progresivo</option></select></div>
      <div><div class="tiny">campo dominante</div><select id="rp-${t.id}">${["auto", "tff", "bff"].map(c => `<option value="${c}" ${o.campo === c ? "selected" : ""}>${c.toUpperCase()}</option>`).join("")}</select></div>
    </div>
    <div class="row" style="margin-top:10px"><button class="btn p" onclick="remPreparar('${t.id}')" ${d.tarea ? "disabled" : ""}>Preparar la fuente</button>
      <span class="tiny">ffmpeg local, gratis: recorte + desentrelazado + x264 casi sin pérdida. ${t.fuente ? "Ya hay una fuente: prepararla de nuevo la reemplaza." : ""}</span></div>`; };
  const estimado = (t) => `<div id="rest-${t.id}" class="card" style="margin-top:10px;padding:12px 14px;background:var(--panel2)"><div class="muted">consultando las A100 disponibles…</div></div>`;
  const listo = (t) => { const s = t.salidas || {}; return `
    <div class="grid" style="grid-template-columns:1fr 1fr;gap:8px;margin-top:6px"><div><div class="tiny">fuente (SD)</div><video controls preload="metadata" style="width:100%;border-radius:6px;background:#000" src="/api/remaster/archivo/fuentes/${t.fuente.split("/")[1]}"></video></div>
      <div><div class="tiny">4K · ${t.final ? t.final.w + "×" + t.final.h : ""}</div><video controls preload="metadata" style="width:100%;border-radius:6px;background:#000" src="/api/remaster/archivo/salidas/${s["4k"].split("/")[1]}"></video></div></div>
    ${t.qc && t.qc.length ? `<div class="tiny" style="margin-top:8px">control de calidad: origen (píxel tal cual) a la izquierda, 4K a la derecha; los dos últimos con zoom ×3 al centro</div>
      <div class="grid" style="grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:6px;margin-top:4px">${t.qc.map(q => `<img src="/api/remaster/archivo/qc/${q.split("/")[1]}" style="width:100%;border-radius:6px;cursor:zoom-in" onclick="lightbox('/api/remaster/archivo/qc/${q.split("/")[1]}')">`).join("")}</div>` : ""}
    <div class="row" style="margin-top:10px"><a class="btn p" href="/api/remaster/archivo/salidas/${s["4k"].split("/")[1]}" download>descargar 4K</a>
      ${s.uhd ? `<a class="btn" href="/api/remaster/archivo/salidas/${s.uhd.split("/")[1]}" download>descargar UHD 3840×2160</a>` : `<button class="btn" onclick="remUhd('${t.id}')" ${d.tarea ? "disabled" : ""}>hacer versión UHD 3840×2160 (barras)</button>`}
      <span class="tiny">${t.costo && t.costo.real != null ? `costó ${usd(t.costo.real)} (${t.costo.minutos} min de A100${t.costo.factor_medido ? `, ${t.costo.factor_medido}× tiempo real` : ""}; estimado ${usd(t.costo.estimado)})` : ""}</span></div>`; };
  $("#rtrabajos").innerHTML = ts.map(t => { const [etq, cls] = ESTADOS_REM[t.estado] || [t.estado, ""]; const activo = ["descargando", "preparando", "alquilando", "arrancando", "instalando", "remasterizando", "codificando", "bajando", "qc"].includes(t.estado);
    return `<div class="card" style="margin-bottom:12px"><h3>${h(t.nombre || "(sin nombre)")} <span class="tiny mono">${t.id}</span><span class="pill ${cls}">${activo ? '<i class="dot live"></i> ' : ""}${etq}</span></h3>
    <div class="grid g2">
      <div><div class="tiny" style="margin-bottom:6px">${sonda(t.sonda)}</div>
        ${t.hoja ? `<img src="/api/remaster/archivo/hojas/${t.hoja.split("/")[1]}" style="width:100%;border-radius:6px;cursor:zoom-in" onclick="lightbox('/api/remaster/archivo/hojas/${t.hoja.split("/")[1]}')">` : ""}
        ${avisos(t)}
        ${t.fuente && t.hoja_fuente && t.estado !== "listo" ? `<div class="tiny" style="margin-top:8px">la fuente preparada: ${t.sonda_fuente ? t.sonda_fuente.w + "×" + t.sonda_fuente.h : ""} · ${secs(t.segundos_fuente)} · ${t.cuadros} cuadros → 4K ${t.final ? t.final.w + "×" + t.final.h : ""}</div><img src="/api/remaster/archivo/hojas/${t.hoja_fuente.split("/")[1]}" style="width:100%;border-radius:6px;margin-top:4px;opacity:.9">` : ""}
        <div class="tiny" style="margin-top:6px;opacity:.7">${h(t.origen || (t.drive ? t.drive.url : ""))}</div></div>
      <div>${activo ? barra(t)
        : t.estado === "listo" ? listo(t)
        : t.estado === "sin_bajar" ? `<div class="pill bad">hecho, sin bajar</div><div class="tiny" style="margin:6px 0">${h(t.nota)}</div><div class="row"><button class="btn p" onclick="remBajar('${t.id}')">bajar de nuevo</button><button class="btn d" onclick="remApagar()">apagar y perderlo</button></div>`
        : (t.estado === "error" ? `<div class="pill bad">error</div><div class="tiny" style="margin:6px 0">${h(t.nota)}</div>` : "") + (t.nota && t.estado === "origen" ? `<div class="tiny" style="color:var(--bad)">${h(t.nota)}</div>` : "")
          + form(t) + (t.fuente ? estimado(t) : "")}
      </div></div>
    ${!activo ? `<div class="row" style="justify-content:flex-end;margin-top:8px"><button class="btn s" onclick="remBorrar('${t.id}')">borrar</button></div>` : ""}</div>`; }).join("") || `<div class="muted">Nada todavía. Subí un video o pegá una ruta para analizarlo.</div>`;
  ts.filter(t => t.fuente && !["preparando", "alquilando", "arrancando", "instalando", "remasterizando", "codificando", "bajando", "qc", "listo", "sin_bajar"].includes(t.estado)).forEach(t => remEstimar(t, libre));
  clearTimeout(remTimer);
  if (ts.some(t => t.estado !== "listo" && t.estado !== "error" && t.estado !== "origen" && t.estado !== "preparado" && t.estado !== "sin_bajar") || d.tarea)
    remTimer = setTimeout(async () => { if (!$("#rtrabajos")) return; try { const d2 = await api("/remaster"); pintarRemaster(d2); } catch {} }, 10000);
}
async function remEstimar(t, libre) {
  const box = $(`#rest-${t.id}`); if (!box) return;
  try {
    const e = await api(`/remaster/${t.id}/estimacion`);
    const est = e.estimado, mejor = e.mejor;
    box.innerHTML = `<div class="kpis"><div class="kpi"><div class="l">video</div><div class="v">${hms(e.segundos)}</div></div><div class="kpi"><div class="l">A100, estimado</div><div class="v">${est.minutos} min</div></div>
        <div class="kpi"><div class="l">costo estimado</div><div class="v">${usd(est.costo)}</div></div><div class="kpi"><div class="l">tope (×1,5)</div><div class="v">${usd(est.tope)}</div></div></div>
      <div class="tiny" style="margin-top:8px">${mejor ? `mejor A100 ahora: ${h(mejor.gpu)} ${Math.round(mejor.vram_gb)} GB · ${h(mejor.geo)} · $${mejor.dph}/h · ${mejor.inet} Mbps · fiab ${mejor.fiabilidad}` : "no hay ninguna A100 de 80 GB apta ahora (verificada, ≤ $1,30/h, fuera de China): probá en unos minutos"}${e.saldo != null ? ` · saldo ${usd(e.saldo)}` : ""}</div>
      ${e.ofertas.length ? `<details style="margin-top:6px"><summary class="tiny" style="cursor:pointer">todas las ofertas (${e.ofertas.length})</summary><table style="margin-top:6px"><tr><th>placa</th><th>lugar</th><th class="num">$/h</th><th class="num">Mbps</th><th class="num">fiab</th><th class="num">estimado</th><th></th></tr>
        ${e.ofertas.map(o => `<tr class="${o.apta ? "apta" : "noapta"}"><td>${h(o.gpu)} ${Math.round(o.vram_gb)} GB</td><td>${h(o.geo)}</td><td class="num">${o.dph}</td><td class="num">${o.inet}</td><td class="num">${o.fiabilidad}</td><td class="num">${usd(o.estimado)}</td><td>${o.apta ? `<button class="btn s" onclick="remCorrer('${t.id}', ${o.id}, ${o.estimado}, ${o.dph})">usar</button>` : `<span class="tiny">${h(o.motivos.join(", "))}</span>`}</td></tr>`).join("")}</table></details>` : ""}
      <div class="row" style="margin-top:10px"><button class="btn p" ${libre && mejor ? "" : "disabled"} onclick="remCorrer('${t.id}', null, ${est.costo}, ${est.dph})">Remasterizar (alquila la A100)</button>
        <span class="tiny">${!libre ? "hay otra tarea o una A100 encendida" : mejor ? "elige la de mayor fiabilidad; se destruye sola al terminar o al fallar" : "esperá a que aparezca una apta"}</span></div>`;
  } catch (err) { box.innerHTML = `<div class="tiny" style="color:var(--bad)">${h(err.message)}</div>`; }
}
function remOpciones(id) {
  return {inicio: Number($(`#ri-${id}`).value || 0), fin: $(`#rf-${id}`).value === "" ? null : Number($(`#rf-${id}`).value),
          recorte: $(`#rc-${id}`).value.trim(), desentrelazar: $(`#rd-${id}`).value === "1", campo: $(`#rp-${id}`).value};
}
async function remPreparar(id) {
  try { const r = await api(`/remaster/${id}/preparar`, {method: "POST", body: remOpciones(id)}); seguirTarea(r.tarea, () => navegar()); toast("preparando la fuente…"); navegar(); }
  catch (e) { toast(e.message, true); }
}
function remCorrer(id, oferta, costo, dph) {
  confirmar("Alquilar una A100 y remasterizar",
    `Esto alquila una A100 de 80 GB a <b>$${dph}/h</b>, instala FlashVSR (~13 min), remasteriza a <b>1 min de máquina por segundo de video</b>, codifica el 4K en la máquina, lo baja y <b>destruye la instancia</b> sola al terminar o al fallar.<br><br>Costo estimado <b>${usd(costo)}</b>, tope ~${usd(costo * 1.5)}. Podés cerrar la página; la tarea sigue.`,
    "Alquilar y remasterizar", async () => {
      try { const r = await api(`/remaster/${id}/correr`, {method: "POST", body: {confirmar: true, oferta}}); seguirTarea(r.tarea, () => navegar()); toast("A100 alquilándose…"); navegar(); }
      catch (e) { toast(e.message, true); }
    });
}
async function remBajar(id) {
  try { const r = await api(`/remaster/${id}/bajar`, {method: "POST"}); seguirTarea(r.tarea, () => navegar()); toast("bajando…"); navegar(); } catch (e) { toast(e.message, true); }
}
async function remUhd(id) {
  try { const r = await api(`/remaster/${id}/uhd`, {method: "POST"}); seguirTarea(r.tarea, () => navegar()); toast("codificando la versión UHD…"); } catch (e) { toast(e.message, true); }
}
function remApagar() {
  confirmar("Apagar la A100", "Destruye la instancia del remaster y deja de cobrar. Si había un trabajo en curso se pierde.", "Apagar", async () => {
    try { const r = await api("/remaster/maquina/apagar", {method: "POST", body: {confirmar: true}}); toast(`apagada · ${usd(r.gasto_final)} en ${r.minutos} min`); estadoVast(); navegar(); } catch (e) { toast(e.message, true); }
  }, true);
}
function remBorrar(id) {
  confirmar("Borrar el trabajo", "Se borran la fuente preparada, las salidas y el QC de este trabajo. El archivo original no se toca si lo analizaste por ruta.", "Borrar", async () => {
    try { await api(`/remaster/${id}`, {method: "DELETE"}); navegar(); } catch (e) { toast(e.message, true); }
  }, true);
}

/* ─────────────────────────────────────────────── libre: el chat con H3 */
let libreTimer = null;
ruta("/libre", async () => {
  const d = await api("/libre");
  const lista = d.maquina === "lista";
  $("#vista").innerHTML = `<div class="wrap"><h1>Libre <span class="pill ${lista ? "ok" : "warn"}">máquina ${h(d.maquina || "apagada")}</span></h1>
    <p class="sub">Un prompt → una imagen → un clip de MiniMax H3. Sin estructura, sin proyecto: para probar una idea, un estilo o un movimiento. La imagen cuesta 4 centavos; el clip, entre 4 minutos (5 s) y 13 minutos (15 s) de GPU de la máquina encendida.</p>
    <div class="card" style="margin-bottom:14px"><h3>Nuevo turno</h3>
      <textarea id="lp" style="min-height:80px" placeholder="Qué querés ver (en castellano o inglés): «un faro de piedra en una tormenta de noche, visto desde el mar, olas enormes, la lámpara girando»"></textarea>
      <div class="row" style="margin-top:8px"><select id="lasp" style="max-width:160px"><option value="16:9">16:9 horizontal</option><option value="9:16">9:16 vertical</option></select>
        <select id="lmotor" style="max-width:220px"><option value="openai">OpenAI / GPT (~$0,25)</option><option value="nanobanana">nano banana (~$0,04, sin créditos hoy)</option></select>
        <input id="lest" placeholder="estilo (opcional, en inglés): photorealistic, 35mm film grain…" style="flex:1;min-width:220px">
        <select id="lajuste" style="max-width:250px" title="qué hacer si la imagen subida no tiene la proporción del video"><option value="encajar">subida: entera, fondo desenfocado</option><option value="recortar">subida: recortar al centro</option></select>
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
  // La mesa de trabajo: sólo lo que está en curso (imagen sin clip, generando,
  // error). Lo terminado baja a la biblioteca y deja la página libre.
  const activos = ts.filter(t => t.estado !== "listo"), hechos = ts.filter(t => t.estado === "listo");
  const dur = s => `${Number(s).toFixed(2).replace(".", ",")} s`;
  const biblioteca = hechos.length ? `<h3 style="margin-top:22px">Biblioteca <span class="pill">${hechos.length} clip${hechos.length > 1 ? "s" : ""}</span></h3>
    <div class="grid g3">${hechos.map(t => `<div class="card" style="padding:10px">
      <video controls preload="metadata" style="width:100%;border-radius:8px;background:#000" src="/api/libre/archivo/${t.clip}"></video>
      <div class="tiny" style="margin-top:6px">${new Date(t.creado * 1000).toLocaleString("es-AR")} · ${t.aspecto} · ${dur(t.segundos)}</div>
      <details style="margin-top:4px"><summary class="tiny" style="cursor:pointer">prompt</summary><div class="tiny mono" style="white-space:pre-wrap;opacity:.8;max-height:220px;overflow:auto">${h(t.prompt_video)}</div></details>
      <div class="row" style="margin-top:8px;gap:8px"><a class="btn s" href="/api/libre/archivo/${t.clip}" download>descargar</a>
        <button class="btn s" onclick="libreOtraVez('${t.id}')" title="turno nuevo con la misma imagen y este prompt precargado">otra versión</button></div></div>`).join("")}</div>` : "";
  $("#turnos").innerHTML = (activos.map(t => `<div class="card" style="margin-bottom:12px"><div class="grid g2">
    <div><div class="tiny" style="margin-bottom:6px">${new Date(t.creado * 1000).toLocaleString("es-AR")} · ${t.aspecto} · ${h(t.origen_imagen)}</div>
      <img src="/api/libre/archivo/${t.imagen}" style="width:100%;border-radius:8px;cursor:zoom-in" onclick="lightbox('/api/libre/archivo/${t.imagen}')">
      <div class="muted" style="margin-top:6px">${h(t.prompt_imagen || "(imagen subida)")}</div></div>
    <div>${t.estado === "generando" ? (p => `<div class="row" style="justify-content:space-between"><span class="pill warn"><i class="dot live"></i> generando en la máquina · ${t.segundos} s</span><span class="tiny">${p ? `${Math.floor(p.transcurrido / 60)} min de ~${Math.round(p.estimado / 60)} estimados` : ""}</span></div>
          <div class="bar" style="height:10px;margin-top:8px"><i style="width:${p ? p.pct : 2}%"></i></div>
          <div class="tiny mono" style="margin-top:6px;white-space:pre-wrap;opacity:.75">${p && p.ultimo ? h(p.ultimo) : "esperando la primera señal de la placa…"}</div>
          <div class="tiny" style="margin-top:4px">El estimado sale de los tiempos medidos (~0,8 min de GPU por segundo de clip). Si el log dice «!!» o pasa de 25 min, falló: casi siempre es memoria en los clips largos.</div>
          <div class="muted" style="margin-top:6px">${h(t.prompt_video)}</div>`)(t.progreso)
      : t.estado === "error" ? `<div class="pill bad">error</div><div class="tiny">${h(t.nota)}</div>`
      : `<textarea id="lv-${t.id}" style="min-height:70px" placeholder="Qué se mueve a partir de esta imagen (inglés recomendado): «locked-off camera; the beam of the lighthouse sweeps slowly; waves crash against the rocks; rain streaks the lens»">${h(t.sugerido || "")}</textarea>
         <div class="row" style="margin-top:8px"><select id="ls-${t.id}" style="max-width:200px">${[["5.167", "5,17 s (seguro)"], ["5.875", "5,88 s"], ["6.583", "6,58 s (riesgo)"], ["7.292", "7,29 s (riesgo)"], ["10.083", "10,08 s (riesgo alto)"], ["12.917", "12,92 s (riesgo alto)"], ["15.083", "15,08 s (el máximo de H3; ~18 min, memoria limpia)"]].map(([v, l]) => `<option value="${v}" ${t.segundos_sugeridos && Math.abs(Number(v) - t.segundos_sugeridos) < 0.01 ? "selected" : ""}>${l}</option>`).join("")}</select>
           <button class="btn s" onclick="libreArmar('${t.id}')" title="convierte lo que escribiste al formato oficial de MiniMax H3 y lo deja en el cuadro para que lo revises">Armar prompt H3</button>
           <button class="btn p" ${lista && !d.ocupada ? "" : "disabled"} onclick="libreVideo('${t.id}')">Generar clip</button>
           <span class="tiny">${!lista ? "encendé la máquina desde el inicio" : d.ocupada ? "hay un turno generando" : ""}</span></div>
         <div class="tiny" style="margin-top:6px">Escribí en castellano lo que pasa y quién dice qué («MONO: Cuéntame.» · «PACIENTE (fuera de cuadro): …»). Al generar, se convierte solo al formato de H3; con «Armar prompt H3» lo ves antes.</div>`}
      ${t.nota && t.estado !== "error" ? `<div class="tiny">${h(t.nota)}</div>` : ""}</div></div></div>`).join("") || `<div class="muted">Nada en curso. Subí una imagen o creá una para empezar.</div>`) + biblioteca;
  clearTimeout(libreTimer);
  if (ts.some(t => t.estado === "generando")) libreTimer = setTimeout(async () => { if (!$("#turnos")) return; const d2 = await api("/libre"); pintarTurnos(d2.turnos, d2); }, 12000);
}
async function libreOtraVez(tid) {
  try { await api(`/libre/${tid}/otra-vez`, {method: "POST", body: {}}); const d = await api("/libre"); pintarTurnos(d.turnos, d); window.scrollTo({top: 0, behavior: "smooth"}); toast("turno nuevo con la misma imagen; el prompt anterior ya está cargado"); }
  catch (e) { toast(e.message, true); }
}
async function libreImagen(b64 = null) {
  $("#lerr").textContent = ""; toast(b64 ? "subiendo…" : "dibujando… (10-20 s)");
  try { await api("/libre/imagen", {method: "POST", body: {prompt: $("#lp").value, aspecto: $("#lasp").value, estilo: $("#lest").value, imagen_b64: b64, motor: $("#lmotor").value, ajuste: $("#lajuste").value}}); navegar(); }
  catch (e) { $("#lerr").textContent = e.message; }
}
async function libreVideo(id) {
  const texto = $(`#lv-${id}`).value;
  const oficial = texto.trim().startsWith("For the target video");
  toast(oficial ? "lanzando…" : "armando el prompt para H3 y lanzando… (15-30 s)");
  try { await api("/libre/video", {method: "POST", body: {id, prompt_video: texto, segundos: Number($(`#ls-${id}`).value)}}); toast("clip lanzado en la máquina"); navegar(); }
  catch (e) { toast(e.message, true); }
}
async function libreArmar(id) {
  const ta = $(`#lv-${id}`);
  toast("armando el prompt oficial de H3… (10-20 s)");
  try {
    const r = await api("/libre/reescribir", {method: "POST", body: {id, texto: ta.value, segundos: Number($(`#ls-${id}`).value)}});
    ta.value = r.prompt; ta.style.minHeight = "260px";
    toast(r.problemas && r.problemas.length ? "prompt armado, con avisos: " + r.problemas[0] : "prompt armado: revisalo y tocá Generar", !!(r.problemas && r.problemas.length));
  } catch (e) { toast(e.message, true); }
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
      ${voz.length ? `<h3 style="margin-top:18px">Voz en off</h3>${voz.map(v => `<div class="muted" style="margin-bottom:6px"><span class="mono tiny">${h(v.plano || "")}</span> ${h(v.texto)}</div>`).join("")}` : ""}
      ${(() => { const pl = (P.proyecto.planos || []).filter(p => !p.clip_de); const con = pl.filter(p => p.prompt_h3).length;
        return `<h3 style="margin-top:18px">Prompts para H3 <span class="pill ${con === pl.length ? "ok" : "warn"}">${con}/${pl.length}</span></h3>
        <p class="tiny">Lo que de verdad recibe MiniMax: cada plano pasa por el reescritor (GPT con la guía oficial de H3, validado). Se rehace solo al empaquetar si hay dibujo nuevo. Si editás uno a mano en el JSON, ponele <span class="mono">"prompt_h3_manual": true</span> para que no se pise.</p>
        ${pl.map(p => `<details style="margin-bottom:6px"><summary class="tiny" style="cursor:pointer"><span class="mono">${p.id}</span> · ${p.prompt_h3 ? h(p.prompt_h3_origen || "") : "<span style='color:var(--warn)'>sin prompt todavía</span>"}</summary>${p.prompt_h3 ? `<div class="tiny mono" style="white-space:pre-wrap;opacity:.85;max-height:260px;overflow:auto;margin-top:4px">${h(p.prompt_h3)}</div>` : ""}</details>`).join("")}
        <div class="row" style="margin-top:8px"><button class="btn s" onclick="reescribirPrompts(false)">Escribir los que faltan</button><button class="btn s" onclick="reescribirPrompts(true)">Rehacer todos</button><span class="tiny">~10 s y centavos por plano</span></div>`; })()}</div>
    <div class="card"><h3>proyecto.json <span class="pill">editable</span></h3>
      <textarea id="pj" class="json" style="min-height:420px">${h(JSON.stringify(P.proyecto, null, 2))}</textarea>
      <div class="row" style="margin-top:10px"><button class="btn p" onclick="guardarProyecto()">Guardar y reconstruir</button><span class="tiny">Se valida al guardar. Cero avisos antes de dibujar.</span></div>
      <div id="err" class="tiny" style="color:var(--bad);margin-top:8px"></div></div></div>`;
}
async function reescribirPrompts(forzar) {
  try { const d = await api(`/proyectos/${P.slug}/reescribir`, {method: "POST", body: {forzar}}); seguirTarea(d.tarea, () => navegar()); toast("escribiendo los prompts de H3…"); }
  catch (e) { toast(e.message, true); }
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
    ${!s.hechos.length && s.instalacion && !s.instalacion.listo ? `<div class="row" style="justify-content:space-between;margin:12px 0 4px"><span class="tiny"><b>instalando H3</b> · ${s.instalacion.gb ?? "?"} de 59 GB${s.instalacion.mbps ? ` · ${s.instalacion.mbps} Mbps` : ""}${s.instalacion.eta_min != null ? ` · faltan ~${s.instalacion.eta_min} min` : ""}</span><span class="tiny">${s.instalacion.pct ?? 0} %</span></div>
      <div class="bar" style="height:12px"><i style="width:${s.instalacion.pct ?? 0}%"></i></div>` : ""}
    <div class="tiny" style="margin-top:12px">clips</div>
    <div class="bar" style="margin:4px 0 6px"><i style="width:${pct}%"></i></div>
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
const fmtDur = s => s == null ? "?" : s >= 60 ? `${Math.floor(s / 60)} min${Math.round(s % 60) ? " " + Math.round(s % 60) + " s" : ""}` : `${Math.round(s)} s`;
ruta("/musica", async ([slug]) => {
  const ps = (await api("/proyectos")).filter(p => String(p.estructura).startsWith("loop"));
  const sel = slug || ps[0]?.slug;
  const bib = await api("/musica/biblioteca");
  let pistas = [];
  const otros = ps.filter(p => p.slug !== sel && (p.estado?.masters || []).some(m => / - loop\.mp4$/.test(m)));
  if (sel) { try { pistas = await api(`/proyectos/${sel}/musica`); } catch {} }
  const p = ps.find(x => x.slug === sel);
  const todas = [...bib.pistas, ...pistas];
  const paso = (n, t, ok) => `<span class="pill ${ok ? "ok" : ""}" style="margin-right:6px">${n} · ${t}</span>`;
  $("#vista").innerHTML = `<div class="wrap"><h1>Music video</h1>
    <p class="sub">Primero la música, después la escena. La app compone la pista con ElevenLabs Music (o subís la tuya), vos describís un lugar, y el video final dura exactamente lo que dura la música: la escena se repite en loop encima.</p>
    <div id="series-seccion"></div>
    <div style="margin-bottom:14px">${paso(1, "música", bib.pistas.length)}${paso(2, "escena", ps.length)}${paso(3, "máquina y clips", p && p.estado.clips.hechos)}${paso(4, "video final", p && p.estado.masters.length)}</div>
    <div class="card" style="margin-bottom:14px"><h3>1 · La música</h3>
        <div class="grid g3" style="gap:12px">
          <div><label class="tiny" style="display:block;margin-bottom:4px">Duración total</label>
            <select id="dur">${[[60, "1 min"], [120, "2 min"], [180, "3 min"], [300, "5 min"], [600, "10 min"], [900, "15 min"], [1200, "20 min"], [1800, "30 min"]].map(([v, l]) => `<option value="${v}" ${v === 180 ? "selected" : ""}>${l}</option>`).join("")}</select>
            <div class="tiny" style="margin-top:4px">Más de 5 min se compone en piezas de hasta 5 min del mismo estilo; cada una baja a silencio al final y la siguiente sube desde silencio.</div></div>
          <div><label class="tiny" style="display:block;margin-bottom:4px">Género</label>
            <select id="genero">${GENEROS_MUSICA.map(([v, l]) => `<option value="${v}">${l}</option>`).join("")}</select>
            <div class="tiny" style="margin-top:4px">Marca el estilo base; lo fino va en la descripción.</div></div>
          <div><label class="tiny" style="display:block;margin-bottom:4px">Voz</label>
            <select id="conletra" onchange="letraToggle()"><option value="no">Instrumental (sin voz)</option><option value="si">Con letra cantada</option></select>
            <label class="tiny" id="loopwrap" style="display:block;margin-top:6px"><input type="checkbox" id="loopeable" checked> sin intro ni final (loopeable)</label></div>
        </div>
        <label class="tiny" style="display:block;margin:12px 0 4px">Descripción · qué tipo de música querés</label>
        <textarea id="tipo" style="min-height:80px" placeholder="Ánimo, instrumentos, tempo, referencias: «lento, para estudiar de noche; piano suave y vinilo; sin batería marcada; melancólico pero cálido; como el canal Lofi Girl»"></textarea>
        <div id="letrabox" hidden style="margin-top:12px;padding:12px;border:1px solid var(--line);border-radius:var(--r2);background:var(--bg2)">
          <div class="row" style="gap:12px;margin-bottom:8px">
            <div><label class="tiny" style="display:block;margin-bottom:4px">Idioma de la letra</label><select id="idioma_letra"><option value="es">Español</option><option value="en">Inglés</option><option value="pt">Portugués</option><option value="it">Italiano</option><option value="fr">Francés</option></select></div>
            <div><label class="tiny" style="display:block;margin-bottom:4px">Quién canta</label><select id="voz_letra"><option value="femenina">Voz femenina</option><option value="masculina">Voz masculina</option><option value="duo">Dúo</option><option value="coro">Coro</option></select></div></div>
          <label class="tiny" style="display:block;margin-bottom:4px">La letra · se canta tal cual, en este orden</label>
          <textarea id="letra" style="min-height:140px;font-family:var(--mono)" placeholder="[Verso 1]
Bajo la lluvia que no para
la ciudad se queda quieta

[Estribillo]
…"></textarea>
          <div class="tiny" style="margin-top:4px">Como guía: 1 minuto de canción son unas 8 a 12 líneas. Si la letra es más larga que la pista, se canta hasta donde llegue.</div></div>
        <div class="row" style="margin-top:12px"><input id="nombre" placeholder="nombre de la pista (opcional)" style="max-width:260px"><button class="btn p" onclick="componer('_musica')">Componer</button><span class="tiny">ElevenLabs Music · 1 a 3 min por cada 5 min de música</span>
          <label class="btn s" style="margin-left:auto">subir mi pista (mp3/wav)<input type="file" id="fpista" accept=".mp3,.wav,audio/*" hidden></label></div>
        ${bib.tareas.length ? `<div class="pill warn" style="margin-top:10px"><i class="dot live"></i> componiendo… ${h(bib.tareas[0].cola || "")}</div>` : ""}
        <div style="margin-top:14px"><div class="tiny" style="margin-bottom:6px">Biblioteca de música ${bib.pistas.length ? `· ${bib.pistas.length} pista${bib.pistas.length > 1 ? "s" : ""}` : ""}</div>
          ${bib.pistas.length ? bib.pistas.map(t => `<div class="row" style="margin-bottom:8px;gap:10px"><audio controls preload="none" src="${t.url}" style="height:30px;flex:1;min-width:220px"></audio><span class="tiny">${h(t.archivo)} · <b>${fmtDur(t.dur)}</b>${t.genero ? " · " + h(t.genero) : ""}${t.con_letra ? " · con letra" : ""}${t.piezas > 1 ? ` · ${t.piezas} piezas` : ""}</span></div>`).join("") : `<div class="tiny">Todavía no hay pistas. Componé una o subí la tuya.</div>`}</div></div>
    <div class="card" style="margin-bottom:14px"><h3>2 · La escena</h3>
        <p class="muted">Un lugar que se mira mientras suena la música. Se dibuja, se anima con H3 y se repite en loop lo que dure la pista.</p>
        <div class="row"><a class="btn p" href="#/nuevo/loop">＋ Nueva escena (la describís en castellano)</a>
          ${ps.length ? `<select id="sel-loop" onchange="location.hash='#/musica/'+this.value" style="max-width:320px">${ps.map(x => `<option value="${x.slug}" ${x.slug === sel ? "selected" : ""}>${h(x.titulo)}</option>`).join("")}</select><span class="tiny">escena elegida</span>` : `<span class="tiny">todavía no hay escenas</span>`}</div></div>
    ${p ? `<div class="grid g2">
      <div class="card"><h3>3 · Máquina y clips <span class="pill ${p.estado.clips.hechos ? "ok" : "warn"}">${p.estado.clips.hechos}/${p.estado.clips.esperados} clips</span></h3>
        <p class="muted">La escena «${h(p.titulo)}» se dibuja y se genera en la máquina como cualquier proyecto: dibujos → máquina → clips. Los clips quedan guardados; el video final se arma sin volver a generar.</p>
        <div class="row"><a class="btn p" href="#/p/${sel}/dibujos">Dibujos</a><a class="btn" href="#/p/${sel}/maquina">Máquina</a><a class="btn" href="#/p/${sel}/clips">Clips</a></div></div>
      <div class="card"><h3>4 · El video final <span class="pill ${p.estado.masters.length ? "ok" : ""}">${p.estado.masters.length ? p.estado.masters.length + " hecho(s)" : "pendiente"}</span></h3>
        <p class="muted">La pista manda la duración: la escena se repite hasta cubrirla y se corta a su largo. Si marcás otras escenas ya hechas, se alternan para que no se vea siempre la misma.</p>
        <label class="tiny" style="display:block;margin-bottom:4px">Pista</label>
        <select id="pista">${todas.map(t => `<option value="${h(t.ruta)}">${h(t.archivo)} · ${fmtDur(t.dur)}</option>`).join("")}${todas.length ? "" : `<option value="">(primero componé o subí una pista)</option>`}</select>
        ${otros.length ? `<div class="tiny" style="margin:10px 0 4px">Alternar con:</div>${otros.map(o => `<label class="tiny" style="display:block"><input type="checkbox" class="otro" value="${o.slug}"> ${h(o.titulo)}</label>`).join("")}` : ""}
        <div class="row" style="margin-top:12px"><button class="btn p" ${todas.length && p.estado.clips.hechos ? "" : "disabled"} onclick="masterMusica('${sel}')">Generar el music video</button>
          <span class="tiny">${!p.estado.clips.hechos ? "faltan los clips de la escena" : !todas.length ? "falta la música" : "tarda ~1 min aunque la pista dure 30"}</span></div>
        <div style="margin-top:12px">${p.estado.masters.map(m => `<div><a href="/api/proyectos/${sel}/archivo/${encodeURIComponent(m)}" target="_blank">${h(m)}</a></div>`).join("")}</div></div>
    </div>` : ""}
    ${ps.length ? `<h3 style="margin:26px 0 10px">Escenas</h3><div class="grid g3">${ps.map(tarjetaProyecto).join("")}</div>` : ""}</div>`;
  $("#conletra") && letraToggle();
  pintarSeriesSeccion("musica");
  $("#fpista").addEventListener("change", async (ev) => {
    const f = ev.target.files[0]; if (!f) return;
    toast("subiendo la pista…");
    const b64 = await new Promise(r => { const fr = new FileReader(); fr.onload = () => r(fr.result); fr.readAsDataURL(f); });
    try { await api("/musica/subir", {method: "POST", body: {nombre: f.name, b64}}); toast("pista guardada en la biblioteca"); navegar(); }
    catch (e) { toast(e.message, true); }
  });
});
const GENEROS_MUSICA = [["lofi", "Lo-fi hip hop"], ["chillhop", "Chillhop"], ["ambient", "Ambient"], ["piano", "Piano solo"], ["jazz", "Jazz suave"],
  ["acustico", "Acústico / folk"], ["clasica", "Clásica de cámara"], ["bossa", "Bossa nova"], ["cinematica", "Cinemática"], ["synthwave", "Synthwave"],
  ["downtempo", "Electrónica downtempo"], ["pop", "Pop"], ["rock", "Rock suave"], ["cumbia", "Cumbia"], ["reggaeton", "Reggaetón"], ["trap", "Trap"],
  ["tango", "Tango"], ["infantil", "Infantil"], ["", "Otro (sólo la descripción)"]];
function letraToggle() {
  const con = $("#conletra").value === "si";
  $("#letrabox").hidden = !con;
  // Una canción con letra tiene principio y final: no se pide loopeable.
  $("#loopwrap").style.opacity = con ? ".4" : "1";
  if (con) $("#loopeable").checked = false;
}
async function componer(slug) {
  const con = $("#conletra").value === "si";
  const body = {slug, tipo: $("#tipo").value, duracion: Number($("#dur").value || 90), genero: $("#genero").value,
    loopeable: !con && $("#loopeable").checked, con_letra: con, letra: con ? $("#letra").value : "",
    idioma_letra: $("#idioma_letra").value, voz_letra: $("#voz_letra").value, nombre: $("#nombre").value || (con ? "cancion" : "musica")};
  const piezas = Math.ceil(body.duracion / 300);
  try { const d = await api("/musica/componer", {method: "POST", body}); seguirTarea(d.tarea, () => navegar()); toast((con ? "componiendo la canción" : "componiendo") + (piezas > 1 ? ` en ${piezas} piezas…` : "…")); setTimeout(navegar, 1200); }
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
