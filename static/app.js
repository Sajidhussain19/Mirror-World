/* Mirror World front-end — vanilla JS, no build step. */
const $ = (s, el = document) => el.querySelector(s);
const COLORS = { "-2": "#ff4d61", "-1": "#ff9a62", "0": "#6f7a90", "1": "#6fd6a0", "2": "#25e89a" };
const IDLE = "#2a3448";
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pct = (x) => (x == null ? "—" : Math.round(x * 100) + "%");
const sgn = (x) => (x > 0 ? "+" : "") + x.toFixed(2);

const S = {
  cfg: null, audience: "urban_online", runId: null, es: null, agents: [], byId: new Map(), st: new Map(),
  hist: new Map(), history: [], final: null, report: null, links: [], pulses: [], rounds: 3, round: 0,
  cohort: 0, seen: 0, finals: {}, parentId: null, backtestId: null, segDim: "Income", usage: null, mode: "demo",
};

/* ---------------- boot ---------------- */
async function boot() {
  S.cfg = await (await fetch("/api/config")).json();
  S.mode = S.cfg.mode;
  const mb = $("#modeBadge");
  mb.textContent = S.mode === "live" ? "Live · Nebius Token Factory" : "Demo mode · offline engine";
  mb.className = "badge " + S.mode;
  const auds = $("#audiences");
  for (const [k, v] of Object.entries(S.cfg.audiences)) {
    const b = document.createElement("button");
    b.className = "chip" + (k === S.audience ? " on" : "");
    b.textContent = v; b.dataset.k = k;
    b.onclick = () => setAudience(k);
    auds.append(b);
  }
  $("#size").max = S.cfg.max_agents;
  for (const ex of S.cfg.examples) {
    const b = document.createElement("button");
    b.className = "item"; b.innerHTML = `<span>${esc(ex.title)}</span><small>${esc(S.cfg.audiences[ex.audience])}</small>`;
    b.onclick = () => { $("#proposal").value = ex.proposal; setAudience(ex.audience); S.backtestId = null; start(); };
    $("#examples").append(b);
  }
  for (const bt of S.cfg.backtests) {
    const b = document.createElement("button");
    b.className = "item"; b.innerHTML = `<span>${esc(bt.title)}</span><small>${esc(bt.date)}</small>`;
    b.onclick = () => { $("#proposal").value = bt.proposal; setAudience(bt.audience); S.backtestId = bt.id; start(); };
    $("#backtests").append(b);
  }
  if (!S.cfg.tavily) { $("#news").checked = false; $("#news").parentElement.title = "Set TAVILY_API_KEY to enable"; }
  $("#size").oninput = (e) => ($("#sizeVal").textContent = e.target.value);
  $("#rounds").oninput = (e) => ($("#roundsVal").textContent = e.target.value);
  $("#runBtn").onclick = () => { S.backtestId = null; start(); };
  $("#proposal").addEventListener("keydown", (e) => { if ((e.metaKey || e.ctrlKey) && e.key === "Enter") { S.backtestId = null; start(); } });
  $("#engineBtn").onclick = () => { renderEngine(); $("#engine").hidden = false; };
  $("#engineX").onclick = () => ($("#engine").hidden = true);
  $("#drawerX").onclick = () => ($("#drawer").hidden = true);
  for (const d of ["#engine", "#drawer"]) $(d).addEventListener("click", (e) => { if (e.target === $(d)) $(d).hidden = true; });
  $("#askForm").onsubmit = ask;
  await loadMap();
  requestAnimationFrame(draw);
}
function setAudience(k) {
  S.audience = k;
  document.querySelectorAll("#audiences .chip").forEach((c) => c.classList.toggle("on", c.dataset.k === k));
}

/* ---------------- run ---------------- */
async function start(opts = {}) {
  const proposal = (opts.proposal ?? $("#proposal").value).trim();
  if (proposal.length < 10) { $("#proposal").focus(); return; }
  $("#runBtn").disabled = true;
  if (!opts.parentId) S.parentId = null;
  const body = { proposal, audience: S.audience, size: +$("#size").value, rounds: +$("#rounds").value,
    use_news: $("#news").checked, backtest_id: S.backtestId, parent_id: opts.parentId || null };
  let res;
  try {
    res = await fetch("/api/run", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
    if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
  } catch (e) { setPhase("⚠ " + e.message); $("#runBtn").disabled = false; return; }
  const { run_id } = await res.json();
  reset(); S.runId = run_id; S.parentId = opts.parentId || null;
  if (S.es) S.es.close();
  S.es = new EventSource(`/api/run/${run_id}/events`);
  S.es.onmessage = (m) => onEvent(JSON.parse(m.data));
  S.es.onerror = () => { if (S.done) S.es.close(); };
}
function reset() {
  S.st.clear(); S.hist.clear(); S.history = []; S.final = null; S.report = null; S.links = []; S.pulses = []; S.done = false;
  S.seen = 0; S.round = 0;
  $("#feed").innerHTML = ""; $("#themes").innerHTML = ""; $("#segments").innerHTML = "";
  $("#verdict").innerHTML = `<div class="lbl">Verdict · Nemotron Ultra</div><div class="skeleton">Waiting for the society to finish talking…</div>`;
  $("#backtestCard").hidden = true; $("#abCard").hidden = true; $("#newsCard").hidden = true;
  $("#results").hidden = false;
  setKpis(null); $("#spark").innerHTML = "";
}
function setPhase(t, live = true) { $("#phase").innerHTML = (live ? '<span class="pulse"></span>' : "") + esc(t); }

function onEvent(e) {
  switch (e.type) {
    case "init":
      S.agents = e.agents; S.byId = new Map(e.agents.map((a) => [a.id, a])); S.rounds = e.rounds;
      S.initInfo = e; layoutAgents();
      setPhase(e.cached ? "Replaying a saved simulation…" : `Spawning ${e.agents.length} people · ${e.audience_label}`);
      break;
    case "phase":
      setPhase(e.label);
      if (e.phase === "round") { S.round = e.round; S.cohort = e.cohort; S.seen = 0; }
      progress();
      break;
    case "news": showNews(e); break;
    case "agent": onAgent(e); break;
    case "metrics":
      S.history.push(e); S.final = e; setKpis(e); spark(); renderSegments(); progress(); break;
    case "themes": renderThemes(e.themes || []); break;
    case "report": S.report = e; renderReport(e); break;
    case "usage": S.usage = e; if (!$("#engine").hidden) renderEngine(); break;
    case "error": setPhase("⚠ " + e.message, false); break;
    case "done":
      S.done = true; S.es && S.es.close(); $("#runBtn").disabled = false;
      if (S.final) S.finals[S.runId] = { final: S.final, proposal: S.initInfo.proposal };
      if (!S.report) break;
      setPhase(`Done · ${S.agents.length} people · ${S.history.length} rounds of word-of-mouth`, false);
      $("#progress i").style.width = "100%";
      if (S.parentId && S.finals[S.parentId]) renderAB();
      break;
  }
}

function onAgent(e) {
  const prev = S.st.get(e.id);
  S.st.set(e.id, e);
  if (!S.hist.has(e.id)) S.hist.set(e.id, []);
  S.hist.get(e.id).push(e);
  S.seen++;
  const a = S.byId.get(e.id);
  if (!a) return;
  const now = performance.now();
  S.pulses.push({ id: e.id, born: now });
  for (const f of e.from || []) S.links.push({ a: f, b: e.id, born: now, c: COLORS[S.st.get(f)?.stance ?? 0] });
  if (S.links.length > 900) S.links.splice(0, S.links.length - 900);
  if (S.seen % 3 === 0 || e.round > 0) {
    const changed = prev && prev.stance !== e.stance;
    if (e.round === 0 || changed) addVoice(a, e, changed ? prev.stance : null);
  }
  if (S.seen % 10 === 0) progress();
}
function addVoice(a, e, from) {
  const d = document.createElement("div");
  d.className = "voice"; d.style.setProperty("--c", COLORS[e.stance]);
  d.innerHTML = `<div class="who">${esc(a.name)}, ${a.age} · ${esc(a.occupation)} · ${esc(a.place)}${from != null ? `<span class="chg">changed ${sgn(from).replace(".00", "")}→${sgn(e.stance).replace(".00", "")}</span>` : ""}</div>${esc(e.quote)}`;
  d.onclick = () => openPerson(a.id);
  const f = $("#feed"); f.prepend(d);
  while (f.children.length > 60) f.lastChild.remove();
  $("#voiceCount").textContent = `${S.st.size} heard`;
}
function progress() {
  const per = 1 / S.rounds;
  const inRound = S.cohort ? Math.min(1, S.seen / S.cohort) : 0;
  const p = Math.min(0.92, (S.round + inRound) * per * 0.92);
  $("#progress i").style.width = (p * 100).toFixed(1) + "%";
}

/* ---------------- KPIs ---------------- */
function setKpis(m) {
  if (!m) { $("#kNet").textContent = "—"; $("#kAdopt").textContent = "—"; $("#kViral").textContent = "—"; $("#gNeedle").style.left = "50%";
    for (const c of ["o", "n", "s"]) $(`#split .${c}`).style.width = "0"; return; }
  $("#kNet").textContent = sgn(m.net_sentiment);
  $("#kNet").style.color = COLORS[Math.max(-2, Math.min(2, Math.round(m.net_sentiment * 1.6)))];
  $("#kAdopt").textContent = pct(m.adoption); $("#kViral").textContent = pct(m.virality);
  $("#gNeedle").style.left = ((m.net_sentiment + 2) / 4 * 100) + "%";
  $("#split .o").style.width = pct(m.oppose); $("#split .n").style.width = pct(m.neutral); $("#split .s").style.width = pct(m.support);
  $("#pO").textContent = "Against " + pct(m.oppose); $("#pN").textContent = "Neutral " + pct(m.neutral); $("#pS").textContent = "For " + pct(m.support);
}
function spark() {
  const H = S.history; if (!H.length) return;
  const W = 300, Hh = 70, pad = 10;
  const x = (i) => H.length === 1 ? W / 2 : pad + (i * (W - 2 * pad)) / (H.length - 1);
  const yS = (v) => Hh - pad - ((v + 2) / 4) * (Hh - 2 * pad);
  const yP = (v) => Hh - pad - v * (Hh - 2 * pad);
  const line = (fn, key) => H.map((h, i) => `${i ? "L" : "M"}${x(i)},${fn(h[key])}`).join("");
  $("#spark").innerHTML = `<line x1="0" x2="${W}" y1="${yS(0)}" y2="${yS(0)}" stroke="#283349" stroke-dasharray="3 3"/>
    <path d="${line(yP, "adoption")}" fill="none" stroke="#8b7cff" stroke-width="2"/>
    <path d="${line(yS, "net_sentiment")}" fill="none" stroke="#76b900" stroke-width="2.5"/>
    ${H.map((h, i) => `<circle cx="${x(i)}" cy="${yS(h.net_sentiment)}" r="3.5" fill="#76b900"/>`).join("")}
    <text x="6" y="12" fill="#76b900" font-size="9" font-family="JetBrains Mono">net sentiment</text>
    <text x="90" y="12" fill="#8b7cff" font-size="9" font-family="JetBrains Mono">would go along</text>`;
}

/* ---------------- segments / themes / report ---------------- */
function renderSegments() {
  const segs = S.final?.segments; if (!segs) return;
  const tabs = $("#segTabs");
  tabs.innerHTML = Object.keys(segs).map((k) => `<button class="tab ${k === S.segDim ? "on" : ""}" data-k="${k}">${k}</button>`).join("");
  tabs.querySelectorAll(".tab").forEach((b) => (b.onclick = () => { S.segDim = b.dataset.k; renderSegments(); }));
  const parent = S.parentId && S.finals[S.parentId]?.final?.segments?.[S.segDim];
  $("#segments").innerHTML = (segs[S.segDim] || []).map((s) => {
    const w = Math.abs(s.net) / 2 * 50, left = s.net >= 0 ? 50 : 50 - w;
    const c = COLORS[Math.max(-2, Math.min(2, Math.round(s.net * 1.6)))];
    const ps = parent && parent.find((p) => p.label === s.label);
    const ghost = ps ? `<s style="left:calc(${(ps.net + 2) / 4 * 100}% - 1px);opacity:.45" title="before: ${sgn(ps.net)}"></s>` : "";
    return `<div class="seg"><span>${esc(s.label)} <span class="muted" style="font-size:11px">n=${s.n}</span></span>
      <div class="bar"><i style="left:${left}%;width:${w}%;background:${c}"></i>${ghost}</div>
      <span class="n" style="color:${c}">${sgn(s.net)}</span><span class="a">${pct(s.adoption)}</span></div>`;
  }).join("") + `<div class="muted" style="font-size:11px;margin-top:4px">Bar = net sentiment (−2…+2) · right column = would go along${parent ? " · white tick = before rewrite" : ""}</div>`;
}
function renderThemes(themes) {
  const c = { negative: "var(--s-2)", positive: "var(--s2)", mixed: "var(--s0)" };
  $("#themes").innerHTML = themes.map((t) => `<div class="theme" style="--c:${c[t.sentiment] || "var(--s0)"}">
     <div class="pct">${t.share_pct ?? ""}%</div><h4>${esc(t.label)}</h4><div class="who">${esc(t.who)}</div><q>${esc(t.quote)}</q></div>`).join("");
}
function showNews(e) {
  $("#newsCard").hidden = false;
  $("#newsList").innerHTML = (e.bullets || []).map((b) => `<li>${esc(b)}</li>`).join("");
  $("#newsSrc").innerHTML = (e.sources || []).map((s) => `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.title.slice(0, 70))}</a>`).join("");
}
function renderReport(r) {
  const labels = S.cfg.outcome_labels;
  const drv = (r.drivers || []).map((d) => `<div class="drv"><span class="d ${d.direction === "+" ? "p" : "m"}">${d.direction === "+" ? "+" : "−"}</span>
     <span><b>${esc(d.factor)}.</b> <span class="muted">${esc(d.explanation)}</span></span></div>`).join("");
  const risk = (r.segments_at_risk || []).map((s) => `<li><b>${esc(s.segment)}</b>: <span class="muted">${esc(s.why)}</span></li>`).join("");
  $("#verdict").innerHTML = `<div class="lbl">Verdict · Nemotron Ultra</div>
    <span class="pred ${esc(r.prediction)}">${esc(labels[r.prediction] || r.prediction)} · ${r.confidence ?? "?"}% confident</span>
    <h2>${esc(r.headline)}</h2><p class="muted">${esc(r.summary)}</p>
    <div class="drivers">${drv}</div>
    ${risk ? `<div class="callout"><div class="lbl">Segments at risk</div><ul style="margin:0;padding-left:18px">${risk}</ul></div>` : ""}
    ${r.say_do_gap ? `<div class="callout"><div class="lbl">Say vs do</div>${esc(r.say_do_gap)}</div>` : ""}
    ${r.surprise ? `<div class="callout"><div class="lbl">Non-obvious insight</div>${esc(r.surprise)}</div>` : ""}
    <div class="callout rewrite"><div class="lbl">The one change most likely to flip it</div><b>${esc(r.fix)}</b>
      <p class="muted">${esc(r.rewrite)}</p>
      <button class="primary small" id="rerunBtn">Rerun the same society with this version →</button></div>`;
  $("#rerunBtn").onclick = () => {
    const parent = S.runId; $("#proposal").value = r.rewrite; S.backtestId = null;
    start({ proposal: r.rewrite, parentId: parent }); window.scrollTo({ top: 0, behavior: "smooth" });
  };
  if (r.backtest) renderBacktest(r);
}
function renderBacktest(r) {
  const b = r.backtest, L = S.cfg.outcome_labels;
  const mark = (ok) => `<span class="${ok ? "ok" : "bad"}">${ok ? "✓" : "✗"}</span>`;
  $("#backtestCard").hidden = false;
  $("#backtestCard").innerHTML = `<div class="big ${b.match_sim ? "ok" : "bad"}">${b.match_sim ? "✓" : "✗"}</div>
    <div><div class="lbl">Backtest · ${esc(S.initInfo.date)}</div>
      <div class="vs">
        <div class="col"><div class="lbl">What the society did</div><div class="res">${mark(b.match_sim)} ${esc(L[r.sim_outcome] || r.sim_outcome)}</div></div>
        <div class="col"><div class="lbl">Nemotron Ultra's verdict</div><div class="res">${mark(b.match_ultra)} ${esc(L[r.prediction] || r.prediction)}</div></div>
        <div class="col"><div class="lbl">What actually happened</div><div class="res">${esc(L[b.actual])}</div></div></div>
      <p class="muted" style="margin:8px 0 0">${esc(b.actual_text)}</p></div>
    <div class="muted" style="font-size:11px;max-width:210px">Agents were told the date and only knew what people knew then. The real outcome was hidden from every model. "What the society did" is computed from the agents' own behaviour, and Ultra's verdict is its own read of the same data.</div>`;
}
function renderAB() {
  const A = S.finals[S.parentId].final, B = S.final;
  const cell = (label, a, b, fmt, inv = false) => {
    const d = b - a, up = inv ? d < 0 : d > 0;
    return `<div class="ab-cell"><div class="k-l">${label}</div><div class="v">${fmt(b)}<span class="delta ${up ? "up" : "down"}">${d >= 0 ? "▲" : "▼"} ${fmt === sgn ? Math.abs(d).toFixed(2) : Math.abs(Math.round(d * 100)) + "pts"}</span></div><div class="muted" style="font-size:12px">before: ${fmt(a)}</div></div>`;
  };
  $("#abCard").hidden = false;
  $("#abCard").innerHTML = `<div class="lbl">A/B · same ${S.agents.length} people, rewritten proposal</div>
    <div class="ab-grid">${cell("Net sentiment", A.net_sentiment, B.net_sentiment, sgn)}${cell("Would go along", A.adoption, B.adoption, pct)}
    ${cell("Against", A.oppose, B.oppose, pct, true)}${cell("Would spread it", A.virality, B.virality, pct)}</div>`;
  renderSegments();
}

/* ---------------- engine room ---------------- */
function renderEngine() {
  const u = S.usage;
  const models = S.initInfo?.models || S.cfg.models;
  const role = { nano: "Persona reactions, word-of-mouth, interviews", super: "News briefs, theme mining", ultra: "Verdict, root causes, rewrite (thinking on)", search: "Live news grounding" };
  const rows = ["nano", "super", "ultra", "search"].map((t) => {
    const s = u?.tiers?.[t] || {};
    return `<div class="eng-row"><div class="tier">${t}</div><div><div class="model">${esc(t === "search" ? "Tavily Search API" : models?.[t] || "—")}</div>
      <div class="muted" style="font-size:12px">${role[t]}</div>
      <div class="stats"><span><b>${s.calls ?? 0}</b> calls</span><span><b>${((s.prompt_tokens || 0) + (s.completion_tokens || 0)).toLocaleString()}</b> tokens</span>
      <span><b>${s.avg_latency ?? 0}s</b> avg</span><span><b>${s.errors ?? 0}</b> retries</span></div></div></div>`;
  }).join("");
  $("#engineBody").innerHTML = rows + `<div class="eng-total"><div><span class="muted">Total tokens</span><b>${(u?.total_tokens || 0).toLocaleString()}</b></div>
    <div><span class="muted">Throughput</span><b>${(u?.tokens_per_sec || 0).toLocaleString()} tok/s</b></div><div><span class="muted">Wall time</span><b>${u?.elapsed ?? 0}s</b></div></div>
    ${S.mode !== "live" ? `<p class="muted" style="margin-top:14px">Demo mode: set NEBIUS_API_KEY to run on Token Factory.</p>` : ""}`;
}

/* ---------------- interview ---------------- */
let chatHist = [];
function openPerson(id) {
  const a = S.byId.get(id); if (!a) return;
  S.talkTo = id; chatHist = [];
  $("#pCard").innerHTML = `<div class="pc-name">${esc(a.name)}, ${a.age}</div>
    <div class="pc-meta">${esc(a.occupation)} · ${esc(a.place)}, ${esc(a.state)} · ${a.urban ? "Urban" : "Rural"} · ${esc(a.income)}/month · speaks ${esc(a.language)}</div>
    <div class="pc-tags"><span>price sensitivity: ${esc(a.price_sensitivity)}</span><span>tech: ${esc(a.tech_comfort)}</span><span>${a.nb.length} contacts</span></div>`;
  $("#pHist").innerHTML = (S.hist.get(id) || []).map((h) => `<div class="h" style="--c:${COLORS[h.stance]}"><small>Round ${h.round + 1} · stance ${sgn(h.stance).replace(".00", "")} · ${esc(h.emotion)}${h.from?.length ? ` · after hearing ${h.from.map((f) => esc(S.byId.get(f)?.name)).join(", ")}` : ""}</small>${esc(h.quote)}</div>`).join("") || `<div class="muted">Hasn't reacted yet.</div>`;
  $("#chat").innerHTML = ""; $("#drawer").hidden = false; $("#askIn").focus();
}
async function ask(e) {
  e.preventDefault();
  const q = $("#askIn").value.trim(); if (!q || S.talkTo == null) return;
  $("#askIn").value = "";
  const add = (cls, t) => { const d = document.createElement("div"); d.className = "msg " + cls; d.textContent = t; $("#chat").append(d); d.scrollIntoView({ block: "end" }); return d; };
  add("me", q); const pending = add("them", "…");
  try {
    const r = await fetch(`/api/run/${S.runId}/ask`, { method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ agent_id: S.talkTo, question: q, history: chatHist }) });
    const j = await r.json(); if (!r.ok) throw new Error(j.detail);
    pending.textContent = j.answer; chatHist.push({ q, a: j.answer });
  } catch (err) { pending.textContent = "⚠ " + err.message; }
}

/* ---------------- map ---------------- */
const cv = $("#map"), ctx = cv.getContext("2d");
let MAP = null, base = null, proj = null, DPR = 1, hover = null;
async function loadMap() {
  MAP = await (await fetch("/static/india.json")).json();
  new ResizeObserver(resize).observe(cv); resize();
  cv.addEventListener("mousemove", onMove); cv.addEventListener("mouseleave", () => { hover = null; $("#tip").hidden = true; });
  cv.addEventListener("click", () => { if (hover != null) openPerson(hover); });
}
function resize() {
  DPR = window.devicePixelRatio || 1;
  const r = cv.getBoundingClientRect(); cv.width = r.width * DPR; cv.height = r.height * DPR;
  const lon0 = 67.8, lon1 = 97.6, lat0 = 6.4, lat1 = 37.3, k = Math.cos((22 * Math.PI) / 180);
  const pad = 24, w = r.width - pad * 2, h = r.height - pad * 2 - 30;
  const s = Math.min(w / ((lon1 - lon0) * k), h / (lat1 - lat0));
  const ox = pad + (w - (lon1 - lon0) * k * s) / 2, oy = pad + (h - (lat1 - lat0) * s) / 2;
  proj = (lon, lat) => [ox + (lon - lon0) * k * s, oy + (lat1 - lat) * s];
  base = document.createElement("canvas"); base.width = cv.width; base.height = cv.height;
  const b = base.getContext("2d"); b.scale(DPR, DPR);
  // subtle dot grid
  b.fillStyle = "rgba(120,140,180,.07)";
  for (let x = 0; x < r.width; x += 14) for (let y = 0; y < r.height; y += 14) b.fillRect(x, y, 1, 1);
  b.beginPath();
  for (const ring of MAP.rings) ring.forEach(([lo, la], i) => { const [x, y] = proj(lo, la); i ? b.lineTo(x, y) : b.moveTo(x, y); });
  const g = b.createLinearGradient(0, 0, 0, r.height); g.addColorStop(0, "rgba(40,60,100,.35)"); g.addColorStop(1, "rgba(20,30,55,.25)");
  b.fillStyle = g; b.fill("evenodd"); b.strokeStyle = "rgba(130,160,220,.35)"; b.lineWidth = 1; b.stroke();
  layoutAgents();
}
function layoutAgents() { if (!proj) return; for (const a of S.agents) { const [x, y] = proj(a.lon, a.lat); a.x = x; a.y = y; } }
function onMove(ev) {
  const r = cv.getBoundingClientRect(), mx = ev.clientX - r.left, my = ev.clientY - r.top;
  let best = null, bd = 100;
  for (const a of S.agents) { const d = (a.x - mx) ** 2 + (a.y - my) ** 2; if (d < bd) { bd = d; best = a; } }
  hover = best ? best.id : null;
  const tip = $("#tip");
  if (!best) { tip.hidden = true; return; }
  const s = S.st.get(best.id);
  tip.hidden = false;
  tip.innerHTML = `<b>${esc(best.name)}, ${best.age}</b> <span class="muted">· ${esc(best.occupation)}</span><br><span class="muted">${esc(best.place)}, ${esc(best.state)} · ${esc(best.income)}</span>${s ? `<q style="color:${COLORS[s.stance]}">“${esc(s.quote)}”</q>` : ""}`;
  tip.style.left = Math.min(mx + 14, r.width - 300) + "px"; tip.style.top = Math.min(my + 14, r.height - 120) + "px";
}
function draw(now) {
  const W = cv.width / DPR, H = cv.height / DPR;
  ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  ctx.clearRect(0, 0, W, H);
  if (base) ctx.drawImage(base, 0, 0, W, H);
  const n = S.agents.length, rad = n > 700 ? 2.3 : n > 400 ? 2.8 : 3.4;
  // links (word of mouth)
  ctx.lineWidth = 1;
  S.links = S.links.filter((l) => now - l.born < 2200);
  for (const l of S.links) {
    const a = S.byId.get(l.a), b = S.byId.get(l.b); if (!a || !b) continue;
    const t = (now - l.born) / 2200;
    ctx.strokeStyle = l.c; ctx.globalAlpha = 0.55 * (1 - t);
    const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2 - Math.hypot(b.x - a.x, b.y - a.y) * 0.18;
    ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.quadraticCurveTo(mx, my, b.x, b.y); ctx.stroke();
  }
  ctx.globalAlpha = 1;
  // dots
  for (const a of S.agents) {
    const s = S.st.get(a.id);
    ctx.fillStyle = s ? COLORS[s.stance] : IDLE;
    ctx.beginPath(); ctx.arc(a.x, a.y, a.id === hover ? rad + 3 : rad, 0, 6.283); ctx.fill();
  }
  // pulses
  S.pulses = S.pulses.filter((p) => now - p.born < 900);
  for (const p of S.pulses) {
    const a = S.byId.get(p.id); if (!a) continue; const t = (now - p.born) / 900, s = S.st.get(p.id);
    ctx.strokeStyle = s ? COLORS[s.stance] : "#fff"; ctx.globalAlpha = 1 - t; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.arc(a.x, a.y, rad + t * 12, 0, 6.283); ctx.stroke();
  }
  ctx.globalAlpha = 1;
  if (hover != null) { const a = S.byId.get(hover); if (a) { ctx.strokeStyle = "#fff"; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.arc(a.x, a.y, rad + 6, 0, 6.283); ctx.stroke(); } }
  requestAnimationFrame(draw);
}

boot();
