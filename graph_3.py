#!/usr/bin/env python3
# transaction_graph_fixed4.py
import json
import random
import datetime
from pathlib import Path

def generate_transaction_data_realistic(n_accounts=40, n_transactions=600):
    accounts = [f"KONTO_{i:03d}" for i in range(n_accounts)]
    txs = []
    n_hubs = max(2, n_accounts // 6)
    hubs = random.sample(accounts, n_hubs)
    
    # Definiujemy zakres dat (np. ostatnie 90 dni)
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=90)
    date_range_days = (end_date - start_date).days
    
    all_dates = []

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
        
        # Generuj losową datę transakcji
        rand_days = random.randint(0, date_range_days)
        tx_date = (start_date + datetime.timedelta(days=rand_days)).isoformat()
        txs.append({"source": src, "target": tgt, "amount": amount, "date": tx_date})
        all_dates.append(tx_date)
        
        # 🔁 25% szansy na transakcję w drugą stronę
        if random.random() < 0.25:
            back_amount = round(random.paretovariate(1.5) * 150, 2)
            # Data transakcji zwrotnej (taka sama lub dzień później)
            back_date = (datetime.date.fromisoformat(tx_date) + datetime.timedelta(days=random.randint(0, 1))).isoformat()
            txs.append({"source": tgt, "target": src, "amount": back_amount, "date": back_date})
            all_dates.append(back_date)
    
    # Nie agregujemy już w Pythonie! Wysyłamy surowe transakcje.
    nodes = [{"id": a, "is_hub": a in hubs} for a in accounts]
    
    # Znajdź min i max datę do ustawienia filtrów
    min_date = min(all_dates)
    max_date = max(all_dates)
    
    return {
        "nodes": nodes, 
        "transactions": txs,
        "minDate": min_date,
        "maxDate": max_date
    }

def build_html(data, output_path="transaction_graph_fixed4.html"):
    data_json = json.dumps(data)
    html = """<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8"/>
<title>Graf transakcji z filtrowaniem dat</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
html,body{height:100%;margin:0;background:#0c1428;color:#e6eef8;font-family:Inter,Segoe UI,Arial}
svg{width:100%;height:100%;display:block}
.link{stroke:rgba(56,189,248,0.6);fill:none}
.edge-label{font-size:10px;fill:#a5d8ff;pointer-events:none;text-anchor:middle;dominant-baseline:middle}
.node circle{stroke:#0b1220;stroke-width:1.2px;cursor:grab}
text.label{font-size:11px;pointer-events:none;fill:#cfe8ff}
#tooltip{position:absolute;pointer-events:none;padding:8px;border-radius:6px;background:rgba(2,6,23,0.88);color:#dbeefe;font-size:13px;box-shadow:0 6px 18px rgba(0,0,0,0.6)}
header.ui{position:absolute;left:12px;top:12px;z-index:10;background:rgba(255,255,255,0.02);padding:8px 12px;border-radius:8px;border:1px solid rgba(255,255,255,0.03)}
input,button{padding:4px 8px;border-radius:4px;border:none;font-size:13px}
input[type=date]{background:#0c1428;color:#e6eef8;border:1px solid #2563eb;padding:3px 6px;}
button{background:#2563eb;color:white;cursor:pointer;margin-left:4px}
button:hover{background:#1e40af}
table{margin-top:10px;border-collapse:collapse;width:100%;font-size:13px;color:#d8e0f0}
th,td{border-bottom:1px solid rgba(255,255,255,0.1);padding:4px 8px;text-align:left}
#tableContainer{position:absolute;right:12px;top:12px;z-index:10;width:380px;background:rgba(255,255,255,0.04);border-radius:8px;padding:10px;overflow:auto;max-height:90%}
</style>
</head>
<body>
<header class="ui">
  <strong>Graf transakcji</strong><br>
  <small>Kliknij konto, aby zobaczyć transakcje. Filtruj wg daty lub konta.</small><br>
  <label for="dateStart">Od:</label>
  <input type="date" id="dateStart" style="vertical-align: middle;">
  <label for="dateEnd" style="margin-left: 5px;">Do:</label>
  <input type="date" id="dateEnd" style="vertical-align: middle;">
  <br style="margin-top: 6px;">
  <input id="accountInput" placeholder="np. KONTO_005" style="margin-top: 4px;"/>
  <button id="filterBtn">Pokaż graf i transakcje</button>
  <button id="resetBtn">Resetuj graf</button>
  <br>
  <label><input type="checkbox" id="showEdgeLabels" checked> Pokaż etykiety</label>
</header>
<div id="tableContainer"></div>
<div id="tooltip" style="opacity:0;"></div>
<svg></svg>

<script>
// surowe (niemutowane) dane — teraz zawierają `transactions` zamiast `links`
const rawGraph = JSON.parse(JSON.stringify(__DATA__));
// `graph` będzie dynamicznie generowany (filtrowany i agregowany)
let graph = { nodes: [], links: [] }; 
let currentAccountFilter = null; // Przechowuje stan filtra konta

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
const dateStartInput = document.getElementById("dateStart");
const dateEndInput = document.getElementById("dateEnd");

// Ustaw domyślne wartości filtrów dat na min/max z danych
dateStartInput.value = rawGraph.minDate;
dateEndInput.value = rawGraph.maxDate;

let link, node, edgeLabel;

// siła
let simulation = d3.forceSimulation()
  .force("link", d3.forceLink().id(d=>d.id).distance(d=>120+Math.log1p(d.sum||1)*15))
  .force("charge", d3.forceManyBody().strength(-400))
  .force("center", d3.forceCenter(width/2,height/2))
  .force("collide", d3.forceCollide(18));

// pomocnicza funkcja: pobiera id (obsługuje string lub obiekt)
function idOf(x){ 
  return (typeof x === "string") ? x : (x && x.id) ? x.id : null; 
}

// funkcja oblicza punkt na krzywej kwadratowej Beziera dla parametru t
function quadraticBezierPoint(p0, p1, p2, t) {
  const x = (1-t)*(1-t)*p0.x + 2*(1-t)*t*p1.x + t*t*p2.x;
  const y = (1-t)*(1-t)*p0.y + 2*(1-t)*t*p1.y + t*t*p2.y;
  return {x, y};
}

/**
 * Główna funkcja do rysowania D3.
 * Czyta dane z globalnej zmiennej `graph`.
 */
function drawD3Graph(){
  g.selectAll("*").remove();

  // mapa WSZYSTKICH połączeń (source->target)
  const allLinks = new Map();
  graph.links.forEach(l => {
    const s = idOf(l.source);
    const t = idOf(l.target);
    const key = `${s}->${t}`;
    allLinks.set(key, true);
  });

  // renderujemy linki
  link = g.append("g").selectAll("path").data(graph.links).enter()
    .append("path").attr("class","link")
    .attr("stroke-width", d => Math.max(1.5, Math.sqrt(d.sum)/20))
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

  // przekazanie do tickera
  simulation.nodes(graph.nodes).on("tick", () => ticked(allLinks));
  simulation.force("link").links(graph.links);
  simulation.alpha(1).restart();
}

function ticked(allLinks){
  link.attr("d", d => {
    const sObj = (typeof d.source === "object") ? d.source : graph.nodes.find(n => n.id === d.source);
    const tObj = (typeof d.target === "object") ? d.target : graph.nodes.find(n => n.id === d.target);
    
    const sx = sObj ? sObj.x : 0;
    const sy = sObj ? sObj.y : 0;
    const tx = tObj ? tObj.x : 0;
    const ty = tObj ? tObj.y : 0;

    const sId = idOf(d.source);
    const tId = idOf(d.target);
    
    const reverseKey = `${tId}->${sId}`;
    const hasReverse = allLinks.has(reverseKey);
    
    let curveOffset = 0;
    if (hasReverse) {
      curveOffset = (sId < tId) ? 60 : -60;
    }
    
    const nodeA = (sId < tId) ? sObj : tObj;
    const nodeB = (sId < tId) ? tObj : sObj;
    
    const nAx = nodeA ? nodeA.x : 0;
    const nAy = nodeA ? nodeA.y : 0;
    const nBx = nodeB ? nodeB.x : 0;
    const nBy = nodeB ? nodeB.y : 0;
    
    const dx_canonical = nBx - nAx;
    const dy_canonical = nBy - nAy;
    const dist_canonical = Math.sqrt(dx_canonical*dx_canonical + dy_canonical*dy_canonical) || 1;

    const perpX = -dy_canonical / dist_canonical;
    const perpY = dx_canonical / dist_canonical;
    
    const cx = (sx + tx) / 2 + perpX * curveOffset;
    const cy = (sy + ty) / 2 + perpY * curveOffset;
    
    return `M ${sx} ${sy} Q ${cx} ${cy} ${tx} ${ty}`;
  });

  node.attr("transform", d => `translate(${d.x},${d.y})`);

  if (edgeLabel) {
    edgeLabel.each(function(d) {
      const sObj = (typeof d.source === "object") ? d.source : graph.nodes.find(n => n.id === d.source);
      const tObj = (typeof d.target === "object") ? d.target : graph.nodes.find(n => n.id === d.target);
      
      const sx = sObj ? sObj.x : 0;
      const sy = sObj ? sObj.y : 0;
      const tx = tObj ? tObj.x : 0;
      const ty = tObj ? tObj.y : 0;

      const sId = idOf(d.source);
      const tId = idOf(d.target);
      
      const reverseKey = `${tId}->${sId}`;
      const hasReverse = allLinks.has(reverseKey);
      let curveOffset = 0;
      if (hasReverse) {
        curveOffset = (sId < tId) ? 60 : -60;
      }
      
      const nodeA = (sId < tId) ? sObj : tObj;
      const nodeB = (sId < tId) ? tObj : sObj;
      
      const nAx = nodeA ? nodeA.x : 0;
      const nAy = nodeA ? nodeA.y : 0;
      const nBx = nodeB ? nodeB.x : 0;
      const nBy = nodeB ? nodeB.y : 0;

      const dx_canonical = nBx - nAx;
      const dy_canonical = nBy - nAy;
      const dist_canonical = Math.sqrt(dx_canonical*dx_canonical + dy_canonical*dy_canonical) || 1;

      const perpX = -dy_canonical / dist_canonical;
      const perpY = dx_canonical / dist_canonical;

      const cx = (sx + tx) / 2 + perpX * curveOffset;
      const cy = (sy + ty) / 2 + perpY * curveOffset;
      
      const p = quadraticBezierPoint(
        {x: sx, y: sy},
        {x: cx, y: cy},
        {x: tx, y: ty},
        0.5
      );
      
      const labelOffset = hasReverse ? 12 : 8;
      const labelX = p.x + perpX * labelOffset;
      const labelY = p.y + perpY * labelOffset;
      
      d3.select(this)
        .attr("x", labelX)
        .attr("y", labelY);
    });
  }
}

// drag: TRWAŁE pozycje (nie resetujemy fx/fy)
function drag(sim){
  function started(e,d){
    if(!e.active) sim.alphaTarget(0.25).restart();
    d.fx = d.x; d.fy = d.y;
  }
  function dragged(e,d){
    d.fx = e.x; d.fy = e.y;
  }
  function ended(e,d){
    if(!e.active) sim.alphaTarget(0);
  }
  return d3.drag().on("start", started).on("drag", dragged).on("end", ended);
}

/**
 * NOWA FUNKCJA
 * Filtruje surowe dane i agreguje je, aby przygotować dane dla D3.
 * Ustawia globalną zmienną `graph` i odpala rysowanie.
 */
function updateVisualization() {
    const startDate = dateStartInput.value;
    const endDate = dateEndInput.value;
    
    // 1. Filtruj transakcje po dacie
    let filteredTransactions = rawGraph.transactions.filter(t => {
        return t.date >= startDate && t.date <= endDate;
    });
    
    let nodesToDisplay;
    
    // 2. (Jeśli aktywny) Filtruj transakcje po koncie
    if (currentAccountFilter) {
        filteredTransactions = filteredTransactions.filter(t => 
            t.source === currentAccountFilter || t.target === currentAccountFilter
        );
        
        // Znajdź powiązane węzły
        const relatedNodes = new Set([currentAccountFilter]);
        filteredTransactions.forEach(t => {
            relatedNodes.add(t.source);
            relatedNodes.add(t.target);
        });
        nodesToDisplay = rawGraph.nodes.filter(n => relatedNodes.has(n.id));
    }
    
    // 3. Agreguj przefiltrowane transakcje w linki
    const agg = {};
    for (const t of filteredTransactions) {
        const key = `${t.source}->${t.target}`; // Klucz agregacji
        if (!agg[key]) {
            agg[key] = { source: t.source, target: t.target, count: 0, sum: 0.0 };
        }
        agg[key].count += 1;
        agg[key].sum += t.amount;
    }
    // Konwertuj mapę agregacji na listę linków
    const aggregatedLinks = Object.values(agg).map(l => ({
        source: l.source,
        target: l.target,
        count: l.count,
        sum: l.sum
    }));

    // 4. (Jeśli brak filtra konta) Filtruj węzły, aby pokazać tylko te z linkami
    if (!currentAccountFilter) {
        const nodesInLinks = new Set();
        aggregatedLinks.forEach(l => {
            nodesInLinks.add(idOf(l.source));
            nodesInLinks.add(idOf(l.target));
        });
        // Pokaż też węzły bez linków, jeśli chcesz
        // nodesToDisplay = rawGraph.nodes;
        // Albo tylko te aktywne:
        nodesToDisplay = rawGraph.nodes.filter(n => nodesInLinks.has(n.id));
    }
    
    // 5. Ustaw globalny obiekt `graph`
    graph = { nodes: nodesToDisplay, links: aggregatedLinks };
    
    // 6. Narysuj graf D3
    drawD3Graph();
}


/**
 * ZMODYFIKOWANA FUNKCJA
 * Pokazuje teraz indywidualne transakcje, respektując filtr daty.
 */
function showTable(accountId){
    const startDate = dateStartInput.value;
    const endDate = dateEndInput.value;

    // Filtruj surowe transakcje po koncie ORAZ dacie
    const relevant = rawGraph.transactions.filter(t => 
        (t.source === accountId || t.target === accountId) &&
        t.date >= startDate && t.date <= endDate
    );
    
    // Sortuj (np. od najnowszych)
    relevant.sort((a, b) => b.date.localeCompare(a.date));

    if (relevant.length === 0) {
        tableContainer.html(`<h3>${accountId}</h3><p>Brak transakcji w wybranym okresie.</p>`);
        return;
    }
    
    let html = `<h3>${accountId} (Pojedyncze transakcje)</h3>
        <table><thead>
        <tr><th>Data</th><th>Nadawca</th><th>Odbiorca</th><th>Kwota</th></tr>
        </thead><tbody>`;
        
    relevant.forEach(r => {
        html += `<tr>
            <td>${r.date}</td>
            <td>${r.source}</td>
            <td>${r.target}</td>
            <td>${r.amount.toFixed(2)} zł</td>
        </tr>`;
    });
    html += "</tbody></table>";
    tableContainer.html(html);
}

// ZMODYFIKOWANE HANDLERY
document.getElementById("filterBtn").onclick = () => {
    const input = document.getElementById("accountInput").value.trim();
    if (!input) return;
    
    const accountExists = rawGraph.nodes.some(n => n.id === input);
    if (!accountExists) {
        alert("Nie znaleziono rachunku: " + input);
        return;
    }
    
    currentAccountFilter = input; // Ustaw filtr konta
    updateVisualization(); // Przebuduj graf
    showTable(currentAccountFilter); // Pokaż tabelę dla tego konta
};

document.getElementById("resetBtn").onclick = () => {
    currentAccountFilter = null; // Wyczyść filtr konta
    document.getElementById("accountInput").value = "";
    tableContainer.html("");
    updateVisualization(); // Przebuduj graf (pokaż wszystko)
};

// NOWE HANDLERY DLA DAT
dateStartInput.onchange = () => {
    updateVisualization(); // Przebuduj graf
    if (currentAccountFilter) {
        showTable(currentAccountFilter); // Odśwież tabelę, jeśli jest aktywna
    }
};
dateEndInput.onchange = () => {
    updateVisualization();
    if (currentAccountFilter) {
        showTable(currentAccountFilter);
    }
};

// Checkbox etykiet - tylko przerysowuje, nie filtruje
document.getElementById("showEdgeLabels").onchange = drawD3Graph;

// Inicjalne wywołanie
updateVisualization();
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
    build_html(data, "transaction_graph_fixed4.html")
