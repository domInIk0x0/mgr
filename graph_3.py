#!/usr/bin/env python3
# transaction_graph_fixed2.py
import json, random
from pathlib import Path

def generate_transaction_data_realistic(n_accounts=40, n_transactions=600):
    accounts = [f"KONTO_{i:03d}" for i in range(n_accounts)]
    txs = []
    n_hubs = max(2, n_accounts // 6)
    hubs = random.sample(accounts, n_hubs)

    for _ in range(n_transactions):
        if random.random() < 0.4:
            src = random.choice(hubs)
        else:
            src = random.choice(accounts)

        possible_targets = [a for a in accounts if a != src]
        if src in hubs:
            tgt = random.choice(possible_targets)
        else:
            tgt = random.choice(hubs + random.sample(possible_targets, k=2))

        amount = round(random.paretovariate(1.5) * 200, 2)
        txs.append({"source": src, "target": tgt, "amount": amount})

        # 🔁 25% szansy na transakcję w drugą stronę
        if random.random() < 0.25:
            back_amount = round(random.paretovariate(1.5) * 150, 2)
            txs.append({"source": tgt, "target": src, "amount": back_amount})

    agg = {}
    for t in txs:
        key = (t["source"], t["target"])
        if key not in agg:
            agg[key] = {"count": 0, "sum": 0.0}
        agg[key]["count"] += 1
        agg[key]["sum"] += t["amount"]

    nodes = [{"id": a, "is_hub": a in hubs} for a in accounts]
    links = [{"source": s, "target": t, "count": v["count"], "sum": v["sum"]} for (s, t), v in agg.items()]
    return {"nodes": nodes, "links": links}


def build_html(data, output_path="transaction_graph_fixed2.html"):
    data_json = json.dumps(data)
    html = """<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8"/>
<title>Graf transakcji — poprawione filtrowanie</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
  html,body{height:100%;margin:0;background:#0c1428;color:#e6eef8;font-family:Inter,Segoe UI,Arial}
  svg{width:100%;height:100%;display:block}
  .link{stroke:rgba(56,189,248,0.6);fill:none}
  .edge-label{font-size:10px;fill:#a5d8ff;pointer-events:none;text-anchor:middle}
  .node circle{stroke:#0b1220;stroke-width:1.2px;cursor:grab}
  text.label{font-size:11px;pointer-events:none;fill:#cfe8ff}
  #tooltip{position:absolute;pointer-events:none;padding:8px;border-radius:6px;background:rgba(2,6,23,0.88);color:#dbeefe;font-size:13px;box-shadow:0 6px 18px rgba(0,0,0,0.6)}
  header.ui{position:absolute;left:12px;top:12px;z-index:10;background:rgba(255,255,255,0.02);padding:8px 12px;border-radius:8px;border:1px solid rgba(255,255,255,0.03)}
  input,button{padding:4px 8px;border-radius:4px;border:none;font-size:13px}
  button{background:#2563eb;color:white;cursor:pointer;margin-left:4px}
  button:hover{background:#1e40af}
  table{margin-top:10px;border-collapse:collapse;width:100%;font-size:13px;color:#d8e0f0}
  th,td{border-bottom:1px solid rgba(255,255,255,0.1);padding:4px 8px;text-align:left}
  #tableContainer{position:absolute;right:12px;top:12px;z-index:10;width:340px;background:rgba(255,255,255,0.04);border-radius:8px;padding:10px;overflow:auto;max-height:90%}
</style>
</head>
<body>
<header class="ui">
  <strong>Graf transakcji</strong><br>
  <small>Kliknij konto, aby zobaczyć jego transakcje. Wpisz numer, aby przefiltrować graf.</small><br>
  <input id="accountInput" placeholder="np. KONTO_005"/>
  <button id="filterBtn">Pokaż graf i transakcje</button>
  <button id="resetBtn">Resetuj graf</button>
  <label><input type="checkbox" id="showEdgeLabels" checked> Pokaż etykiety</label>
</header>

<div id="tableContainer"></div>
<div id="tooltip" style="opacity:0;"></div>
<svg></svg>

<script>
// surowe (niemutowane) dane — zawsze na nich operujemy przy filtrowaniu
const rawGraph = JSON.parse(JSON.stringify(__DATA__)); 
let graph = JSON.parse(JSON.stringify(rawGraph)); // aktualny widok grafu

const svg = d3.select("svg");
const width = window.innerWidth, height = window.innerHeight;
const g = svg.append("g");
svg.call(d3.zoom().scaleExtent([0.2,8]).on("zoom", e=>g.attr("transform",e.transform)));

const defs = svg.append("defs");
defs.append("marker")
  .attr("id","arrow").attr("viewBox","0 -5 10 10")
  .attr("refX",18).attr("refY",0)
  .attr("markerWidth",8).attr("markerHeight",8).attr("orient","auto")
  .append("path").attr("d","M0,-5L10,0L0,5").attr("fill","rgba(56,189,248,0.9)");

const tooltip = d3.select("#tooltip");
const tableContainer = d3.select("#tableContainer");

let link, node, edgeLabel;

// siła
let simulation = d3.forceSimulation()
  .force("link", d3.forceLink().id(d=>d.id).distance(d=>100+Math.log1p(d.sum||1)*15))
  .force("charge", d3.forceManyBody().strength(-300))
  .force("center", d3.forceCenter(width/2,height/2))
  .force("collide", d3.forceCollide(14));

// pomocnicza funkcja: pobiera id (obsługuje string lub obiekt)
function idOf(x){ return (typeof x === "string") ? x : (x && x.id) ? x.id : null; }

function updateGraph(){
  g.selectAll("*").remove();

  // mapa odwrotnych krawędzi na podstawie rawGraph (stringi) — używana do rozdzielania dwóch krawędzi A->B i B->A
  const revPairs = new Set(rawGraph.links.map(l => l.source + "→" + l.target));

  // renderujemy linki (z danych graph)
  link = g.append("g").selectAll("path").data(graph.links).enter()
    .append("path").attr("class","link")
    .attr("stroke-width", d => Math.max(1, Math.sqrt(d.sum)/20))
    .attr("marker-end","url(#arrow)");

  // etykiety — tylko jeśli checkbox
  if (document.getElementById("showEdgeLabels").checked){
    edgeLabel = g.append("g").selectAll("text").data(graph.links).enter()
      .append("text").attr("class","edge-label")
      .text(d => `${d.sum.toFixed(0)} zł / ${d.count}×`);
  } else {
    edgeLabel = null;
  }

  // węzły
  node = g.append("g").selectAll("g").data(graph.nodes).enter().append("g").attr("class","node")
    .on("click", (event,d) => showTable(d.id))
    .call(drag(simulation));

  node.append("circle").attr("r", d => d.is_hub ? 10 : 6).attr("fill", d => d.is_hub ? "#38bdf8" : "#93c5fd");
  node.append("text").attr("class","label").attr("x", 12).attr("y", 4).text(d => d.id);

  // tooltipy
  node.on("mouseover", (e,d) => {
      tooltip.style("opacity",1).html("<strong>"+d.id+"</strong><br>"+(d.is_hub?"Hub (aktywny)":"Zwykły rachunek"));
    }).on("mousemove", e => {
      tooltip.style("left",(e.pageX+12)+"px").style("top",(e.pageY+12)+"px");
    }).on("mouseout", ()=> tooltip.style("opacity",0));

  link.on("mouseover", (e,d) => {
      tooltip.style("opacity",1).html("<strong>"+idOf(d.source)+"</strong> → <strong>"+idOf(d.target)+"</strong><br>Transakcji: "+d.count+"<br>Suma: "+d.sum.toFixed(2)+" zł");
    }).on("mousemove", e => {
      tooltip.style("left",(e.pageX+12)+"px").style("top",(e.pageY+12)+"px");
    }).on("mouseout", ()=> tooltip.style("opacity",0));

  // przed uruchomieniem symulacji: obliczmy mapę par dla aktualnego graph, żeby rozdzielać łuki gdy obie krawędzie istnieją
  // (używamy idOf żeby być odpornym na to czy link.source jest stringiem czy obiektem)
  const pairSet = new Set();
  graph.links.forEach(l => {
    const s = idOf(l.source), t = idOf(l.target);
    pairSet.add(s + "→" + t);
  });

  // przekazanie do tickera: funkcja ticked pobiera pairSet jako closure
  simulation.nodes(graph.nodes).on("tick", () => ticked(pairSet));
  simulation.force("link").links(graph.links);
  simulation.alpha(1).restart();
}

function ticked(pairSet){
  link.attr("d", d => {
    // ujednolicenie id
    const sx = (typeof d.source === "object") ? d.source.x : (graph.nodes.find(n => n.id === d.source) || {}).x;
    const sy = (typeof d.source === "object") ? d.source.y : (graph.nodes.find(n => n.id === d.source) || {}).y;
    const tx = (typeof d.target === "object") ? d.target.x : (graph.nodes.find(n => n.id === d.target) || {}).x;
    const ty = (typeof d.target === "object") ? d.target.y : (graph.nodes.find(n => n.id === d.target) || {}).y;

    // jeśli powyższe nie znalazło pozycji (rzadkie), użyj idOf
    const sId = idOf(d.source), tId = idOf(d.target);

    // fallback (w razie braku pozycji)
    const sxv = sx !== undefined ? sx : 0;
    const syv = sy !== undefined ? sy : 0;
    const txv = tx !== undefined ? tx : 0;
    const tyv = ty !== undefined ? ty : 0;

    const dx = txv - sxv, dy = tyv - syv, mx = (sxv + txv) / 2, my = (syv + tyv) / 2;
    const norm = Math.sqrt(dx*dx + dy*dy) || 1;

    // jeśli istnieje też odwrotna krawędź w aktualnym view (pairSet), rozdzielamy łuki po przeciwnych stronach
    let offset = Math.min(80, 100 / (1 + Math.log1p(d.sum || 1)));
    if (pairSet.has(sId + "→" + tId) && pairSet.has(tId + "→" + sId)) {
      // prosty deterministyczny offset zależny od porządku id, żeby obie krawędzie były rozdzielone
      offset = (sId < tId) ? offset : -offset;
    }
    const cx = mx - dy / norm * offset;
    const cy = my + dx / norm * offset;
    return "M " + sxv + " " + syv + " Q " + cx + " " + cy + " " + txv + " " + tyv;
  });

  node.attr("transform", d => "translate(" + d.x + "," + d.y + ")");
  if (edgeLabel) {
    edgeLabel.attr("x", d => {
      const s_x = (typeof d.source === "object") ? d.source.x : (graph.nodes.find(n => n.id === d.source) || {}).x || 0;
      const t_x = (typeof d.target === "object") ? d.target.x : (graph.nodes.find(n => n.id === d.target) || {}).x || 0;
      const s_y = (typeof d.source === "object") ? d.source.y : (graph.nodes.find(n => n.id === d.source) || {}).y || 0;
      const t_y = (typeof d.target === "object") ? d.target.y : (graph.nodes.find(n => n.id === d.target) || {}).y || 0;
      const midX = (s_x + t_x) / 2;
      const dy = t_y - s_y;
      return midX + (dy > 0 ? 6 : -6);
    }).attr("y", d => {
      const s_x = (typeof d.source === "object") ? d.source.x : (graph.nodes.find(n => n.id === d.source) || {}).x || 0;
      const t_x = (typeof d.target === "object") ? d.target.x : (graph.nodes.find(n => n.id === d.target) || {}).x || 0;
      const s_y = (typeof d.source === "object") ? d.source.y : (graph.nodes.find(n => n.id === d.source) || {}).y || 0;
      const t_y = (typeof d.target === "object") ? d.target.y : (graph.nodes.find(n => n.id === d.target) || {}).y || 0;
      const midY = (s_y + t_y) / 2;
      const dx = t_x - s_x;
      return midY - (dx > 0 ? 6 : -6);
    });
  }
}

// drag: TRWAŁE pozycje (nie resetujemy fx/fy)
function drag(sim){
  function started(e,d){ if(!e.active) sim.alphaTarget(0.25).restart(); d.fx = d.x; d.fy = d.y; }
  function dragged(e,d){ d.fx = e.x; d.fy = e.y; }
  function ended(e,d){ if(!e.active) sim.alphaTarget(0); /* nie czyścimy fx/fy */ }
  return d3.drag().on("start", started).on("drag", dragged).on("end", ended);
}

// pokaż tabelę transakcji (używa rawGraph, bo tam są stringi)
function showTable(accountId){
  const relevant = rawGraph.links.filter(l => l.source === accountId || l.target === accountId);
  if (relevant.length === 0) { tableContainer.html("<h3>"+accountId+"</h3><p>Brak transakcji.</p>"); return; }
  let html = "<h3>"+accountId+"</h3><table><thead><tr><th>Nadawca</th><th>Odbiorca</th><th>Liczba</th><th>Suma</th></tr></thead><tbody>";
  relevant.forEach(r => {
    html += "<tr><td>"+r.source+"</td><td>"+r.target+"</td><td>"+r.count+"</td><td>"+r.sum.toFixed(2)+" zł</td></tr>";
  });
  html += "</tbody></table>";
  tableContainer.html(html);
}

// filter: opieramy się NA ZAWSZE NA rawGraph (niemutowanym)
document.getElementById("filterBtn").onclick = () => {
  const input = document.getElementById("accountInput").value.trim();
  if (!input) return;
  const accountExists = rawGraph.nodes.some(n => n.id === input);
  if (!accountExists) { alert("Nie znaleziono rachunku: " + input); return; }
  const relatedLinks = rawGraph.links.filter(l => l.source === input || l.target === input);
  const relatedNodes = new Set([input]);
  relatedLinks.forEach(l => { relatedNodes.add(l.source); relatedNodes.add(l.target); });
  graph = {
    nodes: rawGraph.nodes.filter(n => relatedNodes.has(n.id)),
    links: relatedLinks.map(l => ({ source: l.source, target: l.target, count: l.count, sum: l.sum }))
  };
  showTable(input);
  updateGraph();
};

// reset przywraca pełny widok (kopię rawGraph)
document.getElementById("resetBtn").onclick = () => {
  graph = JSON.parse(JSON.stringify(rawGraph));
  tableContainer.html("");
  updateGraph();
};

// checkbox etykiet
document.getElementById("showEdgeLabels").onchange = updateGraph;

// initial
updateGraph();
</script>
</body>
</html>
"""
    # wstrzyknięcie danych
    html = html.replace("__DATA__", data_json)
    Path(output_path).write_text(html, encoding="utf-8")
    print("✅ Wygenerowano:", output_path)


if __name__ == "__main__":
    data = generate_transaction_data_realistic(40, 700)
    build_html(data)
