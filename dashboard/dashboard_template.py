"""HTML template for the CTSM CONUS dashboard.

Kept separate from the builder so the markup and JavaScript can be edited
without wading through the Python. build_streamflow_dashboard.py substitutes
__DATA_JSON__ and writes the result.

Conventions the JS relies on:
  colour  = configuration (observed is always black)
  panel   = variable (one variable per panel, so one unit per panel)
  the configuration checkboxes are the shared legend for all seven plots
"""

TEMPLATE = r"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>CTSM CONUS evaluation</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/plotly.js/2.32.0/plotly.min.js"></script>
<style>
  :root { --font:-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
          --ink:#2b2b2b; --muted:#6b6b6b; --border:#e0e0e0; --bg:#fafafa; }
  * { box-sizing:border-box; }
  html,body { height:100%; }
  body { font-family:var(--font); color:var(--ink); margin:0; display:flex;
         height:100vh; overflow:hidden; font-size:13px; }

  /* ---------- left column ---------- */
  #left { width:45%; min-width:420px; display:flex; flex-direction:column;
          border-right:1px solid var(--border); }
  #ctl { padding:7px 10px; border-bottom:1px solid var(--border);
         background:var(--bg); display:flex; flex-direction:column; gap:5px; }
  .row { display:flex; gap:6px; align-items:center; }
  input,select,button { font-family:var(--font); font-size:12px; padding:3px 6px;
         border:1px solid var(--border); border-radius:4px; background:#fff;
         color:var(--ink); }
  button { cursor:pointer; }
  button:hover { background:#f0f0f0; }
  #q { flex:1; min-width:0; }
  .lbl { font-size:11px; color:var(--muted); white-space:nowrap; }
  #stat { font-size:11px; color:var(--muted); min-height:13px; }
  #map { flex:1.15; min-height:0; }
  #tsbox { flex:1; min-height:0; display:flex; flex-direction:column;
           border-top:1px solid var(--border); }
  #tblbox { height:150px; border-top:1px solid var(--border); overflow:auto;
            padding:5px 8px; background:#fff; }
  .boxhdr { padding:3px 8px; font-size:11px; color:var(--muted);
            background:var(--bg); border-bottom:1px solid var(--border);
            display:flex; gap:10px; align-items:center; }
  .boxhdr label { cursor:pointer; }
  #ts { flex:1; min-height:0; }

  /* ---------- right column ---------- */
  #right { flex:1; display:flex; flex-direction:column; min-width:0; }
  #hdr { padding:7px 12px; border-bottom:1px solid var(--border); }
  #hdr b { font-size:15px; }
  .badge { display:inline-block; padding:1px 7px; border-radius:10px;
           color:#fff; font-size:11px; margin-left:4px; white-space:nowrap; }
  .bp { background:#ececec; color:var(--ink); }
  #warn { color:#b2182b; font-size:11px; margin-top:3px; }
  #cfgbar { padding:5px 12px; border-bottom:1px solid var(--border);
            background:var(--bg); display:flex; flex-wrap:wrap; gap:14px;
            align-items:center; }
  #cfgbar label { cursor:pointer; white-space:nowrap; font-size:12px; }
  .sw { display:inline-block; width:20px; height:3px; border-radius:2px;
        margin-right:4px; vertical-align:middle; }
  .init { color:var(--muted); font-size:10.5px; margin-left:3px; }
  #grid { flex:1; min-height:0; display:grid;
          grid-template-columns:1fr 1fr; grid-template-rows:1fr 1fr 1fr; }
  .cell { min-width:0; min-height:0; display:flex; flex-direction:column;
          border-right:1px solid var(--border);
          border-bottom:1px solid var(--border); }
  .cell:nth-child(2n) { border-right:none; }
  .cell .p { flex:1; min-height:0; }
  .chdr { padding:2px 6px; font-size:11px; color:var(--muted);
          background:var(--bg); border-bottom:1px solid var(--border);
          display:flex; gap:6px; align-items:center; }
  .chdr select { font-size:11px; padding:1px 3px; max-width:100%; }
  .fixed { font-weight:600; color:var(--ink); }

  table { border-collapse:collapse; width:100%; font-size:11.5px; }
  th,td { padding:3px 6px; text-align:right; border-bottom:1px solid #f2f2f2;
          white-space:nowrap; }
  th:first-child, td:first-child { text-align:left; }
  th { color:var(--muted); font-weight:600; position:sticky; top:0; background:#fff; }
  td.cfg { font-weight:600; }
  .dot { display:inline-block; width:8px; height:8px; border-radius:50%;
         margin-right:5px; }
  .best { background:#eef6ff; }
  .note { color:var(--muted); font-size:10.5px; margin-top:5px; }
  #hint { color:var(--muted); font-size:13px; }
</style></head>
<body>
  <div id="left">
    <div id="ctl">
      <div class="row">
        <input id="q" placeholder="Search gauge name or ID, press Enter"/>
        <button id="csv" title="Download everything shown for this gauge">CSV</button>
        <button id="link" title="Copy a link that opens on this gauge">Link</button>
      </div>
      <div class="row">
        <span class="lbl">colour by</span>
        <select id="metric">
          <option value="nse">NSE</option>
          <option value="kge">KGE</option>
          <option value="pbias">PBIAS</option>
          <option value="area">Contributing area</option>
        </select>
        <select id="mapcfg"></select>
      </div>
      <div class="row">
        <label class="lbl"><input type="checkbox" id="diff"> difference mode:</label>
        <select id="base"></select>
        <span class="lbl">(applies to every panel)</span>
      </div>
      <div id="stat"></div>
    </div>
    <div id="map"></div>
    <div id="tsbox">
      <div class="boxhdr">
        <span class="fixed">Monthly streamflow (m³/s)</span>
        <label><input type="checkbox" id="logy"> log scale</label>
        <span id="tsnote" class="lbl" style="margin-left:auto"></span>
      </div>
      <div id="ts"></div>
    </div>
    <div id="tblbox"></div>
  </div>

  <div id="right">
    <div id="hdr"><span id="hint">Click a gauge on the map, or search, to load it.</span></div>
    <div id="cfgbar"></div>
    <div id="grid"></div>
  </div>

<script>
const DATA   = __DATA_JSON__;
const CFG    = DATA.configs;          // [{key,label,color,init}]
const VARS   = DATA.vars;             // [{key,label,unit,cfgs:[...]}]
const MONTHS = DATA.months;
const STABLE = DATA.stable_min_months;
const SPINUP = DATA.spinup_years;
const MN = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const WYI = [9,10,11,0,1,2,3,4,5,6,7,8];        // Oct..Sep into Jan..Dec arrays
const FONT = {family:"-apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif", size:11};

let sel = -1, metric = "nse", mapcfg = DATA.ref, mapbase = "";
let diff = false, base = DATA.ref, wy = true, logy = false;
const panels = DATA.panels.slice();               // variable key per panel 2..6
const on = {};
CFG.forEach(c => on[c.key] = true);

const cfgOf = k => CFG.find(c => c.key === k);
const col   = k => (cfgOf(k) || {}).color || "#888";
const lab   = k => (cfgOf(k) || {}).label || k;
const varOf = k => VARS.find(v => v.key === k);
const $     = id => document.getElementById(id);

function ord(a){ return wy ? WYI.map(i => a ? a[i] : null) : (a || []).slice(); }
function xlab(){ return wy ? WYI.map(i => MN[i]) : MN.slice(); }
/* A metric is missing whenever the builder could not compute it (zero observed
   variance, zero observed mean); those arrive as null and must never be drawn
   or formatted as if they were numbers. */
function num(x){ return x !== null && x !== undefined && isFinite(x); }
function fmt(x,d){ return num(x) ? x.toFixed(d) : "\u2013"; }

/* ------------------------------------------------------------------ map */
/* PBIAS is scored on magnitude: zero is good and either sign is bad, so the
   map shows |PBIAS| and, in difference mode, the change in |PBIAS|. */
function mapScore(x){ return metric === "pbias" ? Math.abs(x) : x; }
function mapValue(g){
  if (metric === "area") return Math.log10(Math.max(g.area_km2,1));
  const m = g.m[mapcfg];
  if (!m || !num(m[metric])) return null;
  const a = mapScore(m[metric]);
  if (!mapbase) return a;
  const r = g.m[mapbase];
  if (!r || !num(r[metric])) return null;
  return a - mapScore(r[metric]);
}
/* Fifth element reverses the scale. Plotly's built-in RdBu runs blue -> red
   from low to high, so rev=true puts blue at the top (high NSE/KGE is good)
   and rev=false leaves blue at the bottom (low |PBIAS| is good). Either way
   blue means good and red means bad. */
function mapRange(){
  if (metric === "area")  return [1,6,"log10 km²","Viridis",false];
  if (metric === "pbias") return mapbase ? [-40,40,"Δ|PBIAS| %","RdBu",false]
                                         : [0,100,"|PBIAS| %","RdBu",false];
  return mapbase ? [-0.3,0.3,"Δ"+metric.toUpperCase(),"RdBu",true]
                 : [-1,1,metric.toUpperCase(),"RdBu",true];
}
let mapBound = false;
function renderMap(){
  const [lo,hi,title,scale,rev] = mapRange();
  const v = DATA.gauges.map(mapValue);
  const txt = i => DATA.gauges[i].name+"<br>"
    +DATA.gauges[i].area_km2.toLocaleString()+" km²<br>"
    +(mapbase ? lab(mapcfg)+" − "+lab(mapbase)+"  " : lab(mapcfg)+"  ")
    +title+" = "+(num(v[i]) ? v[i].toFixed(3) : "n/a");
  // Gauges the metric could not be computed for get hollow grey markers: at
  // mid-scale they would be indistinguishable from a genuinely neutral score.
  const ok = [], no = [];
  DATA.gauges.forEach((g,i)=> (num(v[i]) ? ok : no).push(i));
  const tr = [];
  if (no.length) tr.push({
    type:"scattergeo", mode:"markers", name:"g", showlegend:false,
    lon:no.map(i=>DATA.gauges[i].lon), lat:no.map(i=>DATA.gauges[i].lat),
    customdata:no, text:no.map(txt), hoverinfo:"text",
    marker:{size:5, color:"rgba(0,0,0,0)", line:{width:0.8,color:"#b3b3b3"}}
  });
  tr.push({
    type:"scattergeo", mode:"markers", name:"g", showlegend:false,
    lon:ok.map(i=>DATA.gauges[i].lon), lat:ok.map(i=>DATA.gauges[i].lat),
    customdata:ok, text:ok.map(txt), hoverinfo:"text",
    marker:{size:6, color:ok.map(i=>Math.max(lo,Math.min(hi,v[i]))),
      colorscale:scale, reversescale:rev, cmin:lo, cmax:hi,
      colorbar:{title:{text:title,side:"right"}, thickness:11, len:0.85},
      line:{width:0.4,color:"#333"}}
  });
  if (sel>=0 && DATA.gauges[sel].bbox){
    const b = DATA.gauges[sel].bbox;
    tr.push({type:"scattergeo", mode:"lines", name:"bbox", showlegend:false,
      hoverinfo:"skip",
      lat:[b[0],b[0],b[1],b[1],b[0]], lon:[b[2],b[3],b[3],b[2],b[2]],
      line:{width:2,color:"#e45756"}});
  }
  // uirevision keeps the user's pan/zoom (and the zoom the search box sets)
  // across every redraw; without it each react call snaps back to the default.
  Plotly.react("map", tr, {geo:{scope:"usa",showland:true,landcolor:"#f2f2f2",
    showlakes:true, lakecolor:"#fff", showrivers:false},
    uirevision:"map", margin:{t:3,b:3,l:3,r:3}, font:FONT}, {responsive:true});
  if (!mapBound){                 // bind once: renderMap runs on every redraw
    mapBound = true;
    $("map").on("plotly_click", e => {
      const p = e.points[0];
      if (p.data.name === "g") show(p.customdata);
    });
  }
}

/* ------------------------------------------------- monthly time series */
function drawTS(){
  const g = DATA.gauges[sel], s = DATA.series[g.id];
  const x = s.mi.map(i => MONTHS[i]);
  const tr = [];
  if (!diff) {
    tr.push({x:x, y:s.obs, name:"Observed", mode:"lines",
             line:{color:"#111",width:1}, hovertemplate:"obs %{y:.1f}<extra></extra>"});
  }
  CFG.forEach(c=>{
    if(!on[c.key] || !s.sim[c.key]) return;
    let y = s.sim[c.key];
    if (diff) {
      const b = s.sim[base];
      if (!b || c.key === base) return;
      y = y.map((v,i) => (v===null||b[i]===null) ? null : v-b[i]);
    }
    tr.push({x:x, y:y, name:c.label, mode:"lines",
             line:{color:c.color,width:1}});
  });
  // Keyed so zoom survives a configuration toggle but resets whenever the
  // gauge, the axis type or difference mode changes.
  const lay = {margin:{t:6,b:26,l:50,r:10}, font:FONT, showlegend:false,
    uirevision:"ts|"+sel+"|"+(diff?"d":"a")+"|"+(logy?"log":"lin"),
    yaxis:{title:{text: diff ? "Δ m³/s" : "m³/s", standoff:4},
           type: (logy && !diff) ? "log" : "linear"},
    xaxis:{type:"category", nticks:10}, shapes:[], annotations:[]};
  if (diff) lay.shapes.push({type:"line", xref:"paper", x0:0, x1:1,
    yref:"y", y0:0, y1:0, line:{color:"#999", width:1, dash:"dot"}});
  // Configurations start from different restarts, so shade the opening
  // years: differences there can be initialization rather than process.
  if (SPINUP > 0 && x.length){
    const n = Math.min(SPINUP*12, x.length-1);
    if (n > 0){
      lay.shapes.push({type:"rect", xref:"x", x0:x[0], x1:x[n],
        yref:"paper", y0:0, y1:1, fillcolor:"#000", opacity:0.05,
        line:{width:0}, layer:"below"});
      lay.annotations.push({x:x[Math.floor(n/2)], y:1, yref:"paper",
        text:"spin-up influence", showarrow:false,
        font:{size:9,color:"#888"}, yanchor:"bottom"});
    }
  }
  if (logy && diff) lay.annotations.push({x:0.5,y:1.06,xref:"paper",yref:"paper",
    text:"log scale ignored in difference mode", showarrow:false,
    font:{size:9,color:"#b2182b"}});
  Plotly.react("ts", tr, lay, {responsive:true});
  $("tsnote").textContent = diff ? "difference vs " + lab(base) : "";
}

/* ---------------------------------------------------- seasonal panels */
function seriesFor(key, cfgKey){
  const g = DATA.gauges[sel];
  if (key === "__Q__"){
    const s = DATA.series[g.id];
    return cfgKey === "__obs__" ? s.obs_clim : s.sim_clim[cfgKey];
  }
  const b = (g.b || {})[cfgKey];
  return b ? b[key] : null;
}
function drawPanel(i){
  const g = DATA.gauges[sel];
  const key = (i === 0) ? "__Q__" : panels[i-1];
  const v = (i === 0) ? {label:"Streamflow", unit:"m³/s", cfgs:CFG.map(c=>c.key)}
                      : varOf(key);
  const tr = [], xl = xlab();
  if (i === 0 && !diff){
    tr.push({x:xl, y:ord(seriesFor(key,"__obs__")), name:"Observed",
             mode:"lines+markers", line:{color:"#111",width:2}, marker:{size:5}});
  }
  let missing = [];
  CFG.forEach(c=>{
    if (!on[c.key]) return;
    let y = seriesFor(key, c.key);
    if (!y){ if (v && v.cfgs && v.cfgs.indexOf(c.key)<0) missing.push(c.label); return; }
    if (diff){
      const b = seriesFor(key, base);
      if (!b || c.key === base) return;
      y = y.map((val,k)=> (val===null||b[k]===null) ? null : val-b[k]);
    }
    tr.push({x:xl, y:ord(y), name:c.label, mode:"lines+markers",
             line:{color:c.color,width:2}, marker:{size:4}});
  });
  const lay = {margin:{t:5,b:24,l:46,r:8}, font:FONT, showlegend:false,
    uirevision:"p"+i+"|"+sel+"|"+key+"|"+(diff?"d":"a")+"|"+(wy?"wy":"cal"),
    yaxis:{title:{text:(diff?"Δ ":"")+(v?v.unit:""), standoff:3}},
    shapes:[], annotations:[]};
  if (diff) lay.shapes.push({type:"line", xref:"paper", x0:0, x1:1,
    yref:"y", y0:0, y1:0, line:{color:"#999",width:1,dash:"dot"}});
  if (!tr.length) lay.annotations.push({text:"not available for the shown "
    +"configuration(s)", showarrow:false, font:{size:10,color:"#999"}});
  else if (missing.length) lay.annotations.push({x:0.02,y:1.0,xref:"paper",
    yref:"paper", xanchor:"left", yanchor:"top", showarrow:false,
    text:"n/a: "+missing.join(", "), font:{size:9,color:"#999"}});
  Plotly.react("p"+i, tr, lay, {responsive:true});
}
function drawPanels(){ for(let i=0;i<6;i++) drawPanel(i); }

/* ------------------------------------------------------------- table */
function annMean(a){ const f=(a||[]).filter(x=>x!==null);
  return f.length ? f.reduce((s,x)=>s+x,0)/f.length : null; }
function drawTable(){
  const g = DATA.gauges[sel];
  const rows = CFG.filter(c => g.m[c.key]);
  if (!rows.length){ $("tblbox").innerHTML = ""; return; }
  // Math.max/min coerce null to 0, which would hand "best" to a gauge whose
  // metric is missing, so drop the non-numbers before comparing.
  const pick = (f,get) => { const a = rows.map(get).filter(num);
                            return a.length ? f(...a) : null; };
  const best = {nse:  pick(Math.max, c=>g.m[c.key].nse),
                kge:  pick(Math.max, c=>g.m[c.key].kge),
                pbias:pick(Math.min, c=>num(g.m[c.key].pbias)
                                        ? Math.abs(g.m[c.key].pbias) : null)};
  const mark = (x,b) => (num(x) && num(b) && x===b) ? "best" : "";
  const show = panels.slice(0,4).map(varOf).filter(Boolean);
  let h = "<table><tr><th>Configuration</th><th>NSE</th><th>KGE</th><th>PBIAS</th>"
        + "<th>Q̄ m³/s</th>" + show.map(v=>"<th>"+v.label+"</th>").join("") + "</tr>";
  rows.forEach(c=>{
    const m = g.m[c.key], b = (g.b||{})[c.key] || {};
    h += "<tr><td class='cfg'><span class='dot' style='background:"+c.color+"'></span>"
       + c.label + "</td>"
       + "<td class='"+mark(m.nse,best.nse)+"'>"+fmt(m.nse,3)+"</td>"
       + "<td class='"+mark(m.kge,best.kge)+"'>"+fmt(m.kge,3)+"</td>"
       + "<td class='"+mark(num(m.pbias)?Math.abs(m.pbias):null,best.pbias)+"'>"
       + (num(m.pbias) ? fmt(m.pbias,1)+"%" : "\u2013")+"</td>"
       + "<td>"+fmt(m.q,1)+"</td>"
       + show.map(v=>"<td>"+fmt(annMean(b[v.key]),2)+"</td>").join("")
       + "</tr>";
  });
  h += "</table><div class='note'>Metrics use the months common to observations "
     + "and every configuration, so they are directly comparable. Basin columns "
     + "are annual means over the contributing area.</div>";
  $("tblbox").innerHTML = h;
}

/* -------------------------------------------------------------- chrome */
function buildGrid(){
  let h = "";
  for (let i=0;i<6;i++){
    h += "<div class='cell'><div class='chdr'>";
    h += (i===0) ? "<span class='fixed'>Streamflow</span>"
                 : "<select data-p='"+(i-1)+"'></select>";
    h += "</div><div class='p' id='p"+i+"'></div></div>";
  }
  $("grid").innerHTML = h;
  $("grid").querySelectorAll("select").forEach(s=>{
    const pi = +s.dataset.p;
    s.innerHTML = VARS.map(v=>"<option value='"+v.key+"'>"+v.label+" ("+v.unit+")"
      + (v.cfgs.length<CFG.length ? " — "+v.cfgs.map(lab).join("/") : "")
      + "</option>").join("");
    s.value = panels[pi];
    s.addEventListener("change", e=>{
      panels[pi] = e.target.value; drawPanel(pi+1); drawTable(); pushHash();
    });
  });
}
function buildCfgBar(){
  $("cfgbar").innerHTML = "<span class='lbl'>show:</span>" + CFG.map(c=>
    "<label><input type='checkbox' data-k='"+c.key+"'"+(on[c.key]?" checked":"")
    +"><span class='sw' style='background:"+c.color+"'></span>"+c.label
    +(c.init?"<span class='init'>init "+c.init+"</span>":"")
    +"</label>").join("");
  $("cfgbar").querySelectorAll("input").forEach(cb=>
    cb.addEventListener("change", e=>{
      on[e.target.dataset.k] = e.target.checked;
      if (sel>=0){ drawTS(); drawPanels(); }
    }));
}
function buildSelects(){
  $("mapcfg").innerHTML = CFG.map(c=>"<option value='"+c.key+"'>"+c.label
    +"</option>").join("");
  $("mapcfg").value = mapcfg;
  $("mapcfg").addEventListener("change", e=>{ mapcfg=e.target.value; renderMap(); pushHash(); });

  $("base").innerHTML = CFG.map(c=>"<option value='"+c.key+"'>"+c.label
    +"</option>").join("");
  $("base").value = base;
  $("base").addEventListener("change", e=>{
    base = e.target.value;
    if (diff){ mapbase = base; if (mapcfg===base){
        const o=CFG.find(c=>c.key!==base); if(o){ mapcfg=o.key; $("mapcfg").value=o.key; } } }
    redrawAll(); pushHash();
  });
  $("diff").addEventListener("change", e=>{
    diff = e.target.checked;
    mapbase = diff ? base : "";
    if (diff && mapcfg===base){
      const o=CFG.find(c=>c.key!==base); if(o){ mapcfg=o.key; $("mapcfg").value=o.key; } }
    redrawAll(); pushHash();
  });
  $("logy").addEventListener("change", e=>{ logy=e.target.checked; if(sel>=0) drawTS(); });
}
function redrawAll(){ renderMap(); if (sel>=0){ drawTS(); drawPanels(); drawTable(); } }

/* ----------------------------------------------------------- selection */
function show(i){
  sel = i;
  const g = DATA.gauges[i];
  const ns = CFG.filter(c=>g.m[c.key]).map(c=>g.m[c.key].n);
  let w = [];
  if (ns.length && Math.min(...ns) < STABLE)
    w.push("\u26a0 only " + Math.min(...ns) + " overlapping months — NSE/KGE "
           + "can be unreliable at this record length");
  if (g.area_err!==null && Math.abs(g.area_err)>0.02)
    w.push("\u26a0 contributing area differs from the topology's totalArea by "
           + (100*g.area_err).toFixed(1) + "%");
  const inits = CFG.filter(c=>g.m[c.key] && c.init).map(c=>c.init);
  if (new Set(inits).size > 1)
    w.push("\u26a0 configurations start from different restarts ("
           + CFG.filter(c=>g.m[c.key]&&c.init).map(c=>c.label+" "+c.init).join(", ")
           + ") — early differences may be initialization, not process");
  $("hdr").innerHTML = "<b>"+g.name+"</b>"
    + "<span class='badge bp'>"+g.id+"</span>"
    + "<span class='badge bp'>"+g.area_km2.toLocaleString()+" km²</span>"
    + "<span class='badge bp'>"+g.n_hru.toLocaleString()+" HRUs</span>"
    + "<span class='badge bp'>"+g.n_cells.toLocaleString()+" cells</span>"
    + (w.length ? "<div id='warn'>"+w.join("<br>")+"</div>" : "");
  drawTS(); drawPanels(); drawTable(); renderMap(); pushHash();
}

/* ------------------------------------------------------- permalink/CSV */
function pushHash(){
  if (sel < 0) return;
  const p = ["g="+encodeURIComponent(DATA.gauges[sel].id),
             "m="+metric, "c="+mapcfg, "v="+panels.join("|")];
  if (diff) p.push("d="+base);
  if (!wy) p.push("cal=1");
  if (logy) p.push("log=1");
  history.replaceState(null,"","#"+p.join("&"));
}
const METRICS = ["nse","kge","pbias","area"];
function readHash(){
  const h = location.hash.replace(/^#/,""); if(!h) return;
  const q = {}; h.split("&").forEach(kv=>{const [k,v]=kv.split("=");
    if(k) q[k]=decodeURIComponent(v||"");});
  // A stale or hand-edited link must not leave the map colouring by a metric
  // that does not exist, so ignore anything unrecognised.
  if (q.m && METRICS.indexOf(q.m)>=0) { metric=q.m; $("metric").value=metric; }
  if (q.c && cfgOf(q.c)) { mapcfg=q.c; $("mapcfg").value=mapcfg; }
  if (q.v) { q.v.split("|").forEach((k,i)=>{ if(varOf(k)) panels[i]=k; });
             buildGrid(); }
  if (q.d && cfgOf(q.d)) { diff=true; base=q.d; mapbase=base;
             $("diff").checked=true; $("base").value=base; }
  if (q.cal){ wy=false; $("wy").checked=false; }
  if (q.log){ logy=true; $("logy").checked=true; }
  if (q.g){ const i=DATA.gauges.findIndex(g=>String(g.id)===q.g); if(i>=0) show(i); }
}
function toCSV(){
  if (sel<0) return;
  const g = DATA.gauges[sel], s = DATA.series[g.id];
  const keys = CFG.filter(c=>s.sim[c.key]).map(c=>c.key);
  let out = "# "+g.name+" ("+g.id+")  area_km2="+g.area_km2
          + " n_hru="+g.n_hru+" n_cells="+g.n_cells+"\n";
  out += "# configurations: "+CFG.map(c=>c.key+" (init "+(c.init||"?")+")").join(", ")+"\n\n";
  // Gaps go out as empty cells; "null" would be read back as a string by
  // pandas and quietly turn a numeric column into object dtype.
  const cell = x => num(x) ? x : "";
  const join = a => (a||[]).map(cell).join(",");
  out += "# monthly streamflow, m3/s\nmonth,observed,"+keys.join(",")+"\n";
  s.mi.forEach((mi,r)=>{ out += MONTHS[mi]+","+cell(s.obs[r])
    + keys.map(k=>","+cell(s.sim[k][r])).join("")+"\n"; });
  out += "\n# seasonal climatology\nvariable,unit,config,"+MN.join(",")+"\n";
  keys.forEach(k=>{ out += "streamflow,m3/s,"+k+","+join(s.sim_clim[k])+"\n"; });
  out += "streamflow,m3/s,observed,"+join(s.obs_clim)+"\n";
  VARS.forEach(v=>{ CFG.forEach(c=>{ const y=(g.b||{})[c.key]
    ? g.b[c.key][v.key] : null;
    if (y) out += v.key+","+v.unit+","+c.key+","+join(y)+"\n"; }); });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([out],{type:"text/csv"}));
  a.download = "gauge_"+g.id+".csv"; a.click();
}

/* ----------------------------------------------------------- listeners */
$("metric").addEventListener("change", e=>{ metric=e.target.value; renderMap(); pushHash(); });
$("csv").addEventListener("click", toCSV);
$("link").addEventListener("click", ()=>{
  pushHash();
  navigator.clipboard.writeText(location.href).then(
    ()=>{ $("stat").textContent = "link copied"; },
    ()=>{ $("stat").textContent = location.href; });
});
let qHits = [], qPos = 0, qLast = "";
$("q").addEventListener("keydown", e=>{
  if (e.key!=="Enter") return;
  const s = e.target.value.trim().toLowerCase();
  if (!s){ $("stat").textContent=""; return; }
  if (s !== qLast){                                  // new query: collect all matches
    qLast = s; qPos = 0;
    qHits = [];
    DATA.gauges.forEach((g,i)=>{
      const nm = typeof g.name === "string" ? g.name : "";   // gauges without a name are NaN in DATA
      if (nm.toLowerCase().includes(s) || String(g.id).toLowerCase().includes(s)) qHits.push(i);
    });
    qHits.sort((a,b)=>(String(DATA.gauges[b].id)===s) - (String(DATA.gauges[a].id)===s)); // exact ID first
  } else if (qHits.length) qPos = (qPos+1) % qHits.length;   // same query: next match
  if (!qHits.length){ $("stat").textContent='no match for "'+s+'"'; return; }
  const i = qHits[qPos];
  $("stat").textContent = `match ${qPos+1} of ${qHits.length}: ${DATA.gauges[i].name}`
                          + (qHits.length>1 ? " (Enter for next)" : "");
  show(i);                                           // redraws the map, so zoom after
  Plotly.relayout("map",{"geo.center":{lat:DATA.gauges[i].lat,lon:DATA.gauges[i].lon},
    "geo.projection.scale":5});
});

buildCfgBar(); buildGrid(); buildSelects();
// water-year toggle lives in the seasonal area but drives every climatology
const wyBox = document.createElement("label");
wyBox.style.marginLeft = "auto";
wyBox.innerHTML = "<input type='checkbox' id='wy' checked> water year (Oct–Sep)";
$("cfgbar").appendChild(wyBox);
$("wy").addEventListener("change", e=>{ wy=e.target.checked;
  if (sel>=0) drawPanels(); pushHash(); });

// readHash first: renderMap used to run before it, so a link carrying a metric
// or baseline but no gauge drew the map with the defaults and never redrew.
readHash();
renderMap();
</script>
</body></html>
"""
