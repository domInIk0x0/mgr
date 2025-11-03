#!/usr/bin/env python3
# build_graph_full.py
import json
import random
from pathlib import Path

def generate_transaction_data_realistic(n_accounts=40, n_transactions=600):
    """
    Generuje realistyczne, rzadkie połączenia transakcyjne:
    - część kont to 'huby' (więcej połączeń),
    - większość kont ma 1-3 powiązania,
    - rozkład kwot pareto-like (wiele małych, kilka dużych).
    Zwraca dict: {"nodes": [...], "links": [...]}
    """
    accounts = [f"KONTO_{i:03d}" for i in range(n_accounts)]
    txs = []
    n_hubs = max(2, n_accounts // 6)
    hubs = random.sample(accounts, n_hubs)

    for _ in range(n_transactions):
        # nadawca: z większym prawdopodobieństwem hub
        if random.random() < 0.4:
            src = random.choice(hubs)
        else:
            src = random.choice(accounts)
        possible_targets = [a for a in accounts if a != src]
        # jeśli hub -> wysyła do losowych, jeśli zwykły -> częściej do hubów
        if src in hubs:
            tgt = random.choice(possible_targets)
        else:
            # 1/2 szansy do hubów, reszta do losowych (ale mało)
            tgt = random.choice(hubs + random.sample(possible_targets, k=min(2, len(possible_targets))))
        # kwota: pareto-like (dużo małych, trochę dużych)
        amount = round(random.paretovariate(1.5) * 200, 2)
        txs.append({"source": src, "target": tgt, "amount": amount})

    # agregacja (kierunkowa)
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


def build_html(data, output_path="transaction_graph_filtered.html"):
    """
    Tworzy plik HTML z osadzonym JSON-em `data`.
    Ważne: HTML nie jest f-stringiem — dane wstrzykujemy przez zastąpienie "__DATA__".
    """
    data_json = json.dumps(data)
    html = """<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Przepływy finansowe — filtr i trwałe pozycje</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
  html,body{height:100%;margin:0;background:#071022;color:#e6eef8;font-family:Inter,Segoe UI,Arial}
  svg{width:100%;height:100%;display:block}
  .link{stroke:rgba(56,189,248,0.6);fill:none}
  .node circle{stroke:#0b1220;stroke-width:1.2px;cursor:grab}
  text.label{font-size:11px;pointer-events:none;fill:#cfe8ff}
  #tooltip{position:absolute;pointer-events:none;padding:8px;border-radius:6px;background:rgba(2,6,23,0.88);color:#dbeefe;font-size:13px;box-shadow:0 6px 18px rgba(0,0,0,0.6)}
  header.ui{position:absolute;left:12px;top:12px;z-index:10;background:rgba(255,255,255,0.02);padding:8px 12px;border-radius:8px;border:1px solid rgba(255,255,255,0.03)}
  .small{font-size:12px;color:#9fb7d7;margin-top:6px}
  input,button{padding:4px 8px;border-radius:4px;border:none;font-size:13px}
  button{background:#2563eb;color:white;cursor:pointer}
  button:hover{background:#1e40af}
</style>
</head>
<body>
<header class="ui">
  <strong>Przepływy finansowe — filtr i trwałe pozycje</strong>
  <div class="small">Wpisz numer konta (np. KONTO_005), aby wyświetlić tylko jego powiązania. Kliknij w węzeł, by przefiltrować. Przeciągnięty węzeł zostaje.</div>
  <div style="margin-top:6px;">
    <input type="text" id="filterInput" placeholder="np. KONTO_005"/>
    <button id="filterBtn">Filtruj</button>
    <button id="resetBtn">Reset</button>
  </div>
</header>

<div id="tooltip" style="opacity:0;"></div>
<svg></svg>

<script>
/* dane wstawione dynamicznie */
const fullGraph = __DATA__;
let graph = JSON.parse(JSON.stringify(fullGraph));

const svg = d3.select("svg");
const width = window.innerWidth;
const height = window.innerHeight;
const g = svg.append("g");

const defs = svg.append("defs");
defs.append("marker")
  .attr("id", "arrow")
  .attr("viewBox", "0 -5 10 10")
  .attr("refX", 18)
  .attr("refY", 0)
  .attr("markerWidth", 8)
  .attr("markerHeight", 8)
  .attr("orient", "auto")
  .append("path")
    .attr("d", "M0,-5L10,0L0,5")
    .attr("fill", "rgba(56,189,248,0.9)");

let simulation = d3.forceSimulation()
  .force("link", d3.forceLink().id(function(d){ return d.id; }).distance(function(d){ return 80 + Math.min(250, Math.log1p(d.sum||1)*15); }))
  .force("charge", d3.forceManyBody().strength(-300))
  .force("center", d3.forceCenter(width/2, height/2))
  .force("collide", d3.forceCollide(14));

const tooltip = d3.select("#tooltip");

let link, node;

function updateGraph() {
  // usuń poprzednie elementy
  g.selectAll("*").remove();

  // linki jako path (krzywe) z markerami
  link = g.append("g")
    .attr("class", "links")
    .selectAll("path")
    .data(graph.links)
    .enter()
    .append("path")
    .attr("class", "link")
    .attr("stroke-width", function(d){ return Math.max(1, Math.sqrt(d.sum)/20); })
    .attr("marker-end", "url(#arrow)");

  node = g.append("g")
    .attr("class", "nodes")
    .selectAll("g")
    .data(graph.nodes)
    .enter()
    .append("g")
    .attr("class", "node")
    .on("click", function(event, d){
      // kliknięcie w węzeł -> automatyczne filtrowanie jego bezpośrednich powiązań
      document.getElementById("filterInput").value = d.id;
      applyFilter(d.id);
    })
    .call(drag(simulation));

  node.append("circle")
    .attr("r", function(d){ return d.is_hub ? 10 : 6; })
    .attr("fill", function(d){ return d.is_hub ? "#38bdf8" : "#93c5fd"; });

  node.append("text")
    .attr("class", "label")
    .attr("x", 12)
    .attr("y", 4)
    .text(function(d){ return d.id; });

  // tooltip dla węzłów
  node.on("mouseover", function(event, d){
      tooltip.style("opacity", 1).html("<strong>" + d.id + "</strong><br>" + (d.is_hub ? "Hub (aktywny rachunek)" : "Zwykły rachunek"));
    })
    .on("mousemove", function(event){
      tooltip.style("left", (event.pageX + 12) + "px").style("top", (event.pageY + 12) + "px");
    })
    .on("mouseout", function(){
      tooltip.style("opacity", 0);
    });

  // tooltip dla linków
  link.on("mouseover", function(event, d){
      tooltip.style("opacity", 1).html("<strong>" + d.source.id + "</strong> → <strong>" + d.target.id + "</strong><br>Transakcji: " + d.count + "<br>Suma: " + d.sum.toFixed(2) + " PLN");
    })
    .on("mousemove", function(event){
      tooltip.style("left", (event.pageX + 12) + "px").style("top", (event.pageY + 12) + "px");
    })
    .on("mouseout", function(){
      tooltip.style("opacity", 0);
    });

  // ustawienia symulacji
  simulation.nodes(graph.nodes).on("tick", ticked);
  simulation.force("link").links(graph.links);
  simulation.alpha(1).restart();
}

function ticked() {
  // rysuj krzywe quadratic (ładne łuki)
  link.attr("d", function(d){
    const sx = d.source.x, sy = d.source.y;
    const tx = d.target.x, ty = d.target.y;
    const dx = tx - sx, dy = ty - sy;
    const mx = (sx + tx) / 2;
    const my = (sy + ty) / 2;
    const norm = Math.sqrt(dx*dx + dy*dy) || 1;
    const offset = Math.min(80, 100 / (1 + Math.log1p(d.sum || 1)));
    const cx = mx - dy / norm * offset;
    const cy = my + dx / norm * offset;
    return "M " + sx + " " + sy + " Q " + cx + " " + cy + " " + tx + " " + ty;
  });
  node.attr("transform", function(d){ return "translate(" + d.x + "," + d.y + ")"; });
}

// drag: utrzymaj fx/fy po przeciągnięciu (węzeł zostaje)
function drag(sim) {
  function started(event, d) {
    if (!event.active) sim.alphaTarget(0.25).restart();
    d.fx = d.x;
    d.fy = d.y;
  }
  function dragged(event, d) {
    d.fx = event.x;
    d.fy = event.y;
  }
  function ended(event, d) {
    if (!event.active) sim.alphaTarget(0);
    // nie czyścimy fx/fy -> węzeł zostaje tam
  }
  return d3.drag().on("start", started).on("drag", dragged).on("end", ended);
}

// zoom/pan
svg.call(d3.zoom().scaleExtent([0.2, 8]).on("zoom", function(event){
  g.attr("transform", event.transform);
}));

// filter helpers
function applyFilter(input) {
  if (!input) return;
  const connected = new Set();
  fullGraph.links.forEach(function(l){
    if (l.source === input || l.target === input) {
      connected.add(l.source);
      connected.add(l.target);
    }
  });
  if (connected.size === 0) {
    alert("Brak powiązań dla " + input);
    return;
  }
  const filteredNodes = fullGraph.nodes.filter(function(n){ return connected.has(n.id); });
  const filteredLinks = fullGraph.links.filter(function(l){ return connected.has(l.source) && connected.has(l.target); });
  graph = {nodes: filteredNodes, links: filteredLinks};
  updateGraph();
}

document.getElementById("filterBtn").addEventListener("click", function(){
  const input = document.getElementById("filterInput").value.trim();
  applyFilter(input);
});

document.getElementById("resetBtn").addEventListener("click", function(){
  graph = JSON.parse(JSON.stringify(fullGraph));
  updateGraph();
});

// initial render
updateGraph();
</script>
</body>
</html>"""

    # wstrzyknięcie JSON-a (bez f-stringów JS/Python)
    html = html.replace("__DATA__", data_json)
    Path(output_path).write_text(html, encoding="utf-8")
    print(f"✅ Wygenerowano: {output_path}")


if __name__ == "__main__":
    # Generuj dane realistyczne i zbuduj HTML
    data = generate_transaction_data_realistic(n_accounts=40, n_transactions=700)
    build_html(data, output_path="transaction_graph_filtered.html")
