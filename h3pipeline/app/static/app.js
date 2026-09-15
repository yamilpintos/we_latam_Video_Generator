/* La Fábrica · frontend. Sin framework: rutas por hash, fetch a /api, y dos
   librerías por CDN para la portada (Three.js) y las transiciones (GSAP). */

const $ = (s, el = document) => el.querySelector(s);
const h = (s) => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const usd = (x) => x == null ? "—" : "$" + Number(x).toFixed(2);
const mins = (s) => { s = Math.round(s || 0); return s < 90 ? `${s} s` : `${Math.floor(s / 60)} min ${s % 60 ? (s % 60) + " s" : ""}`.trim(); };
const fmtHora = (t) => new Date(t * 1000).toLocaleTimeString("es-AR", {hour: "2-digit", minute: "2-digit"});

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
  const n = (f) => ps.filter(p => f(p)).length;
  const masters = ps.reduce((s, p) => s + (p.estado?.masters?.length || 0), 0);
  $("#vista").innerHTML = `
  <section class="hero">
    <h1>Videos con IA,<br>de la idea al <span>máster</span>.</h1>
    <p class="lead">Guion, dibujos, GPU alquilada por hora, control de calidad y mezcla. Cada paso muestra lo que cuesta antes de gastarlo.</p>
    <div class="puertas">
      <div class="puerta" onclick="location.hash='#/nuevo/short'"><span class="k">VERTICAL · 15 A 90 S</span><h2>Short</h2>
        <p>Voz en off, subtítulos quemados y música. Tres clips para una muestra de 15 s; doce para un minuto.</p><span class="n">${n(p => p.formato === "short" && !String(p.estructura).startsWith("loop") && !String(p.estructura).startsWith("recap"))} proyectos</span></div>
      <div class="puerta" onclick="location.hash='#/nuevo/largo'"><span class="k">VERTICAL · 3 A 8 MIN</span><h2>Largo</h2>
        <p>Recap con voz continua a ritmo de TTS. Primero el audio, medido; después los planos que lo sirven.</p><span class="n">${n(p => String(p.estructura).startsWith("recap"))} proyectos</span></div>
      <div class="puerta dim" onclick="location.hash='#/musica'"><span class="badge pill ac">en preparación</span><span class="k">16:9 · LOOP</span><h2>Music video</h2>
        <p>Un escenario que se mira de fondo y se repite lo que dure la música. La música llega de un módulo aparte.</p><span class="n">${n(p => String(p.estructura).startsWith("loop"))} loops</span></div>
    </div>
    <div class="stats"><div><b>${ps.length}</b>proyectos</div><div><b>${masters}</b>másters</div><div><b>5,17 s</b>por clip, sin excepción</div><div><b>4× 5090</b>verificada o se espera</div></div>
  </section>`;
});

/* ─────────────────────────────────────────────── proyectos */
ruta("/proyectos", async () => {
  const ps = await api("/proyectos");
  $("#vista").innerHTML = `<div class="wrap"><h1>Proyectos</h1><p class="sub">Cada uno es una carpeta en <code>mis-videos/</code>. El estado sale de lo que existe en la carpeta.</p>
    <div class="row" style="margin-bottom:16px"><a class="btn p" href="#/nuevo/short">＋ Nuevo</a></div>
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
  </div>`;
}

/* ─────────────────────────────────────────────── nuevo proyecto */
ruta("/nuevo", async ([formato]) => {
  const ests = await api("/estructuras");
  const f = formato || "short";
  $("#vista").innerHTML = `<div class="wrap"><h1>Nuevo ${f === "largo" ? "largo" : "short"}</h1>
    <p class="sub">El flujo es el de siempre: la Mesa de Armado te da la instrucción para el LLM; el LLM te devuelve el <code>proyecto.json</code>; lo pegás acá.</p>
    <div class="grid g2">
      <div class="card"><h3>1 · La idea</h3><p class="muted">Abrí la Mesa de Armado, elegí formato y estructura, cargá la idea y el estilo, y copiá la instrucción que genera. Pegásela a tu LLM.</p>
        <a class="btn p" href="/mesa" target="_blank">Abrir la Mesa de Armado ↗</a>
        <div class="tiny" style="margin-top:12px">Estructuras disponibles: ${ests.map(e => `<code>${e.nombre}</code>`).join(" · ")}</div></div>
      <div class="card"><h3>2 · El proyecto</h3><p class="muted">Pegá el JSON que devolvió el LLM. Se valida al guardar; después se construye hasta cero avisos.</p>
        <textarea id="json" class="json" placeholder='{ "titulo": "...", "formato": "${f}", "estructura": "...", "planos": [ ... ] }'></textarea>
        <div class="row" style="margin-top:10px"><input id="slug" placeholder="carpeta (opcional, ej. mi-video)" style="max-width:260px"><button class="btn p" onclick="guardarNuevo()">Guardar y construir</button></div>
        <div id="err" class="tiny" style="color:var(--bad);margin-top:8px"></div></div>
    </div></div>`;
});
async function guardarNuevo() {
  let pj; try { pj = JSON.parse($("#json").value); } catch (e) { $("#err").textContent = "JSON inválido: " + e.message; return; }
  try {
    const d = await api("/proyectos", {method: "POST", body: {proyecto: pj, slug: $("#slug").value || null}});
    await api(`/proyectos/${d.slug}/construir`, {method: "POST"});
    location.hash = `#/p/${d.slug}`;
  } catch (e) { $("#err").textContent = e.message; }
}

/* ─────────────────────────────────────────────── el proyecto: los pasos */
let P = null;     // el proyecto abierto
let pasoActual = null;
ruta("/p", async ([slug, paso]) => {
  P = await api(`/proyectos/${slug}`);
  const e = P.estado;
  const hechos = {
    proyecto: P.avisos.length === 0,
    dibujos: e.assets.hechos === e.assets.esperados && e.assets.esperados > 0,
    maquina: e.clips.hechos === e.clips.esperados && e.clips.esperados > 0,
    clips: e.clips.hechos === e.clips.esperados && e.clips.esperados > 0,
    master: e.masters.length > 0,
  };
  pasoActual = paso || (!hechos.proyecto ? "proyecto" : !hechos.dibujos ? "dibujos" : !hechos.maquina ? "maquina" : !hechos.master ? "clips" : "master");
  const pasos = [["proyecto", "Proyecto"], ["dibujos", "Dibujos"], ["maquina", "Máquina"], ["clips", "Clips"], ["master", "Máster"]];
  $("#vista").innerHTML = `<div class="wrap">
    <div class="row" style="justify-content:space-between"><div><h1>${h(P.titulo)}</h1>
      <p class="sub">${P.formato === "largo" ? "16:9" : "9:16"} · ${h(P.estructura)} · ${P.planos.length} planos · ${mins(e.segundos)} generados ${P.negativos === false ? "· sin negativos" : ""}</p></div>
      <div class="row">${e.corrida && !e.corrida.fin ? `<span class="pill warn"><i class="dot live"></i> instancia ${e.corrida.instancia} · ${usd(e.corrida.acumulado)}</span>` : ""}${e.corrida?.gasto_final != null ? `<span class="pill">GPU gastada ${usd(e.corrida.gasto_final)}</span>` : ""}</div></div>
    <div class="pasos">${pasos.map(([k, n], i) => `<div class="paso ${k === pasoActual ? "on" : ""} ${hechos[k] ? "done" : ""}" onclick="location.hash='#/p/${slug}/${k}'"><b>${hechos[k] ? "✓" : i + 1}</b>${n}</div>`).join("")}</div>
    <div id="paso"></div></div>`;
  await ({proyecto: pasoProyecto, dibujos: pasoDibujos, maquina: pasoMaquina, clips: pasoClips, master: pasoMaster}[pasoActual])();
});

function lineaDeTiempo() {
  const total = Math.max(1, ...P.planos.map(p => p.hasta));
  return `<div class="tl">${P.tramos.map(t => `<div class="t" style="left:${t.desde / total * 100}%">${h(t.id)}</div>`).join("")}
    ${P.planos.map(p => `<div class="p" title="${h(p.funcion)}" style="left:${p.desde / total * 100}%;width:${Math.max(.5, (p.hasta - p.desde) / total * 100 - .3)}%">${p.id}</div>`).join("")}</div>
    <div class="tiny">${mins(total)} en la línea de tiempo · los tramos punteados son la estructura <code>${h(P.estructura)}</code></div>`;
}

async function pasoProyecto() {
  const av = P.avisos;
  $("#paso").innerHTML = `<div class="grid g2">
    <div class="card" style="grid-column:1/-1"><h3>Línea de tiempo <span class="pill ${av.length ? "warn" : "ok"}">${av.length ? av.length + " aviso(s)" : "sin avisos"}</span></h3>${lineaDeTiempo()}
      ${av.length ? `<div class="pre" style="margin-top:10px;max-height:160px">${av.map(h).join("\n")}</div>` : ""}</div>
    <div class="card"><h3>Planos</h3><table><tr><th>id</th><th>tipo</th><th>tramo</th><th class="num">genera</th><th class="num">en línea</th><th>función</th></tr>
      ${P.planos.map(p => `<tr><td class="mono">${p.id}${p.clip_de ? ` <span class="tiny">= ${p.clip_de}</span>` : ""}</td><td>${p.tipo}</td><td class="tiny">${h(p.tramo || "")}</td><td class="num">${p.segundos.toFixed(2)}</td><td class="num">${p.desde.toFixed(1)}–${p.hasta.toFixed(1)}</td><td class="tiny">${h(p.funcion)}</td></tr>`).join("")}</table></div>
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

async function pasoDibujos() {
  const as = await api(`/proyectos/${P.slug}/assets`);
  const faltan = as.filter(a => !a.existe).length, barras = as.filter(a => a.con_barras).length;
  const vertical = P.formato === "short";
  $("#paso").innerHTML = `<div class="card" style="margin-bottom:14px"><h3>Dibujos ${as.length - faltan}/${as.length}
      <span class="pill ${faltan ? "warn" : barras ? "bad" : "ok"}">${faltan ? faltan + " faltan" : barras ? barras + " con barras" : "todos listos"}</span></h3>
    <div class="row"><button class="btn p" onclick="dibujar([])">${faltan ? "Dibujar los que faltan" : "Dibujar (nada nuevo)"}</button>
      <button class="btn" onclick="rehacerMarcados()">Rehacer los marcados</button>
      <button class="btn" ${faltan ? "disabled" : ""} onclick="empaquetar()">Empaquetar ZIP ${P.estado.zip ? `(${P.estado.zip_mb} MB, ya existe)` : ""}</button>
      <span class="tiny">~$0,04 por dibujo · se revisan TODOS antes de empaquetar · el detector marca letterbox</span></div></div>
    <div class="thumbs">${as.map(a => `<div class="th ${vertical && a.tipo === "plano" ? "v" : ""} ${a.existe ? "" : "falta"}">
      <img src="${a.existe ? a.url : ""}" onclick="${a.existe ? `lightbox('${a.url}')` : ""}" alt="">
      <div class="c"><input type="checkbox" class="rh" value="${a.id}" title="marcar para rehacer"><b>${a.id}</b>${a.plano ? `<span>${a.plano}</span>` : `<span>${a.tipo}</span>`}
        ${a.con_barras ? `<span class="pill bad">barras</span>` : ""}</div>
      ${a.funcion ? `<div class="tiny" style="padding:0 10px 8px">${h(a.funcion)}</div>` : ""}</div>`).join("")}</div>`;
}
async function dibujar(rehacer) {
  try {
    const d = await api(`/proyectos/${P.slug}/frames`, {method: "POST", body: {madre: true, motor: "nanobanana", rehacer}});
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
  $("#paso").innerHTML = `<div class="grid g2">
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
      <button class="btn d" onclick="destruir(${c.instancia})">Destruir instancia</button>
      <button class="btn s" onclick="pintarInstancia()">actualizar</button><code class="tiny">${h(s.ssh || "")}</code></div>
    <details style="margin-top:10px"><summary class="tiny">log de la máquina</summary><div class="pre">${h(s.logs)}</div></details>`;
  clearTimeout(seguimiento); seguimiento = setTimeout(() => { if (location.hash.includes("/maquina")) pintarInstancia(); }, 20000);
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
    <div class="card"><h3>Máster</h3><p class="muted">${loop ? "Loop: 5,0 s de cada clip, 1080p, −14 LUFS y el «×3» para mirar el empalme. La música entra como archivo." : "Corte por <code>usa</code>, tres capas con ducking, −14 LUFS y subtítulos quemados."}</p>
      ${loop ? `<input id="musica" placeholder="ruta de la pista (mp3/wav), opcional"><div class="row" style="margin-top:8px"><input id="repite" type="number" min="0" placeholder="repetir N veces (opcional)" style="max-width:220px"></div>` : ""}
      <div class="row" style="margin-top:12px"><button class="btn p" ${e.clips.hechos ? "" : "disabled"} onclick="masterizar()">Generar máster</button></div></div>
    <div class="card"><h3>Archivos</h3>${e.masters.length ? e.masters.map(m => `<div class="row" style="margin-bottom:8px"><a href="/api/proyectos/${P.slug}/archivo/${encodeURIComponent(m)}" target="_blank">${h(m)}</a></div>`).join("") : `<div class="muted">Todavía no hay máster.</div>`}
      ${e.masters.length ? `<video controls style="width:100%;border-radius:10px;margin-top:8px" src="/api/proyectos/${P.slug}/archivo/${encodeURIComponent(e.masters[0])}"></video>` : ""}</div></div>`;
}
async function masterizar() {
  const body = {musica: $("#musica")?.value || null, repite: Number($("#repite")?.value || 0)};
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
ruta("/musica", async () => {
  const ps = (await api("/proyectos")).filter(p => String(p.estructura).startsWith("loop"));
  $("#vista").innerHTML = `<div class="wrap"><h1>Music video <span class="pill ac">en preparación</span></h1>
    <p class="sub">Un escenario que se mira de fondo y se repite lo que dure la música. Los loops se hacen acá con el mismo flujo; la música llega de un módulo aparte que está en desarrollo.</p>
    <div class="grid g2"><div class="card"><h3>Cómo se conecta</h3><p class="muted">El módulo de música entrega un archivo de audio de la duración pedida. El máster del loop lo recibe con <code>--musica</code>, cierra la vuelta con un cruce de 2 s y masteriza a −14 LUFS. Cuando el módulo esté, este botón lo llama; hoy acepta una ruta de archivo en el paso Máster de cada loop.</p>
      <a class="btn" href="#/nuevo/largo">Nuevo loop (estructura <code>loop</code>)</a></div>
    <div class="card"><h3>Lo que falta</h3><ul class="muted" style="margin:0;padding-left:18px"><li>Que la pista mande la duración (<code>--largo-de-pista</code>).</li><li>Varios loops de 15 s que se alternan (tríos), para que una canción de 3 min no repita el mismo doce veces.</li><li>El módulo de generación de música (rama <code>hosting-y-musica</code>).</li></ul></div></div>
    <h3 style="margin:26px 0 10px">Loops hechos</h3><div class="grid g3">${ps.map(tarjetaProyecto).join("") || `<div class="muted">Ninguno todavía.</div>`}</div></div>`;
});

/* ─────────────────────────────────────────────── fondo 3D */
(function fondo() {
  if (!window.THREE) return;
  const canvas = $("#bg3d");
  const renderer = new THREE.WebGLRenderer({canvas, antialias: true, alpha: true});
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  const scene = new THREE.Scene();
  const cam = new THREE.PerspectiveCamera(55, 1, .1, 100); cam.position.set(0, 0, 9);
  // Un anillo de "fotogramas": planos finos girando lento, como una tira de película en órbita.
  const grupo = new THREE.Group(); scene.add(grupo);
  const geo = new THREE.PlaneGeometry(1.2, .68);
  for (let i = 0; i < 48; i++) {
    const t = i / 48 * Math.PI * 2, r = 4.2 + Math.sin(i * 1.7) * .5;
    const m = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({color: i % 5 ? 0x2a3350 : 0xffb454, transparent: true, opacity: i % 5 ? .55 : .8, side: THREE.DoubleSide, wireframe: i % 3 === 0}));
    m.position.set(Math.cos(t) * r, Math.sin(t * 2) * .9 + Math.sin(i) * .3, Math.sin(t) * r);
    m.lookAt(0, m.position.y, 0); grupo.add(m);
  }
  // Polvo
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
    const enPortada = document.body.classList.contains("en-portada");
    canvas.style.opacity = enPortada ? .9 : .28;
    renderer.render(scene, cam); requestAnimationFrame(loop);
  })();
})();

estadoVast();
navegar();
